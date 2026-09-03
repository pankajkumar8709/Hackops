"""Pydantic schemas for Phase 9 -- Proactive Reminders.

Covers reminder triggers, notification responses, and sweep results.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Notification ─────────────────────────────────────────


class NotificationOut(BaseModel):
    """A single notification sent to a participant."""
    id: uuid.UUID
    recipient_id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    channel: str
    content: str
    trigger_reason: Optional[str] = None
    reminder_type: Optional[str] = None
    read: bool = False
    sent_at: datetime

    class Config:
        from_attributes = True


# ─── Reminder Sweep ──────────────────────────────────────


class ReminderTeamResult(BaseModel):
    """Result for one team after a reminder sweep."""
    team_id: uuid.UUID
    team_name: str
    completeness_pct: float
    deadline_at: Optional[datetime] = None
    hours_remaining: Optional[float] = None
    missing_fields: list[str] = []
    notifications_sent: int = 0
    message_preview: str = ""


class ReminderSweepResult(BaseModel):
    """Summary of a full reminder sweep."""
    sweep_id: str
    teams_checked: int
    teams_needing_reminders: int
    total_notifications_sent: int
    deadline_at: Optional[datetime] = None
    teams: list[ReminderTeamResult] = []
    swept_at: datetime


# ─── Trigger Config ──────────────────────────────────────


class ReminderTriggerRequest(BaseModel):
    """Manual trigger for the reminder sweep."""
    event_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Specific event to sweep. If omitted, sweeps all events with deadlines.",
    )
    threshold_hours: float = Field(
        default=24.0,
        ge=0.5,
        description="Only remind teams within this many hours of deadline.",
    )
    completeness_threshold: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Only remind teams below this completeness percentage.",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, compute reminders but don't actually send notifications.",
    )
