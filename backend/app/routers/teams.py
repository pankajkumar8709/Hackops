"""Teams router — create, join, view."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_participant, require_organizer
from app.models.participant import Participant
from app.models.team import Team
from app.schemas.auth import TeamCreate, TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new team. The creator is automatically joined to it.
    A participant can only be in one team at a time.
    """
    if participant.team_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already in a team. Leave it before creating a new one.",
        )

    team = Team(
        name=body.name,
        track_id=body.track_id,
    )
    db.add(team)
    await db.flush()  # get team.id before linking participant

    participant.team_id = team.id
    await db.commit()
    await db.refresh(team)
    return team


@router.post("/{team_id}/join", response_model=TeamOut)
async def join_team(
    team_id: uuid.UUID,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """Join an existing team."""
    if participant.team_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already in a team.",
        )

    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    participant.team_id = team.id
    await db.commit()
    await db.refresh(team)
    return team


@router.get("/mine", response_model=TeamOut)
async def get_my_team(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated participant's team."""
    if participant.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in a team")

    result = await db.execute(select(Team).where(Team.id == participant.team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.get("", response_model=list[TeamOut])
async def list_teams(
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Organizer-only: list all teams."""
    result = await db.execute(select(Team).order_by(Team.name))
    return result.scalars().all()


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(
    team_id: uuid.UUID,
    _organizer=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Organizer-only: get a specific team."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team
