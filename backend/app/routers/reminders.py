"""Reminders router -- Phase 9: Proactive Reminders.

Endpoints:
  POST   /reminders/sweep         -- trigger reminder sweep (organizer)
  GET    /reminders               -- organizer: view recent sweep results
  GET    /notifications           -- participant: view own notifications
  GET    /notifications/mine      -- participant: view own notifications (alias)
  PATCH  /notifications/{id}/read -- participant: mark notification as read
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import require_participant, require_organizer, require_any_role
from app.models.participant import Participant
from app.models.issue import Notification
from app.schemas.reminders import (
    ReminderTriggerRequest,
    ReminderSweepResult,
    NotificationOut,
)
from app.services.reminder import sweep_reminders

router = APIRouter(tags=["reminders"])

# ─── In-memory sweep log (for demo; production would use a table) ───
_sweep_log: list[dict] = []
_MAX_SWEEP_LOG = 50


# ─── Organizer: trigger reminder sweep ────────────────────


@router.post(
    "/reminders/sweep",
    response_model=ReminderSweepResult,
    status_code=status.HTTP_200_OK,
)
async def trigger_reminder_sweep(
    body: ReminderTriggerRequest,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger the proactive reminder sweep.

    Checks all teams' submissions against deadlines and sends
    personalized notifications for incomplete submissions.
    """
    result = await sweep_reminders(
        db=db,
        event_id=body.event_id,
        threshold_hours=body.threshold_hours,
        completeness_threshold=body.completeness_threshold,
        dry_run=body.dry_run,
    )

    await db.commit()

    # Store in sweep log (in-memory for demo)
    _sweep_log.append({
        "sweep_id": result.sweep_id,
        "teams_checked": result.teams_checked,
        "teams_needing": result.teams_needing_reminders,
        "notifications_sent": result.total_notifications_sent,
        "swept_at": result.swept_at.isoformat(),
    })
    if len(_sweep_log) > _MAX_SWEEP_LOG:
        _sweep_log.pop(0)

    return result


# ─── Organizer: list recent sweeps ────────────────────────


@router.get(
    "/reminders",
    response_model=list[dict],
)
async def list_sweeps(
    _organizer=Depends(require_organizer),
):
    """Organizer: view recent reminder sweep history."""
    return list(reversed(_sweep_log))


# ─── Participant: view own notifications ──────────────────


@router.get(
    "/notifications/mine",
    response_model=list[NotificationOut],
)
@router.get(
    "/notifications",
    response_model=list[NotificationOut],
)
async def get_my_notifications(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
    reminder_type: Optional[str] = Query(
        default=None,
        description="Filter by reminder_type",
    ),
    unread_only: bool = Query(
        default=False,
        description="If true, only return unread notifications",
    ),
):
    """Participant: view notifications for their team."""
    query = (
        select(Notification)
        .where(Notification.recipient_id == participant.id)
        .order_by(Notification.sent_at.desc())
    )

    if reminder_type:
        query = query.where(Notification.reminder_type == reminder_type)

    if unread_only:
        query = query.where(Notification.read == False)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return notifications


# ─── Participant: mark notification as read ────────────────


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationOut,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    payload: dict = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a notification as read.

    Participants can only mark their own notifications. Organizers (e.g.
    the Discord bot after delivering a DM) may mark any as read.
    """
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    if payload.get("role") == "participant":
        # Load the participant from the JWT
        result = await db.execute(
            select(Participant).where(Participant.id == payload.get("sub"))
        )
        participant = result.scalar_one_or_none()
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Participant not found",
            )
        if notification.recipient_id != participant.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only mark your own notifications as read.",
            )

    notification.read = True
    await db.flush()

    return notification


# ─── Organizer: view all notifications ────────────────────


@router.get(
    "/notifications/all",
    response_model=list[NotificationOut],
)
async def list_all_notifications(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    reminder_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Organizer: view all notifications across all teams."""
    query = (
        select(Notification)
        .order_by(Notification.sent_at.desc())
        .limit(limit)
    )

    if reminder_type:
        query = query.where(Notification.reminder_type == reminder_type)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return notifications
