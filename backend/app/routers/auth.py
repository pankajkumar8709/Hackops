"""Auth router — organizer + participant login."""
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_jwt,
    verify_password,
    verify_organizer_password,
    ORGANIZER_USERNAME,
)
from app.database import get_db
from app.models.participant import Participant
from app.schemas.auth import (
    OrganizerLogin,
    TokenResponse,
    ParticipantLogin,
    ParticipantTokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ─── Rate limiting ──────────────────────────────────────
# In-memory rate limiter: max 5 attempts per minute per IP
_rate_limits: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 60


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if too many login attempts from the same IP."""
    now = time.time()
    # Prune old entries
    _rate_limits[client_ip] = [
        t for t in _rate_limits[client_ip] if now - t < _WINDOW_SECONDS
    ]
    if len(_rate_limits[client_ip]) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )
    _rate_limits[client_ip].append(now)


@router.post("/organizer/login", response_model=TokenResponse)
async def organizer_login(
    body: OrganizerLogin,
    request: Request = None,
):
    """
    Organizer login. Credentials come from ORGANIZER_USERNAME /
    ORGANIZER_PASSWORD env vars (never hardcoded in source).
    Returns a JWT with role='organizer'.
    """
    client_ip = request.client.host if request else "unknown"
    _check_rate_limit(client_ip)

    if body.username != ORGANIZER_USERNAME or not verify_organizer_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organizer credentials",
        )
    token = create_jwt({"sub": "organizer", "role": "organizer"})
    return TokenResponse(access_token=token, role="organizer")


@router.post("/participant/login", response_model=ParticipantTokenResponse)
async def participant_login(
    body: ParticipantLogin,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """
    Participant login with email + password.

    The participant authenticates with their registered email and the
    password they set during registration; a fresh JWT is returned for
    API access.
    """
    client_ip = request.client.host if request else "unknown"
    _check_rate_limit(client_ip)

    result = await db.execute(
        select(Participant).where(Participant.email == body.email)
    )
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found for that email",
        )

    if not participant.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has no password configured. Please contact an organizer.",
        )

    if not verify_password(body.password, participant.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    jwt_token = create_jwt({"sub": str(participant.id), "role": "participant"})
    return ParticipantTokenResponse(
        access_token=jwt_token,
        role="participant",
        participant_id=participant.id,
        name=participant.name,
        email=participant.email,
    )