"""Pydantic schemas for notification delivery -- Phase 12.

Covers the channel-agnostic notification adapter and pending notification views.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Notification Send Request ────────────────────────────


class NotificationSendRequest(BaseModel):
    """Request to send a notification through a specific channel."""
    recipient_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    channel: str = Field(
        default="auto",
        description="Channel: 'auto' (use participant preference), 'in_app', 'discord', 'email'",
    )
    content: str = Field(..., min_length=1, max_length=5000)
    trigger_reason: Optional[str] = None
    reminder_type: Optional[str] = None


class NotificationSendResponse(BaseModel):
    """Response after sending a notification."""
    notification_id: uuid.UUID
    channel: str
    delivered: bool
    message: str = ""


# ─── Pending Notification ─────────────────────────────────


class PendingNotificationOut(BaseModel):
    """A notification pending delivery (for bot polling)."""
    id: uuid.UUID
    recipient_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    channel: str
    content: str
    trigger_reason: Optional[str] = None
    reminder_type: Optional[str] = None
    read: bool = False
    sent_at: datetime

    # Recipient info for delivery
    recipient_name: Optional[str] = None
    discord_handle: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Channel Config ───────────────────────────────────────


class ChannelConfigOut(BaseModel):
    """Current channel configuration."""
    active_channels: list[str] = []
    default_channel: str = "in_app"
    discord_enabled: bool = False
    discord_channel_id: Optional[int] = None
