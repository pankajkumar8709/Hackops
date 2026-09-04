"""Mentor Allocation service -- Phase 7.

Core flow:
  1. Classify issue skills (LLM call via Groq)
  2. Filter available mentors by skill overlap
  3. Rank candidates by overlap count
  4. Create proposed allocation + send Notification to mentor
  5. Handle timeout: re-offer to next-ranked mentor

All LLM usage is limited to skill classification and notification drafting.
Matching/ranking is deterministic (pure Python).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.mentor import Mentor
from app.models.mentor_allocation import MentorAllocation
from app.models.issue import Issue

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────

# Timeout window for mentor response (compressed for hackathon demo)
ALLOCATION_TIMEOUT_MINUTES = 5

# Max re-offer attempts before escalating to organizer
MAX_REOFFER_ATTEMPTS = 3

# ─── Skill classification via LLM ───────────────────────────


def _classify_skills_llm(issue_description: str) -> list[str]:
    """Use Groq LLM to classify which skills are needed for an issue.

    Returns a list of skill keywords (e.g. ["deployment", "docker", "aws"]).
    Falls back to basic keyword matching if LLM fails or times out.
    """
    # Always start with keyword fallback for speed
    fallback = _extract_keywords_fallback(issue_description)

    settings = get_settings()
    try:
        import httpx as _httpx
        import re
        import os

        api_key = settings.groq_api_key
        if not api_key:
            logger.info("No Groq API key, using keyword fallback")
            return fallback

        # Use httpx with timeout for fast failure (5s — LLM is enhancement, not blocker)
        with _httpx.Client(timeout=5.0) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen/qwen3.6-27b",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a skill classifier for a hackathon support system. "
                                "Given an issue description, return a JSON array of 1-5 skill "
                                "keywords that a mentor would need to help with this issue. "
                                "Return ONLY the JSON array, nothing else. "
                                'Example: ["docker", "deployment", "aws"]'
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Issue: {issue_description}",
                        },
                    ],
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
            )

            if response.status_code != 200:
                logger.warning("Groq API returned %d, using keyword fallback", response.status_code)
                return fallback

            data = response.json()
            raw = data["choices"][0]["message"]["content"].strip()

            # Strip <think>...</think> tags (qwen3 model quirk)
            raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()

            # Also try to extract JSON array from the response
            json_match = re.search(r'\[[\s\S]*?\]', raw)
            if json_match:
                raw = json_match.group()

            # Parse JSON array
            skills = json.loads(raw)
            if isinstance(skills, list) and all(isinstance(s, str) for s in skills):
                llm_skills = [s.lower().strip() for s in skills[:5]]
                # Merge LLM skills with fallback for better coverage
                combined = list(dict.fromkeys(llm_skills + fallback))
                return combined[:7]

    except Exception as e:
        logger.warning("LLM skill classification failed, using keyword fallback: %s", e)

    return fallback


def _extract_keywords_fallback(text: str) -> list[str]:
    """Basic keyword extraction fallback when LLM is unavailable."""
    text_lower = text.lower()
    keywords = []

    # Common hackathon skill keywords
    skill_map = {
        "deploy": "deployment",
        "docker": "docker",
        "kubernetes": "kubernetes",
        "k8s": "kubernetes",
        "aws": "aws",
        "gcp": "gcp",
        "azure": "azure",
        "database": "database",
        "sql": "sql",
        "api": "api",
        "frontend": "frontend",
        "backend": "backend",
        "ml": "machine-learning",
        "machine learning": "machine-learning",
        "ai": "machine-learning",
        "deep learning": "deep-learning",
        "git": "git",
        "github": "git",
        "ci/cd": "ci-cd",
        "testing": "testing",
        "bug": "debugging",
        "error": "debugging",
        "performance": "performance",
        "security": "security",
        "authentication": "authentication",
        "auth": "authentication",
        "ui": "frontend",
        "ux": "frontend",
        "css": "frontend",
        "javascript": "javascript",
        "python": "python",
        "react": "react",
        "node": "nodejs",
        "nodejs": "nodejs",
        "java": "java",
        "rust": "rust",
        "go": "golang",
    }

    for trigger, skill in skill_map.items():
        if trigger in text_lower and skill not in keywords:
            keywords.append(skill)

    return keywords[:5] if keywords else ["general"]


# ─── Mentor matching & ranking ──────────────────────────────


async def find_mentor_candidates(
    db: AsyncSession,
    skills: list[str],
) -> list[Mentor]:
    """Find available mentors whose skills overlap with the issue's needed skills.

    Returns mentors sorted by skill overlap count (descending).
    Only includes mentors with availability_status = 'available'.
    """
    # Load all available mentors with their current allocations
    result = await db.execute(
        select(Mentor)
        .options(selectinload(Mentor.allocations))
        .where(Mentor.availability_status == "available")
        .order_by(Mentor.name)
    )
    mentors = result.scalars().unique().all()

    # Score each mentor by skill overlap
    scored = []
    skills_lower = [s.lower() for s in skills]

    for mentor in mentors:
        mentor_skills_lower = [s.lower() for s in (mentor.skills or [])]
        overlap = len(set(skills_lower) & set(mentor_skills_lower))
        if overlap > 0:
            scored.append((mentor, overlap))

    # Sort by overlap count descending, then by name for stability
    scored.sort(key=lambda x: (-x[1], x[0].name))

    return [mentor for mentor, _ in scored]


async def get_next_mentor_for_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
    skip_mentor_ids: list[uuid.UUID],
) -> Optional[Mentor]:
    """Find the next best mentor for an issue, excluding already-tried mentors.

    Used for timeout re-offer flow.
    """
    # Get the issue to re-classify
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if not issue:
        return None

    # Re-classify skills
    skills = _classify_skills_llm(issue.description)

    # Find all available mentors (excluding already tried)
    result = await db.execute(
        select(Mentor)
        .options(selectinload(Mentor.allocations))
        .where(
            Mentor.availability_status == "available",
            ~Mentor.id.in_(skip_mentor_ids) if skip_mentor_ids else True,
        )
    )
    mentors = result.scalars().unique().all()

    # Score and rank
    skills_lower = [s.lower() for s in skills]
    scored = []
    for mentor in mentors:
        mentor_skills_lower = [s.lower() for s in (mentor.skills or [])]
        overlap = len(set(skills_lower) & set(mentor_skills_lower))
        scored.append((mentor, overlap))

    scored.sort(key=lambda x: (-x[1], x[0].name))

    # Return first with overlap > 0, or first overall if none match
    for mentor, overlap in scored:
        if overlap > 0:
            return mentor

    return scored[0][0] if scored else None


# ─── Allocation creation ────────────────────────────────────


async def propose_mentor_allocation(
    db: AsyncSession,
    issue: Issue,
    mentor: Mentor,
    classified_skills: list[str],
    reasoning: Optional[str] = None,
) -> MentorAllocation:
    """Create a proposed allocation and send a notification to the mentor.

    Returns the created MentorAllocation.
    """
    # Build reasoning if not provided
    if reasoning is None:
        mentor_skills = set(s.lower() for s in (mentor.skills or []))
        overlap = set(s.lower() for s in classified_skills) & mentor_skills
        reasoning = (
            f"Matched based on skills: {', '.join(sorted(overlap))}. "
            f"Needed: {', '.join(classified_skills)}. "
            f"Mentor has: {', '.join(mentor.skills or [])}."
        )

    # Create the allocation
    allocation = MentorAllocation(
        mentor_id=mentor.id,
        issue_id=issue.id,
        status="proposed",
        reasoning=reasoning,
    )
    db.add(allocation)
    await db.flush()

    # Enrich reasoning with team info if available
    if issue.team_id:
        from app.models.team import Team
        team_result = await db.execute(select(Team).where(Team.id == issue.team_id))
        team = team_result.scalar_one_or_none()
        if team:
            allocation.reasoning = f"Team '{team.name}' needs help: {reasoning}"

    # Notification is stored in the allocation reasoning field.
    # Full notification delivery (Discord DM) will be wired in Phase 12.
    # For now, mentors view pending allocations via GET /mentor-allocations/mine.

    logger.info(
        "Proposed allocation %s: mentor=%s issue=%s skills=%s",
        allocation.id, mentor.name, issue.id, classified_skills,
    )

    return allocation


# ─── Timeout handling ───────────────────────────────────────


async def check_and_handle_timeouts(db: AsyncSession) -> list[MentorAllocation]:
    """Check for timed-out allocations and re-offer to next mentor.

    Called periodically (by APScheduler in Phase 9, or on-demand).
    Returns list of re-offered allocations.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ALLOCATION_TIMEOUT_MINUTES)

    # Find proposed allocations older than timeout window
    result = await db.execute(
        select(MentorAllocation)
        .options(
            selectinload(MentorAllocation.mentor),
            selectinload(MentorAllocation.issue),
        )
        .where(
            MentorAllocation.status == "proposed",
            MentorAllocation.proposed_at < cutoff,
            MentorAllocation.reoffer_count < MAX_REOFFER_ATTEMPTS,
        )
    )
    timed_out = result.scalars().unique().all()

    reoffered = []
    for allocation in timed_out:
        # Mark as timed out
        allocation.status = "timed_out"
        allocation.timed_out_at = datetime.now(timezone.utc)

        # Find next mentor (skip this one and any previously tried)
        skip_ids = [allocation.mentor_id]
        # Check if there were previous attempts for this issue
        prev_result = await db.execute(
            select(MentorAllocation)
            .where(MentorAllocation.issue_id == allocation.issue_id)
        )
        prev_allocations = prev_result.scalars().all()
        skip_ids.extend(a.mentor_id for a in prev_allocations)

        next_mentor = await get_next_mentor_for_issue(
            db, allocation.issue_id, skip_ids
        )

        if next_mentor:
            # Re-offer to next mentor
            classified_skills = _classify_skills_llm(
                allocation.issue.description
            )
            new_allocation = await propose_mentor_allocation(
                db, allocation.issue, next_mentor, classified_skills,
                reasoning=(
                    f"Re-offered after timeout from mentor "
                    f"'{allocation.mentor.name}'. Original proposed at "
                    f"{allocation.proposed_at.isoformat()}."
                ),
            )
            new_allocation.reoffer_count = allocation.reoffer_count + 1
            reoffered.append(new_allocation)
        else:
            # No more mentors available -- escalate to organizer
            logger.warning(
                "No mentors available for issue %s after timeout. "
                "Creating resourcing-gap escalation.",
                allocation.issue_id,
            )
            # Update issue to signal no mentor found
            allocation.reasoning = (
                allocation.reasoning or ""
            ) + " No more mentors available -- needs organizer attention."

        await db.flush()

    return reoffered
