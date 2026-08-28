"""Pydantic schemas for Phase 4 — Knowledge Engine (RAG)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ─── Document ────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    type: str
    ingested_at: Optional[datetime] = None
    created_at: datetime
    chunk_count: int = 0

    class Config:
        from_attributes = True


# ─── Q&A ─────────────────────────────────────────────────────

class QARequest(BaseModel):
    question: str
    participant_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None


class CitationOut(BaseModel):
    source_doc: str
    chunk_text: str
    similarity_score: float


class QAResponse(BaseModel):
    answer: str
    citations: list[CitationOut] = []
    confident: bool
    issue_id: Optional[uuid.UUID] = None


# ─── Track ──────────────────────────────────────────────────

class TrackOut(BaseModel):
    id: uuid.UUID
    name: str
    eligibility_rules: Optional[str] = None
    event_id: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True
