"""Mentor model."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.database import Base


class Mentor(Base):
    __tablename__ = "mentors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    availability_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="available"
        # values: "available", "busy", "offline"
    )
    discord_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    allocations: Mapped[list["MentorAllocation"]] = relationship(
        "MentorAllocation", back_populates="mentor"
    )


# MentorAllocation is part of Phase 7 — import stub kept here
# to avoid circular deps when models/__init__.py loads.
from app.models.mentor_allocation import MentorAllocation  # noqa: E402
