"""Pydantic schemas for Phase 3 — Mentors."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MentorCreate(BaseModel):
    name: str
    skills: list[str] = []
    availability_status: str = "available"
    discord_handle: Optional[str] = None

class MentorUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[list[str]] = None
    availability_status: Optional[str] = None
    discord_handle: Optional[str] = None

class MentorOut(BaseModel):
    id: uuid.UUID
    name: str
    skills: list[str]
    availability_status: str
    discord_handle: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True
