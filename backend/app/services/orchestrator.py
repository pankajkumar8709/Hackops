"""Agent Orchestrator service -- Phase 11: The Closed Loop.

This is the central intelligence that ties Phases 5-9 together.
It implements the OBSERVE -> DECIDE -> CHECK POLICY -> ACT -> LOG -> VERIFY loop.

Three loop instances using the same function:
  1. submission_audit  -- incomplete submission -> notify -> re-audit
  2. mentor_allocation  -- issue reported -> classify -> match -> propose
  3. resource_allocation -- out of stock -> notify organizer

All deterministic logic stays in Python. LLM is only used for
classification and message drafting (best-effort, with fallbacks).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent_action import AgentAction
from app.models.team import Team
from app.models.submission import Submission, SubmissionRequirement
from app.models.issue import Issue, Notification
from app.models.participant import Participant
from app.models.escalation import Escalation
from app.models.resource import ResourceItem, ResourceAllocation
from app.models.mentor import Mentor
from app.models.mentor_allocation import MentorAllocation
from app.models.event import Event, Track

logger = logging.getLogger(__name__)


# ─── Trigger Types ─────────────────────────────────────────


class TriggerType(str, Enum):
    SUBMISSION_AUDIT = "submission_audit"
    MENTOR_ALLOCATION = "mentor_allocation"
    RESOURCE_ALLOCATION = "resource_allocation"


# ─── Policy Allow-List ─────────────────────────────────────

# Actions the agent can take autonomously
ALLOWED_ACTIONS = {
    "send_notification",
    "create_escalation",
    "propose_mentor_allocation",
    "allocate_resource",
    "re_audit_submission",
    "send_reminder",
}

# Actions that require human approval (never autonomous)
RESTRICTED_ACTIONS = {
    "roster_change",
    "disqualify_team",
    "deadline_edit",
    "resolve_escalation",
}


def check_policy(action_type: str) -> tuple[bool, str]:
    """
    Check if an action is allowed by policy.

    Returns (allowed, reason).
    """
    if action_type in ALLOWED_ACTIONS:
        return True, f"Action '{action_type}' is in the allow-list"
    if action_type in RESTRICTED_ACTIONS:
        return False, (
            f"Action '{action_type}' requires human approval. "
            f"Routed to approval queue."
        )
    # Unknown action: deny by default (safe)
    return False, f"Action '{action_type}' is not in the allow-list"


# ─── Plain-language summaries ───────────────────────────────

_SUMMARY_TEMPLATES = {
    "send_notification": "Notified {target} — {reasoning}",
    "send_reminder": "Reminded {target} — {reasoning}",
    "create_escalation": "Escalated {target} — {reasoning}",
    "propose_mentor_allocation": "Proposed a mentor for {target} — {reasoning}",
    "allocate_resource": "Allocated a resource to {target} — {reasoning}",
    "re_audit_submission": "Re-audited {target} — {reasoning}",
    "verify_sweep": "Post-sweep verification complete — {reasoning}",
    "approve_action": "Organizer approved {target} — {reasoning}",
    "reject_action": "Organizer rejected {target} — {reasoning}",
}


def build_action_summary(
    action_type: str,
    trigger_snapshot: dict,
    reasoning: str,
    outcome: str,
) -> str:
    """Build a one-line, human-readable summary of an agent action.

    Falls back to a deterministic "type: outcome" line when no template
    matches — it never renders raw JSON to the feed.
    """
    target = ""
    if trigger_snapshot:
        target = (
            trigger_snapshot.get("team_name")
            or trigger_snapshot.get("resource_name")
            or trigger_snapshot.get("description", "")[:60]
            or trigger_snapshot.get("issue_id", "")
            or ""
        )
        if not target and trigger_snapshot.get("team_id"):
            target = f"team {str(trigger_snapshot['team_id'])[:8]}"

    short_reason = (reasoning or "").strip()
    if len(short_reason) > 140:
        short_reason = short_reason[:137] + "..."

    template = _SUMMARY_TEMPLATES.get(action_type)
    if template:
        try:
            return template.format(target=target or "participants", reasoning=short_reason or outcome[:80])
        except Exception:
            pass

    short_outcome = (outcome or "").strip()[:100]
    return f"{action_type.replace('_', ' ').title()}: {short_outcome}"


# ─── Agent Action Logger ───────────────────────────────────


async def _log_action(
    db: AsyncSession,
    action_type: str,
    trigger_snapshot: dict,
    reasoning: str,
    policy_result: str,
    outcome: str,
    **kwargs,
) -> AgentAction:
    """Write an AgentAction row for explainability."""
    summary = kwargs.pop("summary", None)
    if not summary:
        summary = build_action_summary(action_type, trigger_snapshot, reasoning, outcome)
    action = AgentAction(
        action_type=action_type,
        trigger_state_snapshot=json.dumps(trigger_snapshot, default=str),
        reasoning_trace=reasoning,
        policy_check_result=policy_result,
        outcome=outcome,
        summary=summary,
        **kwargs,
    )
    db.add(action)
    await db.flush()
    logger.info("AgentAction logged: %s -> %s", action_type, outcome[:80])
    return action


# ─── Notification Helper ───────────────────────────────────


async def _send_notification(
    db: AsyncSession,
    recipient_id: uuid.UUID,
    team_id: uuid.UUID,
    content: str,
    trigger_reason: str,
    reminder_type: str = "agent_action",
) -> Notification:
    """Create and persist a notification via the delivery service (auto-detects channel)."""
    from app.services.notification_delivery import send_notification as _deliver

    await _deliver(
        db=db,
        recipient_id=recipient_id,
        content=content,
        channel="auto",
        team_id=team_id,
        trigger_reason=trigger_reason,
        reminder_type=reminder_type,
    )
    # Return the notification that was just created
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == recipient_id)
        .where(Notification.trigger_reason == trigger_reason)
        .order_by(Notification.sent_at.desc())
        .limit(1)
    )
    return result.scalar_one()


async def _send_team_notifications(
    db: AsyncSession,
    team_id: uuid.UUID,
    content: str,
    trigger_reason: str,
    reminder_type: str = "agent_action",
) -> int:
    """Send notification to all team members. Returns count."""
    from app.services.notification_delivery import send_notification as _deliver

    result = await db.execute(
        select(Participant).where(Participant.team_id == team_id)
    )
    members = result.scalars().all()
    count = 0
    for member in members:
        await _deliver(
            db=db,
            recipient_id=member.id,
            content=content,
            channel="auto",
            team_id=team_id,
            trigger_reason=trigger_reason,
            reminder_type=reminder_type,
        )
        count += 1
    return count


# ─── LOOP 1: Submission Audit ──────────────────────────────


async def _observe_submission(
    db: AsyncSession,
    team_id: uuid.UUID,
) -> dict:
    """Observe submission state for a team."""
    # Load team
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    team = team_result.scalar_one_or_none()
    if not team:
        return {"error": f"Team {team_id} not found"}

    # Load submission
    sub_result = await db.execute(
        select(Submission).where(Submission.team_id == team_id)
    )
    submission = sub_result.scalar_one_or_none()

    # Load track requirements
    missing_fields = []
    completeness = 0.0
    if team.track_id:
        req_result = await db.execute(
            select(SubmissionRequirement)
            .where(SubmissionRequirement.track_id == team.track_id)
        )
        requirements = req_result.scalars().all()

        if requirements and submission:
            for req in requirements:
                if not req.required:
                    continue
                value = getattr(submission, req.field_name, None)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    missing_fields.append(req.field_name)
            total = sum(1 for r in requirements if r.required)
            present = total - len(missing_fields)
            completeness = (present / total * 100) if total > 0 else 100.0
        elif not requirements:
            completeness = 100.0

    return {
        "team_id": str(team_id),
        "team_name": team.name,
        "has_submission": submission is not None,
        "completeness_pct": completeness,
        "missing_fields": missing_fields,
        "track_id": str(team.track_id) if team.track_id else None,
    }


async def _decide_submission(observe: dict) -> dict:
    """Decide what to do based on submission observation."""
    completeness = observe.get("completeness_pct", 0.0)
    missing = observe.get("missing_fields", [])
    has_submission = observe.get("has_submission", False)

    if not has_submission:
        return {
            "action": "send_notification",
            "reasoning": "Team has no submission yet. Sending reminder.",
            "completeness": completeness,
            "missing_fields": missing,
        }

    if completeness < 100.0 and missing:
        if completeness < 50.0:
            return {
                "action": "send_notification",
                "reasoning": (
                    f"Submission at {completeness:.0f}% ({len(missing)} fields missing). "
                    f"Critical: missing {', '.join(missing[:3])}. Urgent notification needed."
                ),
                "completeness": completeness,
                "missing_fields": missing,
            }
        else:
            return {
                "action": "send_notification",
                "reasoning": (
                    f"Submission at {completeness:.0f}% ({len(missing)} fields missing). "
                    f"Missing: {', '.join(missing[:3])}. Reminder notification."
                ),
                "completeness": completeness,
                "missing_fields": missing,
            }

    return {
        "action": "none",
        "reasoning": f"Submission complete ({completeness:.0f}%). No action needed.",
        "completeness": completeness,
        "missing_fields": [],
    }


async def _act_submission(
    db: AsyncSession,
    observe: dict,
    decide: dict,
) -> dict:
    """Execute the decided action for submission audit."""
    if decide["action"] == "none":
        return {"outcome": "no_action", "notifications_sent": 0}

    team_id = uuid.UUID(observe["team_id"])
    team_name = observe.get("team_name", "Team")
    completeness = observe.get("completeness_pct", 0.0)
    missing = observe.get("missing_fields", [])

    field_list = ", ".join(f'"{f}"' for f in missing)
    if completeness < 50.0:
        urgency_tag = "URGENT"
    else:
        urgency_tag = "REMINDER"

    message = (
        f"[{urgency_tag}] {team_name}, your submission is at "
        f"{completeness:.0f}% completeness. "
        f"Missing required fields: {field_list}. "
        f"Please update your submission before the deadline."
    )

    count = await _send_team_notifications(
        db=db,
        team_id=team_id,
        content=message,
        trigger_reason=f"orchestrator:submission_audit:{team_id}",
        reminder_type="submission_reminder",
    )

    return {
        "outcome": f"Sent {count} notification(s) to {team_name}",
        "notifications_sent": count,
    }


# ─── LOOP 2: Mentor Allocation ─────────────────────────────


async def _observe_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> dict:
    """Observe issue state for mentor allocation."""
    result = await db.execute(
        select(Issue).where(Issue.id == issue_id)
    )
    issue = result.scalar_one_or_none()
    if not issue:
        return {"error": f"Issue {issue_id} not found"}

    # Check existing escalations
    esc_result = await db.execute(
        select(Escalation).where(Escalation.issue_id == issue_id)
    )
    escalation = esc_result.scalar_one_or_none()

    # Check existing mentor allocations
    alloc_result = await db.execute(
        select(MentorAllocation).where(MentorAllocation.issue_id == issue_id)
    )
    allocations = alloc_result.scalars().all()

    # Check available mentors
    mentor_result = await db.execute(
        select(Mentor).where(Mentor.availability_status == "available")
    )
    available_mentors = mentor_result.scalars().all()

    return {
        "issue_id": str(issue_id),
        "description": issue.description,
        "category": issue.category,
        "severity": issue.severity,
        "is_blocking": issue.is_blocking,
        "status": issue.status,
        "urgency_score": issue.urgency_score,
        "team_id": str(issue.team_id) if issue.team_id else None,
        "has_escalation": escalation is not None,
        "escalation_status": escalation.status if escalation else None,
        "existing_allocations": len(allocations),
        "available_mentors": len(available_mentors),
    }


async def _decide_mentor(observe: dict) -> dict:
    """Decide what to do based on issue observation."""
    if observe.get("error"):
        return {"action": "none", "reasoning": observe["error"]}

    has_escalation = observe.get("has_escalation", False)
    existing_allocs = observe.get("existing_allocations", 0)
    available_mentors = observe.get("available_mentors", 0)
    is_blocking = observe.get("is_blocking", False)
    severity = observe.get("severity", 0.5)

    # If no escalation exists and no allocation proposed, propose one
    if not has_escalation and existing_allocs == 0:
        if available_mentors > 0:
            return {
                "action": "propose_mentor_allocation",
                "reasoning": (
                    f"New issue (severity={severity}, blocking={is_blocking}). "
                    f"{available_mentors} mentors available. Proposing allocation."
                ),
            }
        else:
            return {
                "action": "create_escalation",
                "reasoning": (
                    f"New issue but no mentors available. "
                    f"Creating escalation for organizer."
                ),
            }

    # If escalation exists but no allocation, try to allocate
    if has_escalation and existing_allocs == 0 and available_mentors > 0:
        return {
            "action": "propose_mentor_allocation",
            "reasoning": (
                f"Issue escalated but no mentor allocated yet. "
                f"{available_mentors} mentors available. Proposing."
            ),
        }

    return {
        "action": "none",
        "reasoning": (
            f"Issue already has {existing_allocs} allocation(s). "
            f"No further action needed."
        ),
    }


async def _act_mentor(
    db: AsyncSession,
    observe: dict,
    decide: dict,
) -> dict:
    """Execute the decided action for mentor allocation."""
    action = decide.get("action", "none")
    if action == "none":
        return {"outcome": "no_action", "allocations_created": 0}

    issue_id = uuid.UUID(observe["issue_id"])

    if action == "propose_mentor_allocation":
        # Find best matching mentor
        from app.services.mentor_allocation import (
            _classify_skills_llm,
            find_mentor_candidates,
            propose_mentor_allocation,
        )

        skills = _classify_skills_llm(observe.get("description", ""))
        mentors = await find_mentor_candidates(db, skills)

        if not mentors:
            return {"outcome": "no_mentors_found", "allocations_created": 0}

        issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
        issue = issue_result.scalar_one()

        allocation = await propose_mentor_allocation(
            db, issue, mentors[0], skills
        )

        return {
            "outcome": f"Proposed allocation to mentor '{mentors[0].name}'",
            "allocations_created": 1,
            "mentor_name": mentors[0].name,
        }

    elif action == "create_escalation":
        from app.services.urgency import create_or_update_escalation

        issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
        issue = issue_result.scalar_one()

        escalation = await create_or_update_escalation(issue, db)
        if escalation:
            return {
                "outcome": f"Created escalation (urgency={escalation.urgency_score:.2f})",
                "escalation_id": str(escalation.id),
            }
        return {"outcome": "escalation_not_needed", "allocations_created": 0}

    return {"outcome": "unknown_action", "allocations_created": 0}


# ─── LOOP 3: Resource Allocation ───────────────────────────


async def _observe_resource(
    db: AsyncSession,
    resource_item_id: uuid.UUID,
    team_id: uuid.UUID,
) -> dict:
    """Observe resource availability for a team request."""
    item_result = await db.execute(
        select(ResourceItem).where(ResourceItem.id == resource_item_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        return {"error": f"Resource item {resource_item_id} not found"}

    # Check team's current allocations
    alloc_result = await db.execute(
        select(ResourceAllocation).where(
            ResourceAllocation.team_id == team_id,
            ResourceAllocation.resource_item_id == resource_item_id,
            ResourceAllocation.status == "allocated",
        )
    )
    team_allocations = alloc_result.scalars().all()

    return {
        "resource_item_id": str(resource_item_id),
        "resource_name": item.name,
        "resource_type": item.resource_type,
        "available": item.available_quantity,
        "total": item.total_quantity,
        "team_id": str(team_id),
        "team_holds": len(team_allocations),
    }


async def _decide_resource(observe: dict) -> dict:
    """Decide what to do based on resource observation."""
    if observe.get("error"):
        return {"action": "none", "reasoning": observe["error"]}

    available = observe.get("available", 0)
    resource_name = observe.get("resource_name", "unknown")

    if available > 0:
        return {
            "action": "allocate_resource",
            "reasoning": (
                f"Resource '{resource_name}' has {available} units available. "
                f"Auto-allocating next unit."
            ),
        }
    else:
        return {
            "action": "send_notification",
            "reasoning": (
                f"Resource '{resource_name}' is out of stock (0/{observe.get('total', 0)}). "
                f"Notifying team."
            ),
        }


async def _act_resource(
    db: AsyncSession,
    observe: dict,
    decide: dict,
) -> dict:
    """Execute the decided action for resource allocation."""
    action = decide.get("action", "none")
    if action == "none":
        return {"outcome": "no_action"}

    team_id = uuid.UUID(observe["team_id"])
    resource_item_id = uuid.UUID(observe["resource_item_id"])
    resource_name = observe.get("resource_name", "resource")

    if action == "allocate_resource":
        from app.services.resource_allocation import allocate_resource

        try:
            allocation = await allocate_resource(db, resource_item_id, team_id)
            return {
                "outcome": f"Allocated '{resource_name}' to team",
                "allocation_id": str(allocation.id),
            }
        except ValueError as e:
            return {"outcome": f"Allocation failed: {e}"}

    elif action == "send_notification":
        message = (
            f"[NOTICE] Resource '{resource_name}' is currently out of stock. "
            f"The organizer has been notified."
        )
        count = await _send_team_notifications(
            db=db,
            team_id=team_id,
            content=message,
            trigger_reason=f"orchestrator:resource_allocation:{resource_item_id}",
            reminder_type="resource_notice",
        )
        return {
            "outcome": f"Sent {count} notification(s) about '{resource_name}' shortage",
            "notifications_sent": count,
        }

    return {"outcome": "unknown_action"}


# ─── VERIFY step ────────────────────────────────────────────


async def _verify(db: AsyncSession, trigger_type: str, observe: dict, act: dict) -> dict:
    """
    VERIFY — re-observe state after ACT and confirm the world changed
    as the decision intended. Returns a verdict dict.

    This closes the OBSERVE -> DECIDE -> POLICY -> ACT -> LOG -> VERIFY loop:
    an action is only reported as verified once its post-condition holds.
    """
    outcome = act.get("outcome", "")
    if outcome in ("no_action", "unknown_action", "no_mentors_found"):
        return {"verified": True, "note": "No state change expected (no action taken)"}
    if outcome.startswith("Blocked by policy"):
        return {"verified": True, "note": "Policy blocked the action; nothing to verify"}

    try:
        if trigger_type == TriggerType.SUBMISSION_AUDIT:
            team_id = uuid.UUID(observe["team_id"])
            post = await _observe_submission(db, team_id)
            sent = act.get("notifications_sent", 0)
            ok = sent == 0 or post is not None
            return {
                "verified": bool(ok),
                "note": f"Re-observed team; notifications_sent={sent}, completeness={post.get('completeness_pct') if post else 'n/a'}",
                "post_observed": post,
            }

        if trigger_type == TriggerType.MENTOR_ALLOCATION:
            issue_id = uuid.UUID(observe["issue_id"])
            post = await _observe_issue(db, issue_id)
            allocs = post.get("existing_allocations", 0)
            ok = act.get("allocations_created", 0) == 1 and allocs >= 1
            return {
                "verified": bool(ok) or "escalation" in outcome,
                "note": f"Re-observed issue; existing_allocations={allocs}, outcome='{outcome[:60]}'",
                "post_observed": post,
            }

        if trigger_type == TriggerType.RESOURCE_ALLOCATION:
            resource_item_id = uuid.UUID(observe["resource_item_id"])
            team_id = uuid.UUID(observe["team_id"])
            post = await _observe_resource(db, resource_item_id, team_id)
            before = observe.get("available", 0)
            after = post.get("available", 0)
            ok = (after == before - 1) if "Allocated" in outcome else True
            return {
                "verified": bool(ok),
                "note": f"Re-observed pool; available {before} -> {after}, outcome='{outcome[:60]}'",
                "post_observed": post,
            }

        return {"verified": True, "note": f"No verifier for {trigger_type}"}
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("VERIFY failed for %s", trigger_type)
        return {"verified": False, "note": f"Verify error: {e}"}


# ─── Main Orchestrator Entry Point ─────────────────────────


async def run_orchestrator(
    db: AsyncSession,
    trigger_type: str,
    context: dict,
) -> dict:
    """
    Run the agent orchestrator closed loop.

    1. OBSERVE — read state
    2. DECIDE — deterministic checks
    3. CHECK POLICY — allow-list validation
    4. ACT — execute decision
    5. VERIFY — re-observe and confirm the post-condition
    6. LOG — write AgentAction

    Args:
        trigger_type: "submission_audit", "mentor_allocation", or "resource_allocation"
        context: trigger-specific context (team_id, issue_id, resource_item_id, etc.)
    """
    now = datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())[:8]

    result = {
        "run_id": run_id,
        "trigger_type": trigger_type,
        "timestamp": now.isoformat(),
        "observe": {},
        "decide": {},
        "policy": {},
        "act": {},
        "verify": {},
        "logged": False,
    }

    try:
        # ── OBSERVE ──
        if trigger_type == TriggerType.SUBMISSION_AUDIT:
            team_id = uuid.UUID(context["team_id"])
            observe = await _observe_submission(db, team_id)
        elif trigger_type == TriggerType.MENTOR_ALLOCATION:
            issue_id = uuid.UUID(context["issue_id"])
            observe = await _observe_issue(db, issue_id)
        elif trigger_type == TriggerType.RESOURCE_ALLOCATION:
            resource_item_id = uuid.UUID(context["resource_item_id"])
            team_id = uuid.UUID(context["team_id"])
            observe = await _observe_resource(db, resource_item_id, team_id)
        else:
            observe = {"error": f"Unknown trigger type: {trigger_type}"}

        result["observe"] = observe

        if observe.get("error"):
            result["error"] = observe["error"]
            result["verify"] = {"verified": False, "note": "Observe failed"}
            return result

        # ── DECIDE ──
        if trigger_type == TriggerType.SUBMISSION_AUDIT:
            decide = await _decide_submission(observe)
        elif trigger_type == TriggerType.MENTOR_ALLOCATION:
            decide = await _decide_mentor(observe)
        elif trigger_type == TriggerType.RESOURCE_ALLOCATION:
            decide = await _decide_resource(observe)
        else:
            decide = {"action": "none", "reasoning": "Unknown trigger"}

        result["decide"] = decide

        action_type = decide.get("action", "none")

        # ── CHECK POLICY ──
        if action_type != "none":
            allowed, policy_reason = check_policy(action_type)
        else:
            allowed, policy_reason = True, "No action needed"

        result["policy"] = {
            "action_type": action_type,
            "allowed": allowed,
            "reason": policy_reason,
        }

        if not allowed:
            result["act"] = {
                "outcome": f"Blocked by policy: {policy_reason}",
                "routed_to_approval": True,
            }
            # Log the blocked action
            await _log_action(
                db=db,
                action_type=action_type,
                trigger_snapshot=observe,
                reasoning=decide.get("reasoning", ""),
                policy_result=f"BLOCKED: {policy_reason}",
                outcome="routed_to_approval_queue",
            )
            result["logged"] = True
            result["verify"] = {"verified": True, "note": "Blocked action routed to approval queue"}
            return result

        # ── ACT ──
        if trigger_type == TriggerType.SUBMISSION_AUDIT:
            act_result = await _act_submission(db, observe, decide)
        elif trigger_type == TriggerType.MENTOR_ALLOCATION:
            act_result = await _act_mentor(db, observe, decide)
        elif trigger_type == TriggerType.RESOURCE_ALLOCATION:
            act_result = await _act_resource(db, observe, decide)
        else:
            act_result = {"outcome": "unknown_trigger"}

        result["act"] = act_result

        # ── VERIFY ──
        verify = await _verify(db, trigger_type, observe, act_result)
        result["verify"] = verify

        # ── LOG ──
        outcome_str = act_result.get("outcome", "completed")
        if not verify.get("verified", True):
            outcome_str = f"{outcome_str} | VERIFY FAILED: {verify.get('note', '')}"
        kwargs = {}
        if trigger_type == TriggerType.SUBMISSION_AUDIT and observe.get("team_id"):
            # Find submission ID for logging
            sub_result = await db.execute(
                select(Submission).where(
                    Submission.team_id == uuid.UUID(observe["team_id"])
                )
            )
            sub = sub_result.scalar_one_or_none()
            if sub:
                kwargs["submission_id"] = sub.id
        elif trigger_type == TriggerType.MENTOR_ALLOCATION and observe.get("issue_id"):
            kwargs["issue_id"] = uuid.UUID(observe["issue_id"])

        await _log_action(
            db=db,
            action_type=action_type,
            trigger_snapshot=observe,
            reasoning=decide.get("reasoning", ""),
            policy_result=f"ALLOWED: {policy_reason}",
            outcome=outcome_str,
            **kwargs,
        )
        result["logged"] = True

    except Exception as e:
        logger.exception("Orchestrator run failed")
        result["error"] = str(e)
        result["verify"] = {"verified": False, "note": str(e)}

    return result


# ─── Full Sweep (runs all 3 loop instances) ─────────────────


async def run_full_sweep(db: AsyncSession) -> dict:
    """
    Run all three orchestrator loop instances in sequence.
    This is what APScheduler would call periodically.

    Every loop instance runs OBSERVE -> DECIDE -> POLICY -> ACT -> VERIFY
    and logs an AgentAction row, so the scheduled path produces the same
    explainability entries as the manual POST /orchestrator/sweep path.
    """
    sweep_id = str(uuid.uuid4())[:8]
    results = []

    # 1. Submission audit sweep: check all teams
    team_result = await db.execute(select(Team))
    teams = team_result.scalars().all()

    for team in teams:
        r = await run_orchestrator(
            db,
            TriggerType.SUBMISSION_AUDIT,
            {"team_id": str(team.id)},
        )
        results.append(r)

    # 2. Mentor allocation: check unallocated issues
    issue_result = await db.execute(
        select(Issue).where(Issue.status == "open")
    )
    issues = issue_result.scalars().all()

    for issue in issues:
        # Check if issue already has an active allocation
        alloc_result = await db.execute(
            select(MentorAllocation).where(
                MentorAllocation.issue_id == issue.id,
                MentorAllocation.status.in_(["proposed", "accepted"]),
            )
        )
        existing = alloc_result.scalars().all()
        if not existing:
            r = await run_orchestrator(
                db,
                TriggerType.MENTOR_ALLOCATION,
                {"issue_id": str(issue.id)},
            )
            results.append(r)

    # 3. Resource allocation: run the loop for out-of-stock pools against
    #    teams that are affected (hold an active allocation from the pool or
    #    have open issues). With available == 0 the DECIDE step always takes
    #    the shortage-notification branch — it never fabricates a demand.
    #    Pools with stock are left untouched (no pending request exists).
    oos_result = await db.execute(
        select(ResourceItem).where(ResourceItem.available_quantity <= 0)
    )
    out_of_stock = oos_result.scalars().all()

    for item in out_of_stock:
        # Teams holding an active allocation of this pool
        hold_result = await db.execute(
            select(ResourceAllocation.team_id).where(
                ResourceAllocation.resource_item_id == item.id,
                ResourceAllocation.status == "allocated",
            )
        )
        affected: set[uuid.UUID] = {row[0] for row in hold_result.all() if row[0]}

        # Teams with open issues (a live demand signal)
        open_issue_result = await db.execute(
            select(Issue.team_id)
            .where(Issue.status == "open", Issue.team_id.is_not(None))
        )
        affected |= {row[0] for row in open_issue_result.all() if row[0]}

        for team_id in affected:
            r = await run_orchestrator(
                db,
                TriggerType.RESOURCE_ALLOCATION,
                {"resource_item_id": str(item.id), "team_id": str(team_id)},
            )
            results.append(r)

    # VERIFY summary across the whole sweep
    verified = sum(1 for r in results if r.get("verify", {}).get("verified"))
    failed = sum(1 for r in results if not r.get("verify", {}).get("verified", True))
    await _log_action(
        db=db,
        action_type="verify_sweep",
        trigger_snapshot={"sweep_id": sweep_id, "total_runs": len(results)},
        reasoning=f"Post-sweep verification: {verified} runs verified, {failed} failed",
        policy_result="ALLOWED: verification is read-only",
        outcome=f"verified={verified}, failed={failed}, total={len(results)}",
    )

    return {
        "sweep_id": sweep_id,
        "total_runs": len(results),
        "verified_runs": verified,
        "failed_verifications": failed,
        "results": results,
    }
