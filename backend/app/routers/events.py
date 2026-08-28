"""Events router — CRUD for events, tracks, schedule-events, submission-requirements."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_organizer
from app.models.event import Event, Track, ScheduleEvent
from app.models.submission import SubmissionRequirement
from app.schemas.events import (
    EventCreate, EventUpdate, EventOut,
    TrackCreate, TrackOut,
    ScheduleEventCreate, ScheduleEventOut,
    SubmissionRequirementCreate, SubmissionRequirementOut,
)

router = APIRouter(tags=["events"])


# ─── Events ────────────────────────────────────────

@router.post("/events", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    event = Event(**body.model_dump())
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.get("/events", response_model=list[EventOut])
async def list_events(
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).order_by(Event.created_at))
    return result.scalars().all()


@router.patch("/events/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await db.commit()
    await db.refresh(event)
    return event


# ─── Tracks ────────────────────────────────────────

@router.post("/tracks", response_model=TrackOut, status_code=status.HTTP_201_CREATED)
async def create_track(
    body: TrackCreate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    # Verify event exists
    ev = await db.execute(select(Event).where(Event.id == body.event_id))
    if not ev.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event not found")
    track = Track(**body.model_dump())
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return track


@router.get("/tracks", response_model=list[TrackOut])
async def list_tracks(
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Track).order_by(Track.name))
    return result.scalars().all()


# ─── Submission Requirements ───────────────────────

@router.post("/submission-requirements", response_model=SubmissionRequirementOut, status_code=status.HTTP_201_CREATED)
async def create_submission_requirement(
    body: SubmissionRequirementCreate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    # Verify track exists
    tr = await db.execute(select(Track).where(Track.id == body.track_id))
    if not tr.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Track not found")
    req = SubmissionRequirement(**body.model_dump())
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req


@router.get("/submission-requirements", response_model=list[SubmissionRequirementOut])
async def list_submission_requirements(
    track_id: uuid.UUID | None = None,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    query = select(SubmissionRequirement)
    if track_id:
        query = query.where(SubmissionRequirement.track_id == track_id)
    result = await db.execute(query.order_by(SubmissionRequirement.field_name))
    return result.scalars().all()


# ─── Schedule Events ──────────────────────────────

@router.post("/schedule-events", response_model=ScheduleEventOut, status_code=status.HTTP_201_CREATED)
async def create_schedule_event(
    body: ScheduleEventCreate,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    ev = await db.execute(select(Event).where(Event.id == body.event_id))
    if not ev.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event not found")
    se = ScheduleEvent(**body.model_dump())
    db.add(se)
    await db.commit()
    await db.refresh(se)
    return se


@router.get("/schedule-events", response_model=list[ScheduleEventOut])
async def list_schedule_events(
    event_id: uuid.UUID | None = None,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    query = select(ScheduleEvent)
    if event_id:
        query = query.where(ScheduleEvent.event_id == event_id)
    result = await db.execute(query.order_by(ScheduleEvent.start_time))
    return result.scalars().all()
