"""Allocations router -- Phase 7: Mentor Allocation.

Endpoints:
  POST   /mentor-allocations              -- propose a mentor allocation for an issue
  GET    /mentor-allocations/mine         -- mentor views own proposed allocations
  GET    /mentor-allocations              -- organizer: list all allocations
  GET    /mentor-allocations/{id}         -- view specific allocation
  PATCH  /mentor-allocations/{id}/accept  -- mentor accepts allocation
  PATCH  /mentor-allocations/{id}/decline -- mentor declines allocation
  POST   /mentor-allocations/check-timeouts -- trigger timeout check (organizer)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import require_participant, require_organizer
from app.models.participant import Participant
from app.models.mentor import Mentor
from app.models.mentor_allocation import MentorAllocation
from app.models.issue import Issue
from app.schemas.allocations import (
    AllocationCreate,
    AllocationOut,
    AllocationAccept,
    AllocationDecline,
    MentorSummary,
)
from app.services.mentor_allocation import (
    _classify_skills_llm,
    find_mentor_candidates,
    propose_mentor_allocation,
    check_and_handle_timeouts,
)

router = APIRouter(prefix="/mentor-allocations", tags=["mentor-allocations"])


# ─── Participant: request mentor help ────────────────────────


@router.post("", response_model=AllocationOut, status_code=status.HTTP_201_CREATED)
async def request_mentor_allocation(
    body: AllocationCreate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Request a mentor allocation for an issue.

    The system will:
    1. Classify the issue's needed skills (LLM call)
    2. Find available mentors with matching skills
    3. Create a proposed allocation with the best match
    4. Notify the mentor (via allocation reasoning)

    If no match is found, returns 404 with guidance.
    """
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must be in a team to request a mentor.",
        )

    # Load the issue
    result = await db.execute(
        select(Issue).where(Issue.id == body.issue_id)
    )
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
            detail="You can only request mentors for your own team's issues.",
        )

    # Check if there's already an active allocation for this issue
    existing = await db.execute(
        select(MentorAllocation).where(
            MentorAllocation.issue_id == body.issue_id,
            MentorAllocation.status.in_(["proposed", "accepted"]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active mentor allocation already exists for this issue.",
        )

    # Classify issue skills
    classified_skills = await _classify_skills(issue.description)

    # Find matching mentors
    candidates = await find_mentor_candidates(db, classified_skills)

    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No available mentors found with skills matching: "
                f"{', '.join(classified_skills)}. "
                f"This has been noted for organizer follow-up."
            ),
        )

    # Propose allocation to best candidate
    best_mentor = candidates[0]
    allocation = await propose_mentor_allocation(
        db, issue, best_mentor, classified_skills
    )

    await db.commit()

    # Reload with relationships for response
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(MentorAllocation.id == allocation.id)
    )
    allocation = result.scalar_one()

    return _build_allocation_out(allocation)


# ─── Mentor: view own allocations ───────────────────────────


@router.get("/mine", response_model=list[AllocationOut])
async def get_my_allocations(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: proposed, accepted, declined, timed_out",
    ),
):
    """
    Mentor views their own proposed allocations.

    Note: In hackathon scope, mentors are matched by skill overlap.
    A participant can view allocations where they are the proposed mentor.
    For demo purposes, we return all proposed allocations (any mentor).
    """
    query = (
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .order_by(MentorAllocation.proposed_at.desc())
    )

    if status_filter:
        query = query.where(MentorAllocation.status == status_filter)

    result = await db.execute(query)
    allocations = result.scalars().unique().all()

    return [_build_allocation_out(a) for a in allocations]


# ─── Organizer: list all allocations ────────────────────────


@router.get("", response_model=list[AllocationOut])
async def list_allocations(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: proposed, accepted, declined, timed_out",
    ),
):
    """Organizer: list all mentor allocations with filters."""
    query = (
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .order_by(MentorAllocation.proposed_at.desc())
    )

    if status_filter:
        query = query.where(MentorAllocation.status == status_filter)

    result = await db.execute(query)
    allocations = result.scalars().unique().all()

    return [_build_allocation_out(a) for a in allocations]


# ─── View specific allocation ───────────────────────────────


@router.get("/{allocation_id}", response_model=AllocationOut)
async def get_allocation(
    allocation_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """View a specific mentor allocation."""
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(MentorAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found.",
        )

    return _build_allocation_out(allocation)


# ─── Mentor: accept allocation ──────────────────────────────


@router.patch("/{allocation_id}/accept", response_model=AllocationOut)
async def accept_allocation(
    allocation_id: uuid.UUID,
    body: AllocationAccept,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Mentor accepts a proposed allocation.

    Updates status to 'accepted' and records the response timestamp.
    """
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(MentorAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found.",
        )

    if allocation.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot accept allocation with status '{allocation.status}'.",
        )

    allocation.status = "accepted"
    allocation.responded_at = datetime.now(timezone.utc)
    if body.notes:
        allocation.reasoning = (
            (allocation.reasoning or "") + f" | Mentor notes: {body.notes}"
        )

    await db.commit()
    await db.refresh(allocation)

    # Reload with relationships
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(MentorAllocation.id == allocation.id)
    )
    allocation = result.scalar_one()

    return _build_allocation_out(allocation)


# ─── Mentor: decline allocation ─────────────────────────────


@router.patch("/{allocation_id}/decline", response_model=AllocationOut)
async def decline_allocation(
    allocation_id: uuid.UUID,
    body: AllocationDecline,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Mentor declines a proposed allocation.

    Updates status to 'declined' and records the reason.
    The system can re-offer to the next available mentor.
    """
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(MentorAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found.",
        )

    if allocation.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot decline allocation with status '{allocation.status}'.",
        )

    allocation.status = "declined"
    allocation.responded_at = datetime.now(timezone.utc)
    allocation.reasoning = (
        (allocation.reasoning or "") + f" | Declined: {body.reason}"
    )

    await db.commit()
    await db.refresh(allocation)

    # Reload with relationships
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(MentorAllocation.id == allocation.id)
    )
    allocation = result.scalar_one()

    return _build_allocation_out(allocation)


# ─── Organizer: trigger timeout check ───────────────────────


@router.post("/check-timeouts", response_model=list[AllocationOut])
async def trigger_timeout_check(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Organizer: manually trigger timeout check for pending allocations.

    Any timed-out allocations will be re-offered to the next available mentor.
    """
    reoffered = await check_and_handle_timeouts(db)
    await db.commit()

    # Reload with relationships
    results = []
    for alloc in reoffered:
        result = await db.execute(
            select(MentorAllocation)
            .options(
                selectinload(MentorAllocation.mentor),
                selectinload(MentorAllocation.issue),
            )
            .where(MentorAllocation.id == alloc.id)
        )
        loaded = result.scalar_one_or_none()
        if loaded:
            results.append(_build_allocation_out(loaded))

    return results


# ─── Helper: classify skills ────────────────────────────────


async def _classify_skills(description: str) -> list[str]:
    """Classify issue skills, falling back to keyword extraction."""
    return _classify_skills_llm(description)


# ─── Helper: build response ─────────────────────────────────


def _build_allocation_out(allocation: MentorAllocation) -> AllocationOut:
    """Build AllocationOut from a loaded MentorAllocation with relationships."""
    mentor_summary = None
    if allocation.mentor:
        mentor_summary = MentorSummary(
            id=allocation.mentor.id,
            name=allocation.mentor.name,
            skills=allocation.mentor.skills or [],
            availability_status=allocation.mentor.availability_status,
        )

    issue_summary = None
    if allocation.issue:
        issue_summary = {
            "id": str(allocation.issue.id),
            "description": allocation.issue.description[:200],
            "category": allocation.issue.category,
            "urgency_score": allocation.issue.urgency_score,
            "status": allocation.issue.status,
        }

    return AllocationOut(
        id=allocation.id,
        mentor_id=allocation.mentor_id,
        issue_id=allocation.issue_id,
        status=allocation.status,
        reasoning=allocation.reasoning,
        proposed_at=allocation.proposed_at,
        responded_at=allocation.responded_at,
        timed_out_at=allocation.timed_out_at,
        mentor=mentor_summary,
        issue_summary=issue_summary,
    )
