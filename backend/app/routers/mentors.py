"""Mentors router — CRUD for mentor roster."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_organizer
from app.models.mentor import Mentor
from app.schemas.mentors import MentorCreate, MentorUpdate, MentorOut

router = APIRouter(prefix="/mentors", tags=["mentors"])


@router.post("", response_model=MentorOut, status_code=status.HTTP_201_CREATED)
async def create_mentor(
    body: MentorCreate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    mentor = Mentor(**body.model_dump())
    db.add(mentor)
    await db.commit()
    await db.refresh(mentor)
    return mentor


@router.get("", response_model=list[MentorOut])
async def list_mentors(
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Mentor).order_by(Mentor.name))
    return result.scalars().all()


@router.get("/{mentor_id}", response_model=MentorOut)
async def get_mentor(
    mentor_id: uuid.UUID,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Mentor).where(Mentor.id == mentor_id))
    mentor = result.scalar_one_or_none()
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found")
    return mentor


@router.patch("/{mentor_id}", response_model=MentorOut)
async def update_mentor(
    mentor_id: uuid.UUID,
    body: MentorUpdate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Mentor).where(Mentor.id == mentor_id))
    mentor = result.scalar_one_or_none()
    if not mentor:
        raise HTTPException(status_code=404, detail="Mentor not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mentor, field, value)
    await db.commit()
    await db.refresh(mentor)
    return mentor
