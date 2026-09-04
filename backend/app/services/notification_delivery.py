"""Notification Delivery service -- Phase 12: Discord Integration.

Channel-agnostic notification adapter. Same internal service, different adapter.
This is the architectural pattern that makes adding Slack/email/WhatsApp trivial.

Delivery channels:
  - in_app: stored in notifications table (default, always works)
  - discord: DM via Discord bot (requires bot running)
  - email: via SMTP (stub -- architecturally trivial, not built)

The bot polls GET /notifications/pending for discord-queued notifications.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.participant import Participant
from app.models.issue import Notification

logger = logging.getLogger(__name__)


# ─── Channel Resolution ───────────────────────────────────


def resolve_channel(
    participant: Participant,
    requested_channel: str = "auto",
) -> str:
    """
    Resolve which channel to use for delivering a notification.

    If 'auto', picks the best channel based on participant's preferences.
    If a specific channel is requested, use that (if available).
    """
    if requested_channel != "auto":
        return requested_channel

    # Auto-detect: prefer discord if handle exists, else in_app
    if participant.discord_handle:
        return "discord"

    return "in_app"


# ─── Send Notification ────────────────────────────────────


async def send_notification(
    db: AsyncSession,
    recipient_id: uuid.UUID,
    content: str,
    channel: str = "auto",
    team_id: Optional[uuid.UUID] = None,
    trigger_reason: Optional[str] = None,
    reminder_type: Optional[str] = None,
) -> Notification:
    """
    Send a notification through the appropriate channel.

    1. Resolve the channel (auto-detect or explicit)
    2. Create the notification record
    3. For discord: mark as pending (bot will pick up)
    4. For in_app: already stored, visible via API

    Returns the Notification record.
    """
    # Load recipient
    result = await db.execute(
        select(Participant).where(Participant.id == recipient_id)
    )
    participant = result.scalar_one_or_none()

    if not participant:
        raise ValueError(f"Participant {recipient_id} not found")

    # Resolve channel
    resolved_channel = resolve_channel(participant, channel)

    # Create notification record
    notification = Notification(
        recipient_id=recipient_id,
        team_id=team_id or participant.team_id,
        channel=resolved_channel,
        content=content,
        trigger_reason=trigger_reason,
        reminder_type=reminder_type,
        read=False,
    )
    db.add(notification)
    await db.flush()

    logger.info(
        "Notification created: id=%s channel=%s recipient=%s content=%s",
        notification.id, resolved_channel, participant.name, content[:60],
    )

    return notification


async def send_team_notification(
    db: AsyncSession,
    team_id: uuid.UUID,
    content: str,
    channel: str = "auto",
    trigger_reason: Optional[str] = None,
    reminder_type: Optional[str] = None,
) -> list[Notification]:
    """Send a notification to all members of a team."""
    from app.models.participant import Participant

    result = await db.execute(
        select(Participant).where(Participant.team_id == team_id)
    )
    members = result.scalars().all()

    notifications = []
    for member in members:
        notif = await send_notification(
            db=db,
            recipient_id=member.id,
            content=content,
            channel=channel,
            team_id=team_id,
            trigger_reason=trigger_reason,
            reminder_type=reminder_type,
        )
        notifications.append(notif)

    return notifications


# ─── Pending Notifications (for bot polling) ───────────────


async def get_pending_notifications(
    db: AsyncSession,
    channel: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Get notifications pending delivery.

    For the Discord bot to poll and deliver via DM.
    Returns notifications with recipient info for delivery.
    """
    query = (
        select(Notification, Participant)
        .join(Participant, Notification.recipient_id == Participant.id)
        .where(Notification.read == False)
        .order_by(Notification.sent_at.asc())
        .limit(limit)
    )

    if channel:
        query = query.where(Notification.channel == channel)

    result = await db.execute(query)
    rows = result.all()

    pending = []
    for notif, participant in rows:
        pending.append({
            "id": notif.id,
            "recipient_id": notif.recipient_id,
            "team_id": notif.team_id,
            "channel": notif.channel,
            "content": notif.content,
            "trigger_reason": notif.trigger_reason,
            "reminder_type": notif.reminder_type,
            "read": notif.read,
            "sent_at": notif.sent_at.isoformat() if notif.sent_at else None,
            "recipient_name": participant.name,
            "discord_handle": participant.discord_handle,
        })

    return pending


# ─── Channel Status ───────────────────────────────────────


def get_channel_status() -> dict:
    """Get current channel configuration status."""
    import os

    discord_token = os.environ.get("DISCORD_TOKEN", "")
    discord_channel_id = os.environ.get("DISCORD_CHANNEL_ID", "0")

    return {
        "active_channels": ["in_app", "discord"] if discord_token else ["in_app"],
        "default_channel": "in_app",
        "discord_enabled": bool(discord_token),
        "discord_channel_id": int(discord_channel_id) if discord_channel_id else None,
    }
