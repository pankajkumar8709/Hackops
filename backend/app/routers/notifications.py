"""Notifications router -- Phase 12: Discord Integration.

Endpoints for the channel-agnostic notification delivery system:
  POST   /notifications/send       -- send a notification through a channel
  GET    /notifications/pending    -- pending notifications for bot polling
  GET    /notifications/channels   -- channel configuration status
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_organizer
from app.schemas.notifications import (
    NotificationSendRequest,
    NotificationSendResponse,
    PendingNotificationOut,
    ChannelConfigOut,
)
from app.services.notification_delivery import (
    send_notification,
    get_pending_notifications,
    get_channel_status,
)

router = APIRouter(tags=["notifications"])


# ─── Send notification ────────────────────────────────────


@router.post(
    "/notifications/send",
    response_model=NotificationSendResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_notif(
    body: NotificationSendRequest,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a notification through the appropriate channel.

    The system auto-detects the best channel based on participant preferences.
    Use channel='auto' for smart routing, or specify 'discord'/'in_app' explicitly.
    """
    try:
        notification = await send_notification(
            db=db,
            recipient_id=body.recipient_id,
            content=body.content,
            channel=body.channel,
            team_id=body.team_id,
            trigger_reason=body.trigger_reason,
            reminder_type=body.reminder_type,
        )
        await db.commit()

        return NotificationSendResponse(
            notification_id=notification.id,
            channel=notification.channel,
            delivered=True,
            message=f"Notification sent via {notification.channel}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ─── Pending notifications (bot polls this) ───────────────


@router.get(
    "/notifications/pending",
    response_model=list[PendingNotificationOut],
)
async def list_pending(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    channel: Optional[str] = Query(
        default=None,
        description="Filter by channel (discord, in_app, etc.)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Get notifications pending delivery.

    The Discord bot polls this endpoint to pick up notifications
    that need to be delivered via DM.
    """
    pending = await get_pending_notifications(db, channel=channel, limit=limit)
    return pending


# ─── Channel status ───────────────────────────────────────


@router.get(
    "/notifications/channels",
    response_model=ChannelConfigOut,
)
async def channel_status(
    _organizer=Depends(require_organizer),
):
    """
    Get current channel configuration.

    Shows which channels are active and configured.
    """
    return get_channel_status()
