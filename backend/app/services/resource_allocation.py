"""Resource Allocation service -- Phase 8.

Core flow:
  1. Check live availability of a ResourceItem pool
  2. Auto-allocate next available unit (decrement available_quantity)
  3. Return resource (increment available_quantity, mark returned)
  4. Overdue detection (allocated > N hours ago, not returned)
  5. Pool summary for organizer dashboard

All logic is deterministic (pure Python) -- no LLM calls.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.resource import ResourceItem, ResourceAllocation
from app.models.team import Team

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────

# After how many hours an allocation is considered overdue
OVERDUE_THRESHOLD_HOURS = 24

# ─── Availability Check ──────────────────────────────────────


async def check_availability(
    db: AsyncSession,
    resource_item_id: uuid.UUID,
) -> tuple[ResourceItem, int]:
    """Check how many units of a resource are available.

    Returns (ResourceItem, available_count).
    Raises ValueError if item not found.
    """
    result = await db.execute(
        select(ResourceItem).where(ResourceItem.id == resource_item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError(f"Resource item {resource_item_id} not found")

    return item, item.available_quantity


# ─── Allocate ────────────────────────────────────────────────


async def allocate_resource(
    db: AsyncSession,
    resource_item_id: uuid.UUID,
    team_id: uuid.UUID,
) -> ResourceAllocation:
    """
    Allocate one unit of a resource to a team.

    - Checks live availability
    - Decrements available_quantity
    - Creates ResourceAllocation record
    - Returns the allocation

    Raises ValueError if not available or item not found.
    """
    item, available = await check_availability(db, resource_item_id)

    if available <= 0:
        raise ValueError(
            f"Resource '{item.name}' ({item.resource_type}) is out of stock. "
            f"Total: {item.total_quantity}, Allocated: {item.total_quantity - available}."
        )

    # Decrement available quantity
    item.available_quantity -= 1

    # Create allocation record
    allocation = ResourceAllocation(
        resource_item_id=resource_item_id,
        team_id=team_id,
        status="allocated",
    )
    db.add(allocation)
    await db.flush()

    logger.info(
        "Allocated '%s' to team %s (remaining: %d/%d)",
        item.name, team_id, item.available_quantity, item.total_quantity,
    )

    return allocation


# ─── Return ──────────────────────────────────────────────────


async def return_resource(
    db: AsyncSession,
    allocation_id: uuid.UUID,
    team_id: uuid.UUID,
) -> ResourceAllocation:
    """
    Mark a resource allocation as returned.

    - Validates the allocation belongs to the team
    - Increments available_quantity on the ResourceItem
    - Marks allocation as 'returned' with timestamp

    Raises ValueError if allocation not found, wrong team, or already returned.
    """
    result = await db.execute(
        select(ResourceAllocation)
        .options(selectinload(ResourceAllocation.resource_item))
        .where(ResourceAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()
    if not allocation:
        raise ValueError(f"Allocation {allocation_id} not found")

    if allocation.team_id != team_id:
        raise ValueError("You can only return resources allocated to your team")

    if allocation.status == "returned":
        raise ValueError("This resource has already been returned")

    # Mark as returned
    allocation.status = "returned"
    allocation.returned_at = datetime.now(timezone.utc)

    # Increment available quantity
    item = allocation.resource_item
    if item:
        item.available_quantity = min(
            item.available_quantity + 1,
            item.total_quantity,
        )

    await db.flush()

    logger.info(
        "Returned '%s' from team %s (now available: %d/%d)",
        item.name if item else "unknown", team_id,
        item.available_quantity if item else 0,
        item.total_quantity if item else 0,
    )

    return allocation


# ─── Overdue Detection ───────────────────────────────────────


async def check_overdue_allocations(
    db: AsyncSession,
    threshold_hours: float = OVERDUE_THRESHOLD_HOURS,
) -> list[ResourceAllocation]:
    """
    Find allocations that are overdue (allocated > N hours ago, not returned).

    Updates their status to 'overdue' and returns the list.
    Called periodically (by APScheduler in Phase 9, or on-demand).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)

    result = await db.execute(
        select(ResourceAllocation)
        .options(
            selectinload(ResourceAllocation.resource_item),
            selectinload(ResourceAllocation.team),
        )
        .where(
            ResourceAllocation.status == "allocated",
            ResourceAllocation.allocated_at < cutoff,
        )
    )
    overdue = result.scalars().unique().all()

    for allocation in overdue:
        allocation.status = "overdue"
        await db.flush()

    if overdue:
        logger.warning(
            "Found %d overdue resource allocations (threshold: %dh)",
            len(overdue), threshold_hours,
        )

    return list(overdue)


# ─── Pool Summary ────────────────────────────────────────────


async def get_pool_summary(
    db: AsyncSession,
) -> list[dict]:
    """
    Get a summary of all resource pools for the organizer dashboard.

    Includes allocated_count and overdue_count per item.
    Uses bulk aggregation to avoid N+1 queries.
    """
    overdue_cutoff = datetime.now(timezone.utc) - timedelta(
        hours=OVERDUE_THRESHOLD_HOURS
    )

    # Bulk-count allocations grouped by resource_item_id
    alloc_counts_result = await db.execute(
        select(
            ResourceAllocation.resource_item_id,
            func.count(ResourceAllocation.id).label("allocated_count"),
        )
        .where(ResourceAllocation.status == "allocated")
        .group_by(ResourceAllocation.resource_item_id)
    )
    alloc_counts = {row[0]: row[1] for row in alloc_counts_result.fetchall()}

    # Bulk-count overdue allocations grouped by resource_item_id
    overdue_counts_result = await db.execute(
        select(
            ResourceAllocation.resource_item_id,
            func.count(ResourceAllocation.id).label("overdue_count"),
        )
        .where(
            ResourceAllocation.status == "allocated",
            ResourceAllocation.allocated_at < overdue_cutoff,
        )
        .group_by(ResourceAllocation.resource_item_id)
    )
    overdue_counts = {row[0]: row[1] for row in overdue_counts_result.fetchall()}

    # Fetch all items
    result = await db.execute(
        select(ResourceItem).order_by(ResourceItem.name)
    )
    items = result.scalars().all()

    summaries = []
    for item in items:
        summaries.append({
            "id": item.id,
            "name": item.name,
            "resource_type": item.resource_type,
            "total_quantity": item.total_quantity,
            "available_quantity": item.available_quantity,
            "allocated_count": alloc_counts.get(item.id, 0),
            "overdue_count": overdue_counts.get(item.id, 0),
        })

    return summaries
