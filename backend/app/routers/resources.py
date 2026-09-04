"""Resources router — CRUD for resource item pools."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.auth import require_organizer, require_any_role
from app.models.resource import ResourceItem
from app.schemas.resources import ResourceItemCreate, ResourceItemOut

router = APIRouter(prefix="/resources", tags=["resources"])


class ResourcePoolPublic(BaseModel):
    """Participant-facing view of a resource pool (no organizer internals)."""
    id: uuid.UUID
    name: str
    resource_type: str
    total_quantity: int
    available_quantity: int

    class Config:
        from_attributes = True


@router.get("/available", response_model=list[ResourcePoolPublic])
async def list_available_resources(
    _payload=Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """
    List resource pools with live stock.

    Accessible to participants (so the request screen can show live stock
    and availability) and organizers. This is the participant-facing view
    of what POST /resource-requests can actually allocate.
    """
    result = await db.execute(select(ResourceItem).order_by(ResourceItem.name))
    return result.scalars().all()


@router.post("", response_model=ResourceItemOut, status_code=status.HTTP_201_CREATED)
async def create_resource_item(
    body: ResourceItemCreate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    item = ResourceItem(
        name=body.name,
        resource_type=body.resource_type,
        total_quantity=body.total_quantity,
        available_quantity=body.available_quantity if body.available_quantity is not None else body.total_quantity,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/bulk", response_model=list[ResourceItemOut], status_code=status.HTTP_201_CREATED)
async def bulk_create_resource_items(
    items: list[ResourceItemCreate],
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple resource items in one call."""
    created = []
    for body in items:
        item = ResourceItem(
            name=body.name,
            resource_type=body.resource_type,
            total_quantity=body.total_quantity,
            available_quantity=body.available_quantity if body.available_quantity is not None else body.total_quantity,
        )
        db.add(item)
        created.append(item)
    await db.commit()
    for item in created:
        await db.refresh(item)
    return created


@router.get("", response_model=list[ResourceItemOut])
async def list_resource_items(
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ResourceItem).order_by(ResourceItem.name))
    return result.scalars().all()


@router.get("/{item_id}", response_model=ResourceItemOut)
async def get_resource_item(
    item_id: uuid.UUID,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ResourceItem).where(ResourceItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Resource item not found")
    return item
