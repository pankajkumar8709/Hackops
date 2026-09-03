"""Pydantic schemas for Phase 10 -- Team Formation & Matchmaking.

Covers capability-gap analysis, candidate matching, and suggestion ranking.
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel


# ─── Skill Gap Analysis ──────────────────────────────────


class SkillGapAnalysis(BaseModel):
    """Describes the gap between a team's current skills and what the track needs."""
    team_id: uuid.UUID
    team_name: str
    team_skills: list[str] = []
    track_needed_skills: list[str] = []
    missing_skills: list[str] = []
    member_count: int = 0


# ─── Match Candidate ──────────────────────────────────────


class MatchCandidate(BaseModel):
    """A single unassigned participant ranked as a match for the team."""
    participant_id: uuid.UUID
    name: str
    email: str
    skills: list[str] = []
    track_pref: Optional[str] = None
    discord_handle: Optional[str] = None

    # Match scoring
    matching_skills: list[str] = []
    match_score: float = 0.0
    reasoning: str = ""

    class Config:
        from_attributes = True


# ─── Match Suggestions Response ───────────────────────────


class MatchSuggestionsResponse(BaseModel):
    """Full response for GET /teams/{id}/match-suggestions."""
    team_id: uuid.UUID
    team_name: str
    gap_analysis: SkillGapAnalysis
    candidates: list[MatchCandidate] = []
    total_candidates: int = 0
    message: str = ""
