"""Pydantic schemas for Phase 3 — Documents."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    type: str
    ingested_at: Optional[datetime]
    created_at: datetime
    class Config:
        from_attributes = True
