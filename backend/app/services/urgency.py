"""Deterministic urgency scoring service -- pure Python, no LLM.

Implements the roadmap Phase 6 urgency formula:
  urgency = (severity_weight * severity)
          + (blocking_weight * is_blocking)
          + (time_weight * (1 / max(minutes_to_deadline, 1)))

This is intentionally a red-team talking point: zero LLM calls,
100% deterministic, auditable logic.

Weight rationale (for hackathon-scope):
  - severity_weight = 0.3  -- how bad is the problem?
  - blocking_weight = 0.3  -- does it stop progress entirely?
  - time_weight     = 0.4  -- proximity to deadline dominates urgency
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issue import Issue
from app.models.escalation import Escalation


# ─── Weights (tuneable, concrete per roadmap instruction) ───

SEVERITY_WEIGHT = 0.3
BLOCKING_WEIGHT = 0.3
TIME_WEIGHT = 0.4

# When to auto-create an Escalation from an Issue
URGENCY_THRESHOLD = 0.5

# Cooldown: don't re-escalate the same Issue within N minutes
COOLDOWN_MINUTES = 5

# Max retries before marking as stuck
MAX_RETRY_COUNT = 3


def compute_urgency(
    severity: float,
    is_blocking: bool,
    minutes_to_deadline: float | None = None,
) -> float:
    """
    Compute the deterministic urgency score.

    Args:
        severity: 0.0 (low) to 1.0 (critical)
        is_blocking: whether this blocks team progress
        minutes_to_deadline: minutes remaining (None = use default)

    Returns:
        Float urgency score (0.0 to ~1.0, can exceed 1.0 in theory)
    """
    # Clamp severity
    severity = max(0.0, min(1.0, severity))

    # Blocking contribution
    blocking_val = 1.0 if is_blocking else 0.0

    # Time contribution: closer to deadline = higher urgency
    if minutes_to_deadline is not None and minutes_to_deadline > 0:
        time_val = 1.0 / max(minutes_to_deadline, 1.0)
    else:
        # Default: assume 120 minutes remaining (hackathon context)
        time_val = 1.0 / 120.0

    urgency = (
        (SEVERITY_WEIGHT * severity)
        + (BLOCKING_WEIGHT * blocking_val)
        + (TIME_WEIGHT * time_val)
    )

    return round(urgency, 4)


async def should_escalate(
    issue: Issue,
    db: AsyncSession,
    minutes_to_deadline: float | None = None,
) -> bool:
    """
    Decide whether an Issue should be escalated to the organizer queue.

    Checks:
    1. Urgency score >= URGENCY_THRESHOLD
    2. Cooldown: not re-escalated within COOLDOWN_MINUTES
    3. Max retry: hasn't exceeded MAX_RETRY_COUNT
    """
    # Check retry limit
    if issue.retry_count >= MAX_RETRY_COUNT:
        return False

    # Check cooldown
    if issue.last_escalated_at is not None:
        elapsed = datetime.now(timezone.utc) - issue.last_escalated_at
        if elapsed < timedelta(minutes=COOLDOWN_MINUTES):
            return False

    # Check if escalation already exists and is still open
    existing = await db.execute(
        select(Escalation).where(
            Escalation.issue_id == issue.id,
            Escalation.status.in_(["open", "assigned"]),
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    # Compute urgency
    urgency = compute_urgency(
        severity=issue.severity,
        is_blocking=issue.is_blocking,
        minutes_to_deadline=minutes_to_deadline,
    )
    return urgency >= URGENCY_THRESHOLD


async def create_or_update_escalation(
    issue: Issue,
    db: AsyncSession,
    minutes_to_deadline: float | None = None,
) -> Escalation | None:
    """
    Create an Escalation for the Issue if it qualifies.

    Returns the Escalation if created, None otherwise.
    """
    should_esc = await should_escalate(issue, db, minutes_to_deadline)

    if not should_esc:
        return None

    # Compute final urgency
    urgency = compute_urgency(
        severity=issue.severity,
        is_blocking=issue.is_blocking,
        minutes_to_deadline=minutes_to_deadline,
    )

    # Create escalation
    escalation = Escalation(
        issue_id=issue.id,
        urgency_score=urgency,
        status="open",
    )
    db.add(escalation)

    # Update issue state
    issue.urgency_score = urgency
    issue.last_escalated_at = datetime.now(timezone.utc)
    issue.retry_count += 1

    await db.flush()
    return escalation


async def get_escalation_queue(
    db: AsyncSession,
    status_filter: str | None = None,
) -> list[dict]:
    """
    Return the escalation queue sorted by urgency (highest first).

    Each entry includes the issue details for the organizer dashboard.
    Uses eager loading to avoid N+1 queries.
    """
    from sqlalchemy.orm import selectinload

    query = (
        select(Escalation)
        .options(selectinload(Escalation.issue))
        .order_by(Escalation.urgency_score.desc())
    )

    if status_filter:
        query = query.where(Escalation.status == status_filter)

    result = await db.execute(query)
    escalations = result.scalars().unique().all()

    queue = []
    for esc in escalations:
        queue.append({
            "escalation": esc,
            "issue": esc.issue,
        })

    return queue
