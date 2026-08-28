"""Pydantic schemas for Phase 3 — Resource Items."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ResourceItemCreate(BaseModel):
    name: str
    resource_type: str  # e.g. "api_key", "hardware_kit"
    total_quantity: int
    available_quantity: int | None = None  # defaults to total_quantity

class ResourceItemOut(BaseModel):
    id: uuid.UUID
    name: str
    resource_type: str
    total_quantity: int
    available_quantity: int
    created_at: datetime
    class Config:
        from_attributes = True
