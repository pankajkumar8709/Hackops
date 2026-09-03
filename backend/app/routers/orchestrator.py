"""Orchestrator router -- Phase 11: Agent Orchestrator (The Closed Loop).

Endpoints:
  POST   /orchestrator/run        -- run a single orchestrator loop instance
  POST   /orchestrator/sweep      -- run full sweep (all teams + issues)
  GET    /orchestrator/actions     -- view agent action log (explainability feed)
  GET    /orchestrator/status      -- orchestrator health and config
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_organizer
from app.models.agent_action import AgentAction
from app.schemas.orchestrator import (
    OrchestratorRunRequest,
    OrchestratorRunResult,
    OrchestratorSweepResult,
    AgentActionOut,
)
from app.services.orchestrator import (
    run_orchestrator,
    run_full_sweep,
    TriggerType,
    ALLOWED_ACTIONS,
    RESTRICTED_ACTIONS,
)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ─── Run single orchestrator instance ──────────────────────


@router.post(
    "/run",
    response_model=OrchestratorRunResult,
    status_code=status.HTTP_200_OK,
)
async def execute_orchestrator(
    body: OrchestratorRunRequest,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Run a single orchestrator loop instance.

    Trigger types:
    - submission_audit: context = {"team_id": "..."}
    - mentor_allocation: context = {"issue_id": "..."}
    - resource_allocation: context = {"resource_item_id": "...", "team_id": "..."}
    """
    # Validate trigger type
    valid_types = [t.value for t in TriggerType]
    if body.trigger_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid trigger_type '{body.trigger_type}'. "
            f"Must be one of: {valid_types}",
        )

    # Validate required context fields
    if body.trigger_type == "submission_audit" and "team_id" not in body.context:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="submission_audit requires 'team_id' in context",
        )
    if body.trigger_type == "mentor_allocation" and "issue_id" not in body.context:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="mentor_allocation requires 'issue_id' in context",
        )
    if body.trigger_type == "resource_allocation":
        if "resource_item_id" not in body.context or "team_id" not in body.context:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="resource_allocation requires both 'resource_item_id' and 'team_id' in context",
            )

    result = await run_orchestrator(db, body.trigger_type, body.context)
    await db.commit()

    return result


# ─── Full sweep ────────────────────────────────────────────


@router.post(
    "/sweep",
    response_model=OrchestratorSweepResult,
    status_code=status.HTTP_200_OK,
)
async def execute_sweep(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Run a full orchestrator sweep across all teams and open issues.

    This is what APScheduler would call periodically.
    """
    result = await run_full_sweep(db)
    await db.commit()

    return result


# ─── Action log (explainability feed) ──────────────────────


@router.get(
    "/actions",
    response_model=list[AgentActionOut],
)
async def list_actions(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    action_type: Optional[str] = Query(
        default=None,
        description="Filter by action_type",
    ),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    View the agent action log (explainability feed).

    Shows all autonomous actions taken by the orchestrator,
    with trigger snapshots, reasoning, policy checks, and outcomes.
    """
    query = (
        select(AgentAction)
        .order_by(AgentAction.executed_at.desc())
        .limit(limit)
    )

    if action_type:
        query = query.where(AgentAction.action_type == action_type)

    result = await db.execute(query)
    actions = result.scalars().all()

    return actions


# ─── Orchestrator status ───────────────────────────────────


@router.get(
    "/status",
)
async def orchestrator_status(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Orchestrator health check and configuration info."""
    # Count recent actions
    result = await db.execute(select(AgentAction))
    total_actions = len(result.scalars().all())

    return {
        "status": "operational",
        "version": "1.0.0",
        "trigger_types": [t.value for t in TriggerType],
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "restricted_actions": sorted(RESTRICTED_ACTIONS),
        "total_actions_logged": total_actions,
    }
