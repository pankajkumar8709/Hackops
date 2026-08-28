"""JWT + token utilities for Phase 2 auth."""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db

settings = get_settings()
bearer_scheme = HTTPBearer()

# ─── Organizer credentials (hardcoded for hackathon scope)
# In production this would be a DB table with hashed passwords.
ORGANIZER_USERNAME = "organizer"
ORGANIZER_PASSWORD = "pulse_admin_2026"


# ─── JWT ──────────────────────────────────────────────────

def create_jwt(data: dict, expires_minutes: int = settings.jwt_expire_minutes) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ─── Participant magic-link style token ───────────────────

def generate_participant_token() -> tuple[str, str]:
    """Return (plain_token, token_hash). Store only the hash."""
    plain = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(plain.encode()).hexdigest()
    return plain, hashed


def hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


# ─── FastAPI dependencies ─────────────────────────────────

def _extract_bearer(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    return credentials.credentials


async def require_organizer(token: str = Depends(_extract_bearer)) -> dict:
    payload = decode_jwt(token)
    if payload.get("role") != "organizer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organizer access required")
    return payload


async def require_participant(
    token: str = Depends(_extract_bearer),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates participant bearer token (JWT wrapping participant_id).
    Returns the Participant ORM object — row-level scoping built in.
    """
    from app.models.participant import Participant

    payload = decode_jwt(token)
    if payload.get("role") != "participant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Participant access required")

    participant_id = payload.get("sub")
    result = await db.execute(select(Participant).where(Participant.id == participant_id))
    participant = result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Participant not found")
    return participant
