"""Pydantic schemas for Phase 13 -- Organizer Dashboard."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Health Dashboard ─────────────────────────────────────

class TeamHealthSummary(BaseModel):
    """Compact health summary for a single team."""
    id: uuid.UUID
    name: str
    submission_status: str
    readiness_pct: float
    member_count: int
    open_issues: int


class MentorLoadSummary(BaseModel):
    """Mentor load for the dashboard."""
    id: uuid.UUID
    name: str
    availability_status: str
    active_allocations: int
    skills: list[str] = []


class ResourcePoolSummary(BaseModel):
    """Resource pool status for the dashboard."""
    id: uuid.UUID
    name: str
    resource_type: str
    total_quantity: int
    available_quantity: int
    allocated_count: int


class DashboardHealth(BaseModel):
    """Full dashboard health view."""
    total_teams: int
    teams_ready: int
    avg_readiness_pct: float
    total_participants: int
    open_escalations: int
    total_issues: int
    total_notifications: int
    total_agent_actions: int
    total_submissions: int
    teams: list[TeamHealthSummary] = []
    mentors: list[MentorLoadSummary] = []
    resource_pools: list[ResourcePoolSummary] = []


# ─── Approval Queue ───────────────────────────────────────

class ApprovalItem(BaseModel):
    """An item in the approval queue — something the agent proposed."""
    id: uuid.UUID
    action_type: str
    description: str
    reasoning: Optional[str] = None
    status: str  # "pending", "approved", "rejected"
    entity_type: str  # "mentor_allocation", "resource_allocation", etc.
    entity_id: uuid.UUID
    created_at: datetime


class ApprovalQueue(BaseModel):
    """Full approval queue for the dashboard."""
    items: list[ApprovalItem] = []
    total_pending: int = 0


# ─── Broadcast ────────────────────────────────────────────

class BroadcastRequest(BaseModel):
    """Request to broadcast a message to all participants."""
    message: str = Field(..., min_length=1, max_length=2000)
    channel: str = Field(default="in_app", description="Channel: in_app, discord, all")


class BroadcastResult(BaseModel):
    """Result of a broadcast."""
    total_recipients: int
    notifications_sent: int
    message_preview: str


# ─── Manual Override ──────────────────────────────────────

class TeamOverride(BaseModel):
    """Manual override for a team record."""
    submission_status: Optional[str] = None
    readiness_pct: Optional[float] = None


class SubmissionOverride(BaseModel):
    """Manual override for a submission record."""
    completeness_pct: Optional[float] = None
