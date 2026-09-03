"""Event, Track, and ScheduleEvent models — no late circular imports."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.submission import SubmissionRequirement


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_phase: Mapped[str] = mapped_column(String(100), nullable=False, default="registration")
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tracks: Mapped[list["Track"]] = relationship("Track", back_populates="event")
    schedule_events: Mapped[list["ScheduleEvent"]] = relationship("ScheduleEvent", back_populates="event")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    eligibility_rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event: Mapped[Optional["Event"]] = relationship("Event", back_populates="tracks")
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="track")
    submission_requirements: Mapped[list["SubmissionRequirement"]] = relationship(
        "SubmissionRequirement", back_populates="track"
    )


class ScheduleEvent(Base):
    __tablename__ = "schedule_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    track_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    audience_filter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )

    event: Mapped[Optional["Event"]] = relationship("Event", back_populates="schedule_events")
