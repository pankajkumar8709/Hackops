"""Submissions router — Phase 5: Submission Audit Module.

Endpoints:
  POST   /submissions          — team submits a project (creates or replaces)
  PATCH  /submissions/{id}     — update submission fields
  GET    /submissions/{id}     — view submission
  GET    /submissions/{id}/audit — deterministic audit of completeness
  GET    /submissions/mine     — view own team's submission
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_participant, require_organizer
from app.models.participant import Participant
from app.models.submission import Submission
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionUpdate,
    SubmissionOut,
    AuditResult,
)
from app.services.audit import run_audit

router = APIRouter(prefix="/submissions", tags=["submissions"])


# ─── Team-facing endpoints ──────────────────────────────────


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def create_or_replace_submission(
    body: SubmissionCreate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a project for the authenticated participant's team.
    If a submission already exists for this team, it is replaced.
    Automatically runs the deterministic audit after creation.
    """
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must be in a team to submit.",
        )

    # Check for existing submission
    result = await db.execute(
        select(Submission).where(Submission.team_id == participant.team_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing submission
        for field in ("repo_url", "readme_url", "demo_url", "description"):
            new_val = getattr(body, field, None)
            if new_val is not None:
                setattr(existing, field, new_val)
        existing.updated_at = datetime.now(timezone.utc)
        submission = existing
    else:
        # Create new submission
        submission = Submission(
            team_id=participant.team_id,
            repo_url=body.repo_url,
            readme_url=body.readme_url,
            demo_url=body.demo_url,
            description=body.description,
        )
        db.add(submission)

    await db.flush()

    # Run deterministic audit (pure Python — no LLM)
    await run_audit(submission, db)

    await db.commit()
    await db.refresh(submission)
    return submission


@router.get("/mine", response_model=SubmissionOut)
async def get_my_submission(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated participant's team submission."""
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You must be in a team to view a submission.",
        )

    result = await db.execute(
        select(Submission).where(Submission.team_id == participant.team_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No submission found for your team.",
        )
    return submission


# ─── Shared by participants and organizers ──────────────────


@router.get("/{submission_id}", response_model=SubmissionOut)
async def get_submission(
    submission_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """View a specific submission. Participants can only view their own team's."""
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    # Row-level scoping: participants can only see their own team's submission
    if submission.team_id != participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own team's submission.",
        )

    return submission


@router.patch("/{submission_id}", response_model=SubmissionOut)
async def update_submission(
    submission_id: uuid.UUID,
    body: SubmissionUpdate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Update submission fields. Participants can only update their own team's.
    Automatically re-runs the deterministic audit after update.
    """
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    # Row-level scoping
    if submission.team_id != participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own team's submission.",
        )

    # Apply updates
    for field in ("repo_url", "readme_url", "demo_url", "description"):
        new_val = getattr(body, field, None)
        if new_val is not None:
            setattr(submission, field, new_val)
    submission.updated_at = datetime.now(timezone.utc)

    # Re-run deterministic audit
    await run_audit(submission, db)

    await db.commit()
    await db.refresh(submission)
    return submission


@router.get("/{submission_id}/audit", response_model=AuditResult)
async def get_submission_audit(
    submission_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Run and return the deterministic audit for a submission.
    Checks each required field against the track's SubmissionRequirement rows.
    Pure Python — no LLM calls.
    """
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    # Row-level scoping
    if submission.team_id != participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only audit your own team's submission.",
        )

    # Run audit
    audit = await run_audit(submission, db)
    await db.commit()

    return audit


# ─── Organizer-only endpoints ───────────────────────────────


@router.get("", response_model=list[SubmissionOut])
async def list_submissions(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Organizer-only: list all submissions."""
    result = await db.execute(
        select(Submission).order_by(Submission.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{submission_id}/audit-organizer", response_model=AuditResult)
async def get_submission_audit_organizer(
    submission_id: uuid.UUID,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Organizer-only: run and return the deterministic audit for any submission.
    No row-level scoping — organizers can view any team's audit.
    """
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    audit = await run_audit(submission, db)
    await db.commit()
    return audit
