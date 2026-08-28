"""Deterministic submission audit service — pure Python, no LLM.

Compares a submission's filled fields against the track's
SubmissionRequirement rows and computes completeness_pct.

This is intentionally a red-team talking point: zero LLM calls,
100% deterministic, auditable logic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission, SubmissionRequirement
from app.models.team import Team
from app.schemas.submission import AuditFieldResult, AuditResult


# Fields that can appear on a Submission model
_SUBMISSION_FIELDS = {"repo_url", "readme_url", "demo_url", "description"}


def _is_present(value) -> bool:
    """Return True if the field value is meaningfully filled (not None, not empty string)."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


async def run_audit(
    submission: Submission,
    db: AsyncSession,
) -> AuditResult:
    """
    Run the deterministic audit against a submission.

    1. Load the team → find the track_id.
    2. Load all SubmissionRequirement rows for that track.
    3. For each required field, check if the submission has it filled.
    4. Compute completeness_pct = (passed required fields) / (total required fields) * 100.
    5. Update submission.completeness_pct and last_audited_at.
    """
    # Load team to get track_id
    result = await db.execute(select(Team).where(Team.id == submission.team_id))
    team = result.scalar_one_or_none()
    if not team or not team.track_id:
        # No track assigned — no requirements, mark 0%
        submission.completeness_pct = 0.0
        submission.last_audited_at = datetime.now(timezone.utc)
        return AuditResult(
            submission_id=submission.id,
            team_id=submission.team_id,
            completeness_pct=0.0,
            total_required=0,
            total_present=0,
            fields=[],
            last_audited_at=submission.last_audited_at,
        )

    # Load requirements for the team's track
    result = await db.execute(
        select(SubmissionRequirement)
        .where(SubmissionRequirement.track_id == team.track_id)
    )
    requirements = result.scalars().all()

    # If no requirements defined, mark 100% (nothing to check)
    if not requirements:
        submission.completeness_pct = 100.0
        submission.last_audited_at = datetime.now(timezone.utc)
        return AuditResult(
            submission_id=submission.id,
            team_id=submission.team_id,
            completeness_pct=100.0,
            total_required=0,
            total_present=0,
            fields=[],
            last_audited_at=submission.last_audited_at,
        )

    # Evaluate each requirement against the submission
    field_results: list[AuditFieldResult] = []
    required_count = 0
    passed_count = 0

    for req in requirements:
        field_name = req.field_name
        required = req.required

        # Check if the submission has this field filled
        if field_name in _SUBMISSION_FIELDS:
            value = getattr(submission, field_name, None)
            present = _is_present(value)
        else:
            # Unknown field — treat as not present
            present = False

        # A field "passes" if it's not required, or if it's required and present
        passed = present if required else True

        field_results.append(
            AuditFieldResult(
                field_name=field_name,
                required=required,
                present=present,
                passed=passed,
            )
        )

        if required:
            required_count += 1
            if passed:
                passed_count += 1

    # Compute completeness percentage
    completeness_pct = (passed_count / required_count * 100) if required_count > 0 else 100.0

    # Persist audit results
    submission.completeness_pct = completeness_pct
    submission.last_audited_at = datetime.now(timezone.utc)

    return AuditResult(
        submission_id=submission.id,
        team_id=submission.team_id,
        completeness_pct=completeness_pct,
        total_required=required_count,
        total_present=passed_count,
        fields=field_results,
        last_audited_at=submission.last_audited_at,
    )
