"""Pydantic schemas for Phase 8 -- Resource Allocation & Tracking.

Covers resource requests, allocation responses, return tracking, and overdue detection.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Resource Request ───────────────────────────────────────


class ResourceRequestCreate(BaseModel):
    """Request a resource allocation for the requesting team.

    resource_item_id: which resource pool to draw from.
    team_id is auto-populated from the participant's token.
    """
    resource_item_id: uuid.UUID


class ResourceAllocationOut(BaseModel):
    """Full allocation response with resource item and team details."""
    id: uuid.UUID
    resource_item_id: uuid.UUID
    team_id: uuid.UUID
    status: str
    allocated_at: datetime
    returned_at: Optional[datetime] = None
    overdue: bool = False

    # Nested summaries
    resource_item: Optional[dict] = None
    team: Optional[dict] = None

    class Config:
        from_attributes = True


class ResourceReturn(BaseModel):
    """Mark a resource allocation as returned."""
    notes: Optional[str] = Field(default=None, max_length=1000)


class ResourcePoolSummary(BaseModel):
    """Summary of a resource item's current stock for the organizer dashboard."""
    id: uuid.UUID
    name: str
    resource_type: str
    total_quantity: int
    available_quantity: int
    allocated_count: int
    overdue_count: int

    class Config:
        from_attributes = True
