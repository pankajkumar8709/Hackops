"""Pydantic schemas for Phase 2 — Auth & Onboarding."""
from __future__ import annotations
import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr


# ─────────────────────────────────────────────
# Participant
# ─────────────────────────────────────────────

class ParticipantRegister(BaseModel):
    name: str
    email: EmailStr
    skills: list[str] = []
    track_pref: Optional[str] = None
    discord_handle: Optional[str] = None


class ParticipantOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    skills: list[str]
    track_pref: Optional[str]
    discord_handle: Optional[str]
    role: str
    team_id: Optional[uuid.UUID]
    token: str  # plain token returned once at registration

    class Config:
        from_attributes = True


class ParticipantPublic(BaseModel):
    """Safe public view — no token."""
    id: uuid.UUID
    name: str
    email: str
    skills: list[str]
    track_pref: Optional[str]
    discord_handle: Optional[str]
    role: str
    team_id: Optional[uuid.UUID]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Team
# ─────────────────────────────────────────────

class TeamCreate(BaseModel):
    name: str
    track_id: Optional[uuid.UUID] = None


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    track_id: Optional[uuid.UUID]
    submission_status: str
    readiness_pct: float

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

class OrganizerLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
