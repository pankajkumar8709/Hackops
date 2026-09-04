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
    ingestion_status: str = "processing"
    chunk_count: int = 0
    error: Optional[str] = None
    ingested_at: Optional[datetime]
    created_at: datetime
    class Config:
        from_attributes = True