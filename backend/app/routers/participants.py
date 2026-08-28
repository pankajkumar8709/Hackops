"""Participants router — registration and profile."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import (
    generate_participant_token,
    create_jwt,
    require_participant,
    require_organizer,
)
from app.models.participant import Participant
from app.schemas.auth import ParticipantRegister, ParticipantOut, ParticipantPublic

router = APIRouter(prefix="/participants", tags=["participants"])


@router.post("/register", response_model=ParticipantOut, status_code=status.HTTP_201_CREATED)
async def register_participant(
    body: ParticipantRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new participant.
    Returns a one-time plain token — store it, it is never shown again.
    """
    # Check duplicate email
    existing = await db.execute(
        select(Participant).where(Participant.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    plain_token, token_hash = generate_participant_token()

    participant = Participant(
        name=body.name,
        email=body.email,
        token_hash=token_hash,
        skills=body.skills,
        track_pref=body.track_pref,
        discord_handle=body.discord_handle,
        role="participant",
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)

    # Issue a JWT wrapping the participant ID
    jwt_token = create_jwt({"sub": str(participant.id), "role": "participant"})

    return ParticipantOut(
        id=participant.id,
        name=participant.name,
        email=participant.email,
        skills=participant.skills,
        track_pref=participant.track_pref,
        discord_handle=participant.discord_handle,
        role=participant.role,
        team_id=participant.team_id,
        token=jwt_token,
    )


@router.get("/me", response_model=ParticipantPublic)
async def get_me(participant: Participant = Depends(require_participant)):
    """Return the authenticated participant's profile."""
    return participant


@router.get("", response_model=list[ParticipantPublic])
async def list_participants(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Organizer-only: list all participants."""
    result = await db.execute(select(Participant).order_by(Participant.name))
    return result.scalars().all()


@router.get("/{participant_id}", response_model=ParticipantPublic)
async def get_participant(
    participant_id: uuid.UUID,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Organizer-only: get a specific participant by ID."""
    result = await db.execute(
        select(Participant).where(Participant.id == participant_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return p
