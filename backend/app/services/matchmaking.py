"""Team Formation & Matchmaking service -- Phase 10.

Core flow:
  1. Load team -> gather aggregate skills from all members
  2. Load track -> extract commonly-needed skills from eligibility_rules
  3. Identify the capability gap (needed skills NOT in team)
  4. Find unassigned participants (team_id IS NULL)
  5. Score each candidate by how many gap skills they fill
  6. Rank by match_score descending, generate one-line reasoning

All logic is deterministic (pure Python) -- no LLM calls.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team
from app.models.participant import Participant
from app.models.event import Track
from app.schemas.matchmaking import (
    SkillGapAnalysis,
    MatchCandidate,
    MatchSuggestionsResponse,
)

logger = logging.getLogger(__name__)

# ─── Common hackathon skills (fallback when track has no eligibility_rules) ───

_DEFAULT_HACKATHON_SKILLS = {
    "python", "javascript", "typescript", "react", "node",
    "html", "css", "sql", "postgresql", "mongodb",
    "machine learning", "ml", "deep learning", "nlp", "computer vision",
    "data science", "data analysis", "pandas", "numpy",
    "docker", "kubernetes", "aws", "gcp", "azure",
    "api", "rest", "graphql", "fastapi", "flask", "django",
    "mobile", "ios", "android", "flutter",
    "figma", "ui", "ux", "design",
    "git", "github", "devops", "ci/cd",
    "blockchain", "web3", "solidity",
    "security", "penetration testing",
    "iot", "embedded", "raspberry pi",
    "ar", "vr", "unity",
    "presentation", "pitch", "demo",
}

# ─── Skill Extraction ────────────────────────────────────


def _extract_skills_from_rules(eligibility_rules: Optional[str]) -> list[str]:
    """
    Extract commonly-needed skills from a track's eligibility_rules text.
    Uses word-boundary regex matching against a known skill vocabulary.
    """
    if not eligibility_rules:
        return list(_DEFAULT_HACKATHON_SKILLS)

    text = eligibility_rules.lower()
    found = set()

    for skill in _DEFAULT_HACKATHON_SKILLS:
        # Use word-boundary regex to avoid substring false positives
        # e.g. 'ar' should not match inside 'preparation' or 'data'
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text):
            found.add(skill)

    # If very few matches, fall back to full default set
    if len(found) < 3:
        return list(_DEFAULT_HACKATHON_SKILLS)

    return list(found)


def _normalize_skill(skill: str) -> str:
    """Normalize a skill string for comparison."""
    return skill.strip().lower()


# ─── Gap Analysis ─────────────────────────────────────────


def _compute_team_skills(members: list[Participant]) -> list[str]:
    """Gather unique skills from all team members."""
    all_skills = set()
    for member in members:
        if member.skills:
            for s in member.skills:
                all_skills.add(_normalize_skill(s))
    return sorted(all_skills)


def _compute_gap(team_skills: list[str], track_skills: list[str]) -> list[str]:
    """Find skills the track needs that the team doesn't have."""
    team_set = set(_normalize_skill(s) for s in team_skills)
    track_set = set(_normalize_skill(s) for s in track_skills)
    return sorted(track_set - team_set)


# ─── Candidate Scoring ────────────────────────────────────


def _score_candidate(
    candidate: Participant,
    missing_skills: list[str],
    team_skills: list[str],
) -> tuple[float, list[str], str]:
    """
    Score a candidate by how many gap skills they fill.

    Returns (score, matching_skills, reasoning).
    Score is 0.0 - 1.0 based on percentage of gap filled.
    """
    candidate_skills = set(_normalize_skill(s) for s in (candidate.skills or []))
    missing_set = set(_normalize_skill(s) for s in missing_skills)
    team_set = set(_normalize_skill(s) for s in team_skills)

    matching = sorted(missing_set & candidate_skills)
    # Also count bonus skills (skills that complement existing team skills)
    bonus = sorted(candidate_skills - team_set - missing_set)

    if not missing_set:
        # No gap to fill -- score based on how many new skills they bring
        if bonus:
            score = min(len(bonus) * 0.1, 0.5)
            reasoning = f"Brings {len(bonus)} new skill(s): {', '.join(bonus[:3])}"
        else:
            score = 0.1
            reasoning = "No new skills to add, but could join for collaboration"
    else:
        # Score = fraction of gap filled
        score = len(matching) / len(missing_set) if missing_set else 0.0

        # Bonus for extra complementary skills
        score += min(len(bonus) * 0.05, 0.2)
        score = min(score, 1.0)

        if matching:
            reasoning = (
                f"Fills {len(matching)}/{len(missing_set)} skill gaps: "
                f"{', '.join(matching[:4])}"
            )
            if bonus:
                reasoning += f". Also brings: {', '.join(bonus[:2])}"
        else:
            reasoning = (
                f"Does not directly fill gaps ({', '.join(missing_skills[:3])}), "
                f"but has complementary skills: {', '.join(list(candidate_skills)[:3])}"
            )

    return round(score, 3), matching, reasoning


# ─── Main Entry Point ─────────────────────────────────────


async def get_match_suggestions(
    db: AsyncSession,
    team_id: uuid.UUID,
) -> MatchSuggestionsResponse:
    """
    Get ranked match suggestions for a team.

    1. Load team and members
    2. Compute aggregate team skills
    3. Load track and extract needed skills
    4. Find gap
    5. Find unassigned participants
    6. Score and rank candidates
    7. Return suggestions with reasoning
    """
    # Load team
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise ValueError(f"Team {team_id} not found")

    # Load team members
    member_result = await db.execute(
        select(Participant).where(Participant.team_id == team_id)
    )
    members = member_result.scalars().all()

    # Compute team's aggregate skills
    team_skills = _compute_team_skills(members)

    # Load track and extract needed skills
    track_skills = []
    if team.track_id:
        track_result = await db.execute(
            select(Track).where(Track.id == team.track_id)
        )
        track = track_result.scalar_one_or_none()
        if track:
            track_skills = _extract_skills_from_rules(track.eligibility_rules)

    # Compute gap
    missing_skills = _compute_gap(team_skills, track_skills)

    # Build gap analysis
    gap_analysis = SkillGapAnalysis(
        team_id=team.id,
        team_name=team.name,
        team_skills=team_skills,
        track_needed_skills=track_skills,
        missing_skills=missing_skills,
        member_count=len(members),
    )

    # Find unassigned participants
    unassigned_result = await db.execute(
        select(Participant).where(
            Participant.team_id.is_(None),
            Participant.role == "participant",
        )
    )
    unassigned = unassigned_result.scalars().all()

    # Score and rank candidates
    candidates: list[MatchCandidate] = []
    for p in unassigned:
        score, matching, reasoning = _score_candidate(p, missing_skills, team_skills)
        candidates.append(
            MatchCandidate(
                participant_id=p.id,
                name=p.name,
                email=p.email,
                skills=p.skills or [],
                track_pref=p.track_pref,
                discord_handle=p.discord_handle,
                matching_skills=matching,
                match_score=score,
                reasoning=reasoning,
            )
        )

    # Sort by match_score descending
    candidates.sort(key=lambda c: c.match_score, reverse=True)

    # Generate overall message
    if not missing_skills:
        message = "Team has full skill coverage. No gaps identified."
    elif not candidates:
        message = (
            f"Team is missing {len(missing_skills)} skill(s) "
            f"({', '.join(missing_skills[:3])}) but no unassigned participants "
            f"are currently available."
        )
    else:
        top = candidates[0]
        message = (
            f"Found {len(candidates)} candidate(s). "
            f"Best match: {top.name} ({top.match_score:.0%} match) — "
            f"{top.reasoning}"
        )

    return MatchSuggestionsResponse(
        team_id=team.id,
        team_name=team.name,
        gap_analysis=gap_analysis,
        candidates=candidates,
        total_candidates=len(candidates),
        message=message,
    )
