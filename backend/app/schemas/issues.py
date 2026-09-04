"""Pydantic schemas for Phase 6 -- Escalation & Urgency Scoring.

Covers Issue CRUD and Escalation queue views.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Issue CRUD ────────────────────────────────────────────


class IssueCreate(BaseModel):
    """Create a new issue.

    team_id is auto-populated from the authenticated participant's token.
    severity: 0.0 (low) to 1.0 (critical), default 0.5.
    is_blocking: whether this issue blocks the team's progress.
    participant_id: OPTIONAL — only honored when an organizer (e.g. the
        Discord bot) creates the issue on behalf of a participant. Ignored
        for participant callers, whose identity comes from their JWT.
    """
    description: str = Field(..., min_length=3, max_length=2000)
    category: str = Field(default="general", max_length=100)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    is_blocking: bool = Field(default=False)
    participant_id: Optional[uuid.UUID] = Field(default=None)


class IssueOut(BaseModel):
    id: uuid.UUID
    team_id: Optional[uuid.UUID] = None
    participant_id: Optional[uuid.UUID] = None
    description: str
    category: str
    status: str
    urgency_score: float
    is_blocking: bool
    severity: float
    retry_count: int
    last_escalated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Escalation ────────────────────────────────────────────


class EscalationResolve(BaseModel):
    """Organizer resolves an escalation.

    resolution_notes: what was done to resolve it.
    assigned_organizer / assigned_mentor: who owns/resolved the escalation
        (surfaced on the dashboard and in the explainability feed).
    """
    resolution_notes: str = Field(default="", max_length=2000)
    assigned_organizer: Optional[str] = Field(default=None, max_length=255)
    assigned_mentor: Optional[str] = Field(default=None, max_length=255)


class EscalationOut(BaseModel):
    id: uuid.UUID
    issue_id: uuid.UUID
    urgency_score: float
    status: str
    assigned_organizer: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    # Nested issue summary for the queue view
    issue: Optional[IssueOut] = None

    class Config:
        from_attributes = True
