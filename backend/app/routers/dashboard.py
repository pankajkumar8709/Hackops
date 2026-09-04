"""Dashboard router -- Phase 13: Organizer Dashboard.

Endpoints:
  GET  /dashboard/health          -- aggregated health metrics for the dashboard
  WS   /dashboard/ws              -- WebSocket for live dashboard updates
  POST /dashboard/broadcast       -- broadcast message to all participants
  PATCH /teams/{id}/override      -- manual override for team record
  PATCH /submissions/{id}/override -- manual override for submission record
  GET  /dashboard/export          -- export submissions as CSV
  GET  /dashboard/approval-queue  -- approval queue for agent-proposed actions
"""
from __future__ import annotations

import csv
import io
import json
import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_organizer, decode_jwt
from app.models.team import Team
from app.models.participant import Participant
from app.models.submission import Submission
from app.models.escalation import Escalation
from app.models.issue import Issue
from app.models.issue import Notification
from app.models.agent_action import AgentAction
from app.models.mentor import Mentor
from app.models.mentor_allocation import MentorAllocation
from app.models.resource import ResourceItem, ResourceAllocation
from app.schemas.dashboard import (
    DashboardHealth,
    TeamHealthSummary,
    MentorLoadSummary,
    ResourcePoolSummary,
    ApprovalItem,
    ApprovalQueue,
    BroadcastRequest,
    BroadcastResult,
    TeamOverride,
    SubmissionOverride,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ─── WebSocket connection manager ────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for live dashboard updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


# ─── Health aggregation endpoint ─────────────────────────

@router.get("/health", response_model=DashboardHealth)
async def dashboard_health(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregated health metrics for the organizer dashboard.
    Returns team readiness, escalation count, mentor load, resource pool levels.
    """
    from sqlalchemy import text

    # Bulk: team member counts
    member_rows = await db.execute(
        select(Participant.team_id, func.count().label("cnt"))
        .where(Participant.team_id.is_not(None))
        .group_by(Participant.team_id)
    )
    member_map = {row[0]: row[1] for row in member_rows.all()}

    # Bulk: team open issue counts
    issue_rows = await db.execute(
        select(Issue.team_id, func.count().label("cnt"))
        .where(Issue.status != "resolved", Issue.team_id.is_not(None))
        .group_by(Issue.team_id)
    )
    issue_map = {row[0]: row[1] for row in issue_rows.all()}

    # Teams
    teams_result = await db.execute(select(Team).order_by(Team.name))
    teams = teams_result.scalars().all()

    team_summaries = []
    for team in teams:
        team_summaries.append(TeamHealthSummary(
            id=team.id,
            name=team.name,
            submission_status=team.submission_status,
            readiness_pct=team.readiness_pct,
            member_count=member_map.get(team.id, 0),
            open_issues=issue_map.get(team.id, 0),
        ))

    teams_ready = sum(1 for t in team_summaries if t.readiness_pct >= 100.0)
    avg_readiness = (
        sum(t.readiness_pct for t in team_summaries) / len(team_summaries)
        if team_summaries else 0.0
    )

    # Bulk counts (single queries)
    total_participants = (await db.execute(select(func.count()).select_from(Participant))).scalar() or 0
    open_escalations = (await db.execute(select(func.count()).where(Escalation.status == "open"))).scalar() or 0
    total_issues = (await db.execute(select(func.count()).select_from(Issue))).scalar() or 0
    total_notifications = (await db.execute(select(func.count()).select_from(Notification))).scalar() or 0
    total_agent_actions = (await db.execute(select(func.count()).select_from(AgentAction))).scalar() or 0
    total_submissions = (await db.execute(select(func.count()).select_from(Submission))).scalar() or 0

    # Bulk: mentor active allocation counts
    mentor_alloc_rows = await db.execute(
        select(MentorAllocation.mentor_id, func.count().label("cnt"))
        .where(MentorAllocation.status == "proposed")
        .group_by(MentorAllocation.mentor_id)
    )
    mentor_alloc_map = {row[0]: row[1] for row in mentor_alloc_rows.all()}

    mentors_result = await db.execute(select(Mentor))
    mentors = mentors_result.scalars().all()
    mentor_summaries = [
        MentorLoadSummary(
            id=m.id,
            name=m.name,
            availability_status=m.availability_status,
            active_allocations=mentor_alloc_map.get(m.id, 0),
            skills=m.skills or [],
        ) for m in mentors
    ]

    # Bulk: resource pool allocated counts
    pool_alloc_rows = await db.execute(
        select(ResourceAllocation.resource_item_id, func.count().label("cnt"))
        .where(ResourceAllocation.status == "allocated")
        .group_by(ResourceAllocation.resource_item_id)
    )
    pool_alloc_map = {row[0]: row[1] for row in pool_alloc_rows.all()}

    pools_result = await db.execute(select(ResourceItem))
    pools = pools_result.scalars().all()
    pool_summaries = [
        ResourcePoolSummary(
            id=p.id,
            name=p.name,
            resource_type=p.resource_type,
            total_quantity=p.total_quantity,
            available_quantity=p.available_quantity,
            allocated_count=pool_alloc_map.get(p.id, 0),
        ) for p in pools
    ]

    return DashboardHealth(
        total_teams=len(team_summaries),
        teams_ready=teams_ready,
        avg_readiness_pct=round(avg_readiness, 1),
        total_participants=total_participants,
        open_escalations=open_escalations,
        total_issues=total_issues,
        total_notifications=total_notifications,
        total_agent_actions=total_agent_actions,
        total_submissions=total_submissions,
        teams=team_summaries,
        mentors=mentor_summaries,
        resource_pools=pool_summaries,
    )


# ─── Approval queue ──────────────────────────────────────

@router.get("/approval-queue", response_model=ApprovalQueue)
async def get_approval_queue(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Approval queue: agent-proposed actions that need human confirmation.
    Includes proposed mentor allocations and policy-gated actions.
    """
    items: list[ApprovalItem] = []

    # Proposed mentor allocations
    alloc_result = await db.execute(
        select(MentorAllocation)
        .where(MentorAllocation.status == "proposed")
        .order_by(MentorAllocation.proposed_at.desc())
    )
    allocations = alloc_result.scalars().all()

    for alloc in allocations:
        # Load related entities for description
        mentor = (await db.execute(
            select(Mentor).where(Mentor.id == alloc.mentor_id)
        )).scalar_one_or_none()
        issue = (await db.execute(
            select(Issue).where(Issue.id == alloc.issue_id)
        )).scalar_one_or_none()

        mentor_name = mentor.name if mentor else "Unknown"
        issue_desc = issue.description[:80] if issue else "Unknown issue"

        items.append(ApprovalItem(
            id=alloc.id,
            action_type="propose_mentor",
            description=f"Mentor allocation: {mentor_name} → {issue_desc}",
            reasoning=alloc.reasoning,
            status="pending",
            entity_type="mentor_allocation",
            entity_id=alloc.id,
            created_at=alloc.proposed_at,
        ))

    # Low-stock resource alerts (available == 0)
    pool_result = await db.execute(
        select(ResourceItem).where(ResourceItem.available_quantity == 0)
    )
    low_pools = pool_result.scalars().all()
    for pool in low_pools:
        items.append(ApprovalItem(
            id=pool.id,
            action_type="resource_low_stock",
            description=f"Resource pool '{pool.name}' is out of stock ({pool.resource_type})",
            reasoning=f"available_quantity=0, total={pool.total_quantity}",
            status="pending",
            entity_type="resource_item",
            entity_id=pool.id,
            created_at=pool.created_at,
        ))

    # Sort by created_at descending
    items.sort(key=lambda x: x.created_at, reverse=True)

    return ApprovalQueue(
        items=items,
        total_pending=len(items),
    )


# ─── Approval queue actions (approve / reject) ─────────────

async def _log_approval_action(
    db: AsyncSession,
    decision: str,  # "approve" | "reject"
    entity_type: str,
    entity_id: uuid.UUID,
    description: str,
    note: str | None,
):
    """Write an AgentAction row recording an organizer's approval decision."""
    from app.services.orchestrator import _log_action, build_action_summary

    action_type = "approve_action" if decision == "approve" else "reject_action"
    reasoning = f"Organizer {decision}d: {description}"
    if note:
        reasoning += f" — {note}"

    kwargs = {}
    if entity_type == "mentor_allocation":
        alloc = (await db.execute(
            select(MentorAllocation).where(MentorAllocation.id == entity_id)
        )).scalar_one_or_none()
        if alloc:
            kwargs["issue_id"] = alloc.issue_id

    summary = build_action_summary(
        action_type, {"issue_id": str(entity_id)}, reasoning, reasoning
    )
    await _log_action(
        db=db,
        action_type=action_type,
        trigger_snapshot={"entity_type": entity_type, "entity_id": str(entity_id)},
        reasoning=reasoning,
        policy_result="HUMAN_APPROVAL",
        outcome=reasoning,
        summary=summary,
        **kwargs,
    )


@router.patch("/approval-queue/{item_id}/approve")
async def approve_queue_item(
    item_id: uuid.UUID,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    note: str | None = Query(default=None),
):
    """
    Approve an item in the queue, executing the proposed action.

    - mentor_allocation: the proposed mentor is accepted for the issue.
    - resource_low_stock: restock is authorized (logged for audit).

    The decision is written to the AgentAction explainability log.
    """
    # Try mentor allocation first (ids are unique UUIDs)
    alloc = (await db.execute(
        select(MentorAllocation).where(MentorAllocation.id == item_id)
    )).scalar_one_or_none()

    if alloc:
        if alloc.status != "proposed":
            raise HTTPException(status_code=409, detail=f"Allocation already {alloc.status}")
        mentor = (await db.execute(
            select(Mentor).where(Mentor.id == alloc.mentor_id)
        )).scalar_one_or_none()
        issue = (await db.execute(
            select(Issue).where(Issue.id == alloc.issue_id)
        )).scalar_one_or_none()
        desc = f"mentor {mentor.name if mentor else '?'} for issue {str(alloc.issue_id)[:8]}"

        alloc.status = "accepted"
        alloc.responded_at = datetime.now(timezone.utc)

        # Notify the team that raised the issue
        if issue and issue.team_id:
            members = (await db.execute(
                select(Participant).where(Participant.team_id == issue.team_id)
            )).scalars().all()
            for m in members:
                db.add(Notification(
                    recipient_id=m.id,
                    team_id=issue.team_id,
                    channel="in_app",
                    content=f"Your mentor request was approved — {mentor.name if mentor else 'a mentor'} has been assigned to your issue.",
                    trigger_reason="organizer_approval:mentor",
                    reminder_type="mentor_assigned",
                ))

        await _log_approval_action(db, "approve", "mentor_allocation", item_id, desc, note)
        await db.commit()
        return {"id": str(item_id), "decision": "approved", "entity_type": "mentor_allocation", "status": "accepted", "message": f"Approved {desc}"}

    # Resource pool out-of-stock alert
    pool = (await db.execute(
        select(ResourceItem).where(ResourceItem.id == item_id)
    )).scalar_one_or_none()
    if pool:
        desc = f"restock authorization for pool '{pool.name}'"
        await _log_approval_action(db, "approve", "resource_item", item_id, desc, note)
        await db.commit()
        return {"id": str(item_id), "decision": "approved", "entity_type": "resource_item", "message": f"Approved {desc}"}

    raise HTTPException(status_code=404, detail="Approval item not found")


@router.patch("/approval-queue/{item_id}/reject")
async def reject_queue_item(
    item_id: uuid.UUID,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    note: str | None = Query(default=None),
):
    """
    Reject an item in the queue, discarding the proposed action.

    - mentor_allocation: the proposal is declined (the orchestrator may
      propose a different mentor on its next sweep).
    - resource_low_stock: the alert is dismissed and logged for audit.
    """
    alloc = (await db.execute(
        select(MentorAllocation).where(MentorAllocation.id == item_id)
    )).scalar_one_or_none()

    if alloc:
        if alloc.status != "proposed":
            raise HTTPException(status_code=409, detail=f"Allocation already {alloc.status}")
        mentor = (await db.execute(
            select(Mentor).where(Mentor.id == alloc.mentor_id)
        )).scalar_one_or_none()
        desc = f"mentor {mentor.name if mentor else '?'} for issue {str(alloc.issue_id)[:8]}"

        alloc.status = "declined"
        alloc.responded_at = datetime.now(timezone.utc)
        alloc.reasoning = (alloc.reasoning or "") + " | Rejected by organizer"

        await _log_approval_action(db, "reject", "mentor_allocation", item_id, desc, note)
        await db.commit()
        return {"id": str(item_id), "decision": "rejected", "entity_type": "mentor_allocation", "status": "declined", "message": f"Rejected {desc}"}

    pool = (await db.execute(
        select(ResourceItem).where(ResourceItem.id == item_id)
    )).scalar_one_or_none()
    if pool:
        desc = f"restock alert for pool '{pool.name}'"
        await _log_approval_action(db, "reject", "resource_item", item_id, desc, note)
        await db.commit()
        return {"id": str(item_id), "decision": "rejected", "entity_type": "resource_item", "message": f"Rejected {desc}"}

    raise HTTPException(status_code=404, detail="Approval item not found")


# ─── Broadcast ───────────────────────────────────────────

@router.post("/broadcast", response_model=BroadcastResult)
async def broadcast_message(
    body: BroadcastRequest,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Broadcast a message to all participants.
    Creates an in-app notification for each participant.
    """
    # Get all participants
    result = await db.execute(select(Participant))
    participants = result.scalars().all()

    total_sent = 0
    for p in participants:
        notif = Notification(
            recipient_id=p.id,
            team_id=p.team_id,
            content=f"📢 Broadcast: {body.message}",
            channel=body.channel if body.channel != "all" else "in_app",
            trigger_reason="organizer_broadcast",
            reminder_type="broadcast",
            read=False,
        )
        db.add(notif)
        total_sent += 1

    await db.commit()

    # Notify WebSocket listeners
    await ws_manager.broadcast({
        "type": "broadcast",
        "message": body.message,
        "total_recipients": total_sent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return BroadcastResult(
        total_recipients=total_sent,
        notifications_sent=total_sent,
        message_preview=body.message[:100],
    )


# ─── Manual override: team ───────────────────────────────

@router.patch("/teams/{team_id}/override")
async def override_team(
    team_id: str,
    body: TeamOverride,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Manual override for a team record. Organizer can force status/readiness."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if body.submission_status is not None:
        team.submission_status = body.submission_status
    if body.readiness_pct is not None:
        team.readiness_pct = body.readiness_pct

    await db.commit()
    await db.refresh(team)

    # Notify WebSocket listeners
    await ws_manager.broadcast({
        "type": "team_override",
        "team_id": str(team.id),
        "team_name": team.name,
        "changes": {
            k: v for k, v in body.model_dump(exclude_none=True).items()
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "id": str(team.id),
        "name": team.name,
        "submission_status": team.submission_status,
        "readiness_pct": team.readiness_pct,
        "message": "Override applied",
    }


# ─── Manual override: submission ─────────────────────────

@router.patch("/submissions/{submission_id}/override")
async def override_submission(
    submission_id: str,
    body: SubmissionOverride,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Manual override for a submission record. Organizer can force completeness."""
    result = await db.execute(select(Submission).where(Submission.id == submission_id))
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if body.completeness_pct is not None:
        submission.completeness_pct = body.completeness_pct

    submission.last_audited_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(submission)

    return {
        "id": str(submission.id),
        "completeness_pct": submission.completeness_pct,
        "message": "Override applied",
    }


# ─── Export submissions as CSV ───────────────────────────

@router.get("/export")
async def export_submissions_csv(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all submissions with audit status as CSV.
    Returns a downloadable CSV file.
    """
    # Join teams with submissions
    result = await db.execute(
        select(Team, Submission)
        .join(Submission, Submission.team_id == Team.id, isouter=True)
        .order_by(Team.name)
    )
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Team Name", "Submission Status", "Readiness %",
        "Repo URL", "Demo URL", "Description",
        "Completeness %", "Last Audited",
    ])

    for team, submission in rows:
        writer.writerow([
            team.name,
            team.submission_status,
            team.readiness_pct,
            submission.repo_url if submission else "",
            submission.demo_url if submission else "",
            (submission.description[:200] if submission and submission.description else ""),
            submission.completeness_pct if submission else 0.0,
            submission.last_audited_at.isoformat() if submission and submission.last_audited_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=submissions_export.csv"
        },
    )


# ─── WebSocket for live updates ──────────────────────────

@router.websocket("/ws")
async def dashboard_websocket(websocket: WebSocket, token: str = Query(default="")):
    """
    WebSocket endpoint for live dashboard updates.

    Requires an organizer JWT passed as a query parameter (?token=...) —
    browsers cannot set headers on a WebSocket handshake. Connections
    without a valid token are closed immediately.
    """
    from app.auth import require_organizer_ws

    # Authenticate before accepting
    try:
        await require_organizer_ws(websocket, token)
    except Exception:
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; receive client messages (pings, etc.)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ─── Trigger live update broadcast (called by orchestrator) ─

async def broadcast_dashboard_update(event_type: str, payload: dict):
    """Push a live update to all connected dashboard WebSocket clients."""
    await ws_manager.broadcast({
        "type": event_type,
        "data": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
