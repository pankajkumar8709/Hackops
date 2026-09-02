"""Issues & Escalations router -- Phase 6: Escalation & Urgency Scoring.

Endpoints:
  POST   /issues                    -- participant reports an issue
  GET    /issues/mine               -- participant views own issues
  GET    /issues/{id}               -- participant views specific issue (own team)
  GET    /escalations               -- organizer: escalation queue sorted by urgency
  PATCH  /escalations/{id}/resolve  -- organizer: resolve an escalation
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_participant, require_organizer
from app.models.participant import Participant
from app.models.issue import Issue
from app.models.escalation import Escalation
from app.schemas.issues import (
    IssueCreate,
    IssueOut,
    EscalationOut,
    EscalationResolve,
)
from app.services.urgency import (
    compute_urgency,
    create_or_update_escalation,
    get_escalation_queue,
)

router = APIRouter(tags=["issues"])


# ─── Participant-facing endpoints ──────────────────────────


@router.post("/issues", response_model=IssueOut, status_code=status.HTTP_201_CREATED)
async def create_issue(
    body: IssueCreate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
    minutes_to_deadline: Optional[float] = Query(
        default=None,
        ge=0.0,
        description="Minutes to event deadline (None = default hackathon context)",
    ),
):
    """
    Participant reports an issue (problem, blocker, question needing human help).

    The urgency score is computed deterministically and the issue may be
    auto-escalated to the organizer queue if urgency crosses threshold.
    """
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must be in a team to report an issue.",
        )

    # Create the issue
    issue = Issue(
        participant_id=participant.id,
        team_id=participant.team_id,
        description=body.description,
        category=body.category,
        severity=body.severity,
        is_blocking=body.is_blocking,
    )
    db.add(issue)
    await db.flush()

    # Compute urgency and possibly escalate
    urgency = compute_urgency(
        severity=issue.severity,
        is_blocking=issue.is_blocking,
        minutes_to_deadline=minutes_to_deadline,
    )
    issue.urgency_score = urgency

    await create_or_update_escalation(issue, db, minutes_to_deadline)

    await db.commit()
    await db.refresh(issue)
    return issue


@router.get("/issues/mine", response_model=list[IssueOut])
async def get_my_issues(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """Return all issues reported by the authenticated participant's team."""
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You must be in a team to view issues.",
        )

    result = await db.execute(
        select(Issue)
        .where(Issue.team_id == participant.team_id)
        .order_by(Issue.created_at.desc())
    )
    return result.scalars().all()


@router.get("/issues/{issue_id}", response_model=IssueOut)
async def get_issue(
    issue_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """View a specific issue. Participants can only view their own team's."""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found.",
        )

    # Row-level scoping
    if issue.team_id != participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own team's issues.",
        )

    return issue


# ─── Organizer-only endpoints ───────────────────────────────


@router.get("/escalations", response_model=list[EscalationOut])
async def list_escalations(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: open, assigned, resolved",
    ),
):
    """
    Organizer: return the escalation queue sorted by urgency (highest first).

    This is the main view for the organizer dashboard.
    """
    queue = await get_escalation_queue(db, status_filter=status)

    # Build response with nested issue data
    results = []
    for entry in queue:
        esc = entry["escalation"]
        issue = entry["issue"]

        esc_out = EscalationOut(
            id=esc.id,
            issue_id=esc.issue_id,
            urgency_score=esc.urgency_score,
            status=esc.status,
            assigned_organizer=esc.assigned_organizer,
            resolution_notes=esc.resolution_notes,
            created_at=esc.created_at,
            resolved_at=esc.resolved_at,
            issue=IssueOut.model_validate(issue) if issue else None,
        )
        results.append(esc_out)

    return results


@router.patch(
    "/escalations/{escalation_id}/resolve",
    response_model=EscalationOut,
)
async def resolve_escalation(
    escalation_id: uuid.UUID,
    body: EscalationResolve,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Organizer: resolve an escalation.

    Sets status to "resolved" and records resolution notes.
    Also updates the underlying issue status to "resolved".
    """
    result = await db.execute(
        select(Escalation).where(Escalation.id == escalation_id)
    )
    escalation = result.scalar_one_or_none()
    if not escalation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found.",
        )

    # Mark escalation as resolved
    escalation.status = "resolved"
    escalation.resolution_notes = body.resolution_notes
    escalation.resolved_at = datetime.now(timezone.utc)

    # Also resolve the underlying issue
    issue_result = await db.execute(
        select(Issue).where(Issue.id == escalation.issue_id)
    )
    issue = issue_result.scalar_one_or_none()
    if issue:
        issue.status = "resolved"

    await db.commit()
    await db.refresh(escalation)

    # Load issue for response
    issue_result = await db.execute(
        select(Issue).where(Issue.id == escalation.issue_id)
    )
    issue = issue_result.scalar_one_or_none()

    return EscalationOut(
        id=escalation.id,
        issue_id=escalation.issue_id,
        urgency_score=escalation.urgency_score,
        status=escalation.status,
        assigned_organizer=escalation.assigned_organizer,
        resolution_notes=escalation.resolution_notes,
        created_at=escalation.created_at,
        resolved_at=escalation.resolved_at,
        issue=IssueOut.model_validate(issue) if issue else None,
    )
