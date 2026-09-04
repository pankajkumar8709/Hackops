"""Pydantic schemas for Phase 3 — Events, Tracks, ScheduleEvents, SubmissionRequirements."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .mentors import MentorOut
from .resources import ResourceItemOut


# ─── Event ──────────────────────────────────────
class EventCreate(BaseModel):
    name: str
    current_phase: str = "registration"
    timezone: str = "UTC"
    deadline_at: Optional[datetime] = None

class EventUpdate(BaseModel):
    name: Optional[str] = None
    current_phase: Optional[str] = None
    timezone: Optional[str] = None
    deadline_at: Optional[datetime] = None

class EventOut(BaseModel):
    id: uuid.UUID
    name: str
    current_phase: str
    timezone: str
    deadline_at: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True


# ─── Track ──────────────────────────────────────
class TrackCreate(BaseModel):
    name: str
    event_id: uuid.UUID
    eligibility_rules: Optional[str] = None

class TrackOut(BaseModel):
    id: uuid.UUID
    name: str
    event_id: Optional[uuid.UUID]
    eligibility_rules: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True


# ─── ScheduleEvent ──────────────────────────────
class ScheduleEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    event_id: uuid.UUID
    track_scope: Optional[str] = None
    audience_filter: Optional[str] = None

class ScheduleEventOut(BaseModel):
    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    event_id: Optional[uuid.UUID]
    track_scope: Optional[str]
    audience_filter: Optional[str]
    class Config:
        from_attributes = True


# ─── SubmissionRequirement ──────────────────────
class SubmissionRequirementCreate(BaseModel):
    track_id: uuid.UUID
    field_name: str  # e.g. "repo_url", "demo_url", "description"
    required: bool = True

class SubmissionRequirementOut(BaseModel):
    id: uuid.UUID
    track_id: uuid.UUID
    field_name: str
    required: bool
    class Config:
        from_attributes = True


# ─── Event Setup Wizard ─────────────────────────
# One guided request that takes an organizer from "nothing" to a fully
# configured event: event + tracks + submission requirements + optional
# mentors and resource pools. A rules doc can then be uploaded separately.
class WizardTrack(BaseModel):
    name: str
    eligibility_rules: Optional[str] = None
    required_fields: list[str] = []  # e.g. ["repo_url", "demo_url", "description"]

class WizardMentor(BaseModel):
    name: str
    skills: list[str] = []
    availability_status: str = "available"
    discord_handle: Optional[str] = None

class WizardResourcePool(BaseModel):
    name: str
    resource_type: str
    total_quantity: int = Field(ge=1)

class EventWizardRequest(BaseModel):
    name: str
    current_phase: str = "registration"
    timezone: str = "UTC"
    deadline_at: Optional[datetime] = None
    tracks: list[WizardTrack] = []
    mentors: list[WizardMentor] = []
    resource_pools: list[WizardResourcePool] = []

class EventWizardResult(BaseModel):
    event: EventOut
    tracks: list[TrackOut] = []
    requirements: list[SubmissionRequirementOut] = []
    mentors: list["MentorOut"] = []
    resource_pools: list["ResourceItemOut"] = []
