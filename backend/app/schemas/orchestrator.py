"""Pydantic schemas for Phase 11 -- Agent Orchestrator.

Covers orchestrator run requests, results, and action logs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Orchestrator Run ──────────────────────────────────────


class OrchestratorRunRequest(BaseModel):
    """Request to run the orchestrator for a specific trigger."""
    trigger_type: str = Field(
        ...,
        description="One of: submission_audit, mentor_allocation, resource_allocation",
    )
    context: dict = Field(
        default_factory=dict,
        description="Trigger-specific context. "
        "For submission_audit: {'team_id': '...'} "
        "For mentor_allocation: {'issue_id': '...'} "
        "For resource_allocation: {'resource_item_id': '...', 'team_id': '...'}",
    )


class OrchestratorStepResult(BaseModel):
    """Result of a single orchestrator step."""
    step: str
    data: dict = {}


class OrchestratorRunResult(BaseModel):
    """Full result of an orchestrator run."""
    run_id: str
    trigger_type: str
    timestamp: str
    observe: dict = {}
    decide: dict = {}
    policy: dict = {}
    act: dict = {}
    verify: dict = {}
    logged: bool = False
    error: Optional[str] = None


# ─── Action Log ────────────────────────────────────────────


class AgentActionOut(BaseModel):
    """A single agent action from the explainability log."""
    id: uuid.UUID
    action_type: str
    summary: Optional[str] = None
    trigger_state_snapshot: Optional[str] = None
    reasoning_trace: Optional[str] = None
    policy_check_result: Optional[str] = None
    outcome: Optional[str] = None
    issue_id: Optional[uuid.UUID] = None
    notification_id: Optional[uuid.UUID] = None
    submission_id: Optional[uuid.UUID] = None
    escalation_id: Optional[uuid.UUID] = None
    executed_at: datetime

    class Config:
        from_attributes = True


# ─── Sweep ─────────────────────────────────────────────────


class OrchestratorSweepResult(BaseModel):
    """Result of a full orchestrator sweep across all teams/issues."""
    sweep_id: str
    total_runs: int
    verified_runs: int = 0
    failed_verifications: int = 0
    results: list[OrchestratorRunResult] = []
