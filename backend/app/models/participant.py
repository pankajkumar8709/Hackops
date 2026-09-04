"""Participant model — no late circular imports."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.database import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.issue import Issue, Notification


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    track_pref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    discord_handle: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="participant")

    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships — string refs avoid circular imports at module load time
    team: Mapped[Optional["Team"]] = relationship(
        "Team", back_populates="members", foreign_keys=[team_id]
    )
    issues: Mapped[list["Issue"]] = relationship("Issue", back_populates="participant")
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="recipient"
    )
