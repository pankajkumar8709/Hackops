"""Resource Requests router -- Phase 8: Resource Allocation & Tracking.

Endpoints:
  POST   /resource-requests              -- participant requests a resource
  GET    /resource-requests/mine         -- participant views own team's allocations
  GET    /resource-requests/{id}         -- view specific allocation
  PATCH  /resource-requests/{id}/return  -- participant returns a resource
  GET    /resource-requests              -- organizer: list all allocations
  GET    /resource-pools                 -- organizer: pool summary with stock levels
  POST   /resource-requests/check-overdue -- organizer: trigger overdue check
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import require_participant, require_organizer
from app.models.participant import Participant
from app.models.resource import ResourceItem, ResourceAllocation
from app.schemas.resource_allocations import (
    ResourceRequestCreate,
    ResourceAllocationOut,
    ResourceReturn,
    ResourcePoolSummary,
)
from app.services.resource_allocation import (
    allocate_resource,
    return_resource,
    check_overdue_allocations,
    get_pool_summary,
)

router = APIRouter(tags=["resource-requests"])


# ─── Participant: request a resource ─────────────────────────


@router.post(
    "/resource-requests",
    response_model=ResourceAllocationOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_resource(
    body: ResourceRequestCreate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Request a resource allocation for the participant's team.

    The system will:
    1. Check live availability of the requested resource pool
    2. If available, auto-allocate one unit and decrement the pool
    3. If out of stock, return an error (organizer is flagged separately)

    Each team can hold multiple resource types simultaneously.
    Duplicate requests for the same resource type are allowed (multiple units).
    """
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must be in a team to request resources.",
        )

    # Validate the resource item exists
    result = await db.execute(
        select(ResourceItem).where(ResourceItem.id == body.resource_item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource item not found.",
        )

    # Check availability and allocate
    try:
        allocation = await allocate_resource(
            db, body.resource_item_id, participant.team_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    await db.commit()

    # Reload with relationships for response
    result = await db.execute(
        select(ResourceAllocation)
        .options(
            selectinload(ResourceAllocation.resource_item),
            selectinload(ResourceAllocation.team),
        )
        .where(ResourceAllocation.id == allocation.id)
    )
    allocation = result.scalar_one()

    return _build_allocation_out(allocation)


# ─── Participant: view own team's allocations ────────────────


@router.get(
    "/resource-requests/mine",
    response_model=list[ResourceAllocationOut],
)
async def get_my_allocations(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: allocated, returned, overdue",
    ),
):
    """
    Return the authenticated participant's team resource allocations.
    """
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You must be in a team to view allocations.",
        )

    query = (
        select(ResourceAllocation)
        .options(
            selectinload(ResourceAllocation.resource_item),
            selectinload(ResourceAllocation.team),
        )
        .where(ResourceAllocation.team_id == participant.team_id)
        .order_by(ResourceAllocation.allocated_at.desc())
    )

    if status_filter:
        query = query.where(ResourceAllocation.status == status_filter)

    result = await db.execute(query)
    allocations = result.scalars().unique().all()

    return [_build_allocation_out(a) for a in allocations]


# ─── View specific allocation ────────────────────────────────


@router.get(
    "/resource-requests/{allocation_id}",
    response_model=ResourceAllocationOut,
)
async def get_allocation(
    allocation_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """View a specific resource allocation. Participants can only view their own team's."""
    result = await db.execute(
        select(ResourceAllocation)
        .options(
            selectinload(ResourceAllocation.resource_item),
            selectinload(ResourceAllocation.team),
        )
        .where(ResourceAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found.",
        )

    # Row-level scoping
    if allocation.team_id != participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own team's allocations.",
        )

    return _build_allocation_out(allocation)


# ─── Participant: return a resource ──────────────────────────


@router.patch(
    "/resource-requests/{allocation_id}/return",
    response_model=ResourceAllocationOut,
)
async def return_allocated_resource(
    allocation_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Return a previously allocated resource.

    - Validates the allocation belongs to the participant's team
    - Increments available_quantity on the ResourceItem pool
    - Records the return timestamp
    """
    if not participant.team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You must be in a team to return resources.",
        )

    try:
        allocation = await return_resource(
            db, allocation_id, participant.team_id
        )
    except ValueError as e:
        status_code = status.HTTP_404_NOT_FOUND
        if "already been returned" in str(e):
            status_code = status.HTTP_409_CONFLICT
        elif "your team" in str(e):
            status_code = status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=str(e))

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(ResourceAllocation)
        .options(
            selectinload(ResourceAllocation.resource_item),
            selectinload(ResourceAllocation.team),
        )
        .where(ResourceAllocation.id == allocation.id)
    )
    allocation = result.scalar_one()

    return _build_allocation_out(allocation)


# ─── Organizer: list all allocations ─────────────────────────


@router.get(
    "/resource-requests",
    response_model=list[ResourceAllocationOut],
)
async def list_allocations(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: allocated, returned, overdue",
    ),
):
    """Organizer: list all resource allocations with filters."""
    query = (
        select(ResourceAllocation)
        .options(
            selectinload(ResourceAllocation.resource_item),
            selectinload(ResourceAllocation.team),
        )
        .order_by(ResourceAllocation.allocated_at.desc())
    )

    if status_filter:
        query = query.where(ResourceAllocation.status == status_filter)

    result = await db.execute(query)
    allocations = result.scalars().unique().all()

    return [_build_allocation_out(a) for a in allocations]


# ─── Organizer: pool summary ────────────────────────────────


@router.get(
    "/resource-pools",
    response_model=list[ResourcePoolSummary],
)
async def resource_pool_summary(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """
    Organizer: get a summary of all resource pools.

    Shows stock levels, allocated count, and overdue count per item.
    This is the main view for the organizer dashboard resource section.
    """
    summaries = await get_pool_summary(db)
    return [ResourcePoolSummary(**s) for s in summaries]


# ─── Organizer: trigger overdue check ───────────────────────


@router.post(
    "/resource-requests/check-overdue",
    response_model=list[ResourceAllocationOut],
)
async def trigger_overdue_check(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
    threshold_hours: float = Query(
        default=24.0,
        ge=1.0,
        description="Hours after which an allocation is considered overdue",
    ),
):
    """
    Organizer: manually trigger overdue check for resource allocations.

    Any allocations older than the threshold will be marked as 'overdue'.
    """
    overdue = await check_overdue_allocations(db, threshold_hours)
    await db.commit()

    # Reload with relationships
    results = []
    for alloc in overdue:
        result = await db.execute(
            select(ResourceAllocation)
            .options(
                selectinload(ResourceAllocation.resource_item),
                selectinload(ResourceAllocation.team),
            )
            .where(ResourceAllocation.id == alloc.id)
        )
        loaded = result.scalar_one_or_none()
        if loaded:
            results.append(_build_allocation_out(loaded))

    return results


# ─── Helper: build response ─────────────────────────────────


def _build_allocation_out(allocation: ResourceAllocation) -> ResourceAllocationOut:
    """Build ResourceAllocationOut from a loaded allocation with relationships."""
    from datetime import datetime, timezone

    resource_summary = None
    if allocation.resource_item:
        resource_summary = {
            "id": str(allocation.resource_item.id),
            "name": allocation.resource_item.name,
            "resource_type": allocation.resource_item.resource_type,
            "available_quantity": allocation.resource_item.available_quantity,
            "total_quantity": allocation.resource_item.total_quantity,
        }

    team_summary = None
    if allocation.team:
        team_summary = {
            "id": str(allocation.team.id),
            "name": allocation.team.name,
        }

    # Check if overdue (allocated > threshold hours ago and not returned)
    overdue = False
    if allocation.status == "allocated":
        from app.services.resource_allocation import OVERDUE_THRESHOLD_HOURS
        from datetime import timedelta
        elapsed = datetime.now(timezone.utc) - allocation.allocated_at
        overdue = elapsed > timedelta(hours=OVERDUE_THRESHOLD_HOURS)

    return ResourceAllocationOut(
        id=allocation.id,
        resource_item_id=allocation.resource_item_id,
        team_id=allocation.team_id,
        status=allocation.status,
        allocated_at=allocation.allocated_at,
        returned_at=allocation.returned_at,
        overdue=overdue,
        resource_item=resource_summary,
        team=team_summary,
    )
