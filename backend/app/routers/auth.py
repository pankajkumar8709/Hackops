"""Auth router — POST /auth/organizer/login."""
from fastapi import APIRouter, HTTPException, status

from app.auth import (
    create_jwt,
    ORGANIZER_USERNAME,
    ORGANIZER_PASSWORD,
)
from app.schemas.auth import OrganizerLogin, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/organizer/login", response_model=TokenResponse)
async def organizer_login(body: OrganizerLogin):
    """
    Organizer login with static credentials (suitable for hackathon scope).
    Returns a JWT with role='organizer'.
    """
    if body.username != ORGANIZER_USERNAME or body.password != ORGANIZER_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organizer credentials",
        )
    token = create_jwt({"sub": "organizer", "role": "organizer"})
    return TokenResponse(access_token=token, role="organizer")
