"""JWT + token utilities for Phase 2 auth."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db

settings = get_settings()
bearer_scheme = HTTPBearer()

# ─── Password hashing (bcrypt) ──────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── Organizer credentials (env-driven, never hardcoded)
# Read from settings (which loads ORGANIZER_USERNAME / ORGANIZER_PASSWORD
# from .env). If unset, a random password is generated once at import and
# logged so the operator can see it — no real-looking credential is ever
# committed to source.
import logging as _logging
import secrets as _secrets

_org_logger = _logging.getLogger(__name__)

_settings = get_settings()

ORGANIZER_USERNAME = _settings.organizer_username or "organizer"
ORGANIZER_PASSWORD = _settings.organizer_password
if not ORGANIZER_PASSWORD:
    ORGANIZER_PASSWORD = _secrets.token_urlsafe(16)
    _org_logger.warning(
        "ORGANIZER_PASSWORD not set in .env — generated one-time password: %s",
        ORGANIZER_PASSWORD,
    )

# Hash the organizer password at import time for constant-time comparison
ORGANIZER_PASSWORD_HASH = pwd_context.hash(ORGANIZER_PASSWORD)


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


def verify_token_hash(plain: str, stored_hash: str) -> bool:
    """Constant-time comparison of token hash to prevent timing attacks."""
    computed = hashlib.sha256(plain.encode()).hexdigest()
    return hmac.compare_digest(computed, stored_hash)


def verify_organizer_password(plain: str) -> bool:
    """Verify organizer password against bcrypt hash (constant-time)."""
    return pwd_context.verify(plain, ORGANIZER_PASSWORD_HASH)


def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


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


async def require_any_role(
    token: str = Depends(_extract_bearer),
    db: AsyncSession = Depends(get_db),
):
    """
    Accepts a valid organizer OR participant JWT and returns the payload.

    Used by endpoints shared between the participant UI and the
    organizer-authenticated Discord bot (e.g. POST /qa).
    """
    payload = decode_jwt(token)
    if payload.get("role") not in ("organizer", "participant"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return payload


async def require_organizer_ws(websocket, token: str):
    """Validate an organizer JWT supplied as a WebSocket query parameter.

    Browsers cannot set headers on a WebSocket handshake, so the dashboard
    client passes ?token=<jwt>. Raises WebSocketDisconnect on failure.
    """
    from fastapi import WebSocketDisconnect

    if not token:
        await websocket.close(code=4401, reason="Missing token")
        raise WebSocketDisconnect(code=4401)
    try:
        payload = decode_jwt(token)
    except HTTPException:
        await websocket.close(code=4401, reason="Invalid token")
        raise WebSocketDisconnect(code=4401)
    if payload.get("role") != "organizer":
        await websocket.close(code=4403, reason="Organizer access required")
        raise WebSocketDisconnect(code=4403)
    return payload
