"""Proactive Reminder service -- Phase 9.

Core flow:
  1. Periodic sweep (triggered by APScheduler or manual POST):
     - Find events with deadline_at set and in the future
     - For each event's tracks -> teams -> submissions
     - Check completeness vs. time-to-deadline
  2. If incomplete AND under threshold time remaining:
     - Identify missing required fields
     - Draft a personalized reminder message (keyword-based, fast)
     - Send Notification to all team members
  3. Return sweep results for the dashboard

All core logic is deterministic (pure Python).
LLM is optional (used for enhanced message drafting only).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event, Track
from app.models.team import Team
from app.models.submission import Submission, SubmissionRequirement
from app.models.participant import Participant
from app.models.issue import Notification
from app.schemas.reminders import (
    ReminderTeamResult,
    ReminderSweepResult,
)

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────

# Default: remind teams within 24h of deadline
DEFAULT_THRESHOLD_HOURS = 24.0

# Default: remind if completeness is below 100%
DEFAULT_COMPLETENESS_THRESHOLD = 100.0

# ─── Message Drafting (deterministic, no LLM) ──────────────


def _draft_reminder_message(
    team_name: str,
    completeness_pct: float,
    missing_fields: list[str],
    hours_remaining: Optional[float],
    event_name: str,
) -> str:
    """
    Draft a personalized reminder message naming the exact missing fields.

    This is deterministic -- no LLM call needed. The message is personalized
    with the team name, specific missing fields, and time context.
    """
    field_list = ", ".join(f'"{f}"' for f in missing_fields)

    if hours_remaining is not None and hours_remaining <= 1:
        urgency = "URGENT"
        time_phrase = f"less than 1 hour"
    elif hours_remaining is not None and hours_remaining <= 6:
        urgency = "IMPORTANT"
        time_phrase = f"approximately {hours_remaining:.1f} hours"
    else:
        urgency = "REMINDER"
        time_phrase = f"approximately {hours_remaining:.1f} hours" if hours_remaining else "before the deadline"

    msg = (
        f"[{urgency}] {team_name}, your submission for {event_name} is "
        f"at {completeness_pct:.0f}% completeness. "
        f"Missing required fields: {field_list}. "
        f"Please complete these before {time_phrase} remain."
    )

    return msg


def _draft_llm_enhanced_message(
    team_name: str,
    completeness_pct: float,
    missing_fields: list[str],
    hours_remaining: Optional[float],
    event_name: str,
) -> Optional[str]:
    """
    Try to draft an LLM-enhanced message via Groq API.
    Returns None if the API call fails or times out.
    This is a best-effort enhancement -- never blocks the reminder pipeline.
    """
    try:
        import os
        import httpx

        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return None

        time_desc = (
            f"{hours_remaining:.1f} hours" if hours_remaining else "an unknown amount of time"
        )

        prompt = (
            f"Write a short, encouraging hackathon reminder message for team '{team_name}'. "
            f"Their project '{event_name}' is at {completeness_pct:.0f}% completeness. "
            f"They are missing these required fields: {', '.join(missing_fields)}. "
            f"They have about {time_desc} until the deadline. "
            f"Keep it under 50 words, friendly but urgent. "
            f"Do not include any greeting or sign-off."
        )

        with httpx.Client(timeout=3.0) as client:
            resp = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content and len(content) > 10:
                    return content
    except Exception:
        pass  # Always fall back to deterministic message

    return None


# ─── Core Sweep Logic ──────────────────────────────────────


async def sweep_reminders(
    db: AsyncSession,
    event_id: Optional[uuid.UUID] = None,
    threshold_hours: float = DEFAULT_THRESHOLD_HOURS,
    completeness_threshold: float = DEFAULT_COMPLETENESS_THRESHOLD,
    dry_run: bool = False,
) -> ReminderSweepResult:
    """
    Run the proactive reminder sweep.

    1. Find events with deadlines
    2. For each team in each event's tracks:
       - Load or create submission
       - Run audit to get completeness
       - Check if incomplete AND within threshold
       - Draft personalized message
       - Create Notification for each team member
    3. Return sweep results
    """
    sweep_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc)
    deadline_cutoff = now + timedelta(hours=threshold_hours)

    # Find events with deadlines
    event_query = select(Event).where(Event.deadline_at.isnot(None))
    if event_id:
        event_query = event_query.where(Event.id == event_id)
    else:
        # Only future deadlines
        event_query = event_query.where(Event.deadline_at > now)

    result = await db.execute(event_query)
    events = result.scalars().all()

    teams_checked = 0
    teams_needing = 0
    total_notifications = 0
    team_results: list[ReminderTeamResult] = []

    for event in events:
        # Load tracks for this event
        track_result = await db.execute(
            select(Track).where(Track.event_id == event.id)
        )
        tracks = track_result.scalars().all()

        for track in tracks:
            # Load teams in this track
            team_result = await db.execute(
                select(Team).where(Team.track_id == track.id)
            )
            teams = team_result.scalars().all()

            for team in teams:
                teams_checked += 1

                # Load or find submission
                sub_result = await db.execute(
                    select(Submission).where(Submission.team_id == team.id)
                )
                submission = sub_result.scalar_one_or_none()

                completeness = submission.completeness_pct if submission else 0.0

                # Check if incomplete and within threshold
                hours_remaining = None
                if event.deadline_at:
                    hours_remaining = (event.deadline_at - now).total_seconds() / 3600

                needs_reminder = (
                    completeness < completeness_threshold
                    and hours_remaining is not None
                    and hours_remaining <= threshold_hours
                    and hours_remaining > 0
                )

                if not needs_reminder:
                    continue

                teams_needing += 1

                # Find missing required fields
                missing_fields = await _find_missing_fields(db, team, submission)

                # Draft message
                message = _draft_reminder_message(
                    team_name=team.name,
                    completeness_pct=completeness,
                    missing_fields=missing_fields,
                    hours_remaining=hours_remaining,
                    event_name=event.name,
                )

                # Try LLM enhancement (best-effort, non-blocking)
                llm_message = _draft_llm_enhanced_message(
                    team_name=team.name,
                    completeness_pct=completeness,
                    missing_fields=missing_fields,
                    hours_remaining=hours_remaining,
                    event_name=event.name,
                )
                if llm_message:
                    message = llm_message

                # Create notifications for all team members
                notif_count = 0
                if not dry_run:
                    notif_count = await _send_team_notifications(
                        db=db,
                        team_id=team.id,
                        message=message,
                        trigger_reason=f"submission_deadline_reminder:{sweep_id}",
                        reminder_type="deadline_reminder",
                    )
                total_notifications += notif_count

                team_results.append(
                    ReminderTeamResult(
                        team_id=team.id,
                        team_name=team.name,
                        completeness_pct=completeness,
                        deadline_at=event.deadline_at,
                        hours_remaining=hours_remaining,
                        missing_fields=missing_fields,
                        notifications_sent=notif_count,
                        message_preview=message[:200],
                    )
                )

                logger.info(
                    "Reminder: team=%s completeness=%.0f%% missing=%s notifs=%d",
                    team.name, completeness, missing_fields, notif_count,
                )

    return ReminderSweepResult(
        sweep_id=sweep_id,
        teams_checked=teams_checked,
        teams_needing_reminders=teams_needing,
        total_notifications_sent=total_notifications,
        deadline_at=None,  # could be set for single-event sweeps
        teams=team_results,
        swept_at=now,
    )


async def _find_missing_fields(
    db: AsyncSession,
    team: Team,
    submission: Optional[Submission],
) -> list[str]:
    """Find required fields that are missing from the submission."""
    if not team.track_id:
        return []

    result = await db.execute(
        select(SubmissionRequirement)
        .where(SubmissionRequirement.track_id == team.track_id)
    )
    requirements = result.scalars().all()

    if not requirements:
        return []

    missing = []
    for req in requirements:
        if not req.required:
            continue
        field_name = req.field_name
        if submission:
            value = getattr(submission, field_name, None)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                missing.append(field_name)
        else:
            missing.append(field_name)

    return missing


async def _send_team_notifications(
    db: AsyncSession,
    team_id: uuid.UUID,
    message: str,
    trigger_reason: str,
    reminder_type: str,
) -> int:
    """Create a Notification for every member of the team. Returns count sent."""
    result = await db.execute(
        select(Participant).where(Participant.team_id == team_id)
    )
    members = result.scalars().all()

    count = 0
    for member in members:
        notification = Notification(
            recipient_id=member.id,
            team_id=team_id,
            channel="in_app",
            content=message,
            trigger_reason=trigger_reason,
            reminder_type=reminder_type,
        )
        db.add(notification)
        count += 1

    if count > 0:
        await db.flush()

    return count


# ─── APScheduler Job Wrapper ───────────────────────────────


async def scheduled_reminder_sweep():
    """
    APScheduler job wrapper for the reminder sweep.
    Uses a fresh DB session per invocation.
    """
    from app.database import AsyncSessionLocal

    logger.info("APScheduler: starting reminder sweep")
    async with AsyncSessionLocal() as session:
        try:
            result = await sweep_reminders(session)
            await session.commit()
            logger.info(
                "APScheduler: sweep complete -- checked=%d, need_reminders=%d, sent=%d",
                result.teams_checked,
                result.teams_needing_reminders,
                result.total_notifications_sent,
            )
        except Exception:
            logger.exception("APScheduler: reminder sweep failed")
            await session.rollback()
