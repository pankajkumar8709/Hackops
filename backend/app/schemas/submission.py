"""Pydantic schemas for Phase 5 — Submission Audit Module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


# ─── Submission CRUD ────────────────────────────────────────

class SubmissionCreate(BaseModel):
    """Team submits a project — all fields optional except what the team has."""
    repo_url: Optional[str] = None
    readme_url: Optional[str] = None
    demo_url: Optional[str] = None
    description: Optional[str] = None


class SubmissionUpdate(BaseModel):
    """PATCH — update any subset of submission fields."""
    repo_url: Optional[str] = None
    readme_url: Optional[str] = None
    demo_url: Optional[str] = None
    description: Optional[str] = None


class SubmissionOut(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    repo_url: Optional[str] = None
    readme_url: Optional[str] = None
    demo_url: Optional[str] = None
    description: Optional[str] = None
    completeness_pct: float
    last_audited_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Submission Requirement ────────────────────────────────

class SubmissionRequirementOut(BaseModel):
    id: uuid.UUID
    track_id: uuid.UUID
    field_name: str
    required: bool

    class Config:
        from_attributes = True


# ─── Audit ─────────────────────────────────────────────────

class AuditFieldResult(BaseModel):
    """Pass/fail for a single required field."""
    field_name: str
    required: bool
    present: bool
    passed: bool


class AuditResult(BaseModel):
    """Full audit result for a submission."""
    submission_id: uuid.UUID
    team_id: uuid.UUID
    completeness_pct: float
    total_required: int
    total_present: int
    fields: list[AuditFieldResult]
    last_audited_at: Optional[datetime] = None
