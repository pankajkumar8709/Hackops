"""Pydantic schemas for Phase 7 -- Mentor Allocation.

Covers allocation CRUD: propose, accept, decline, timeout.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Allocation CRUD ────────────────────────────────────────


class AllocationCreate(BaseModel):
    """Request to propose a mentor allocation for an issue.

    The system will classify the issue, find matching mentors,
    and create a proposed allocation.
    """
    issue_id: uuid.UUID


class MentorSummary(BaseModel):
    """Brief mentor info for allocation response."""
    id: uuid.UUID
    name: str
    skills: list[str] = []
    availability_status: str = "available"

    class Config:
        from_attributes = True


class AllocationOut(BaseModel):
    """Full allocation response with mentor and issue details."""
    id: uuid.UUID
    mentor_id: uuid.UUID
    issue_id: uuid.UUID
    status: str
    reasoning: Optional[str] = None
    proposed_at: datetime
    responded_at: Optional[datetime] = None
    timed_out_at: Optional[datetime] = None

    # Nested summaries
    mentor: Optional[MentorSummary] = None
    issue_summary: Optional[dict] = None

    class Config:
        from_attributes = True


class AllocationAccept(BaseModel):
    """Mentor accepts the allocation."""
    notes: Optional[str] = Field(default=None, max_length=1000)


class AllocationDecline(BaseModel):
    """Mentor declines the allocation."""
    reason: str = Field(..., max_length=1000)
