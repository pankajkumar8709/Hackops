"""Team model — no late circular imports."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.participant import Participant
    from app.models.event import Track
    from app.models.submission import Submission
    from app.models.issue import Issue
    from app.models.resource import ResourceAllocation


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    track_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True
    )
    repo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    readme_ok: Mapped[bool] = mapped_column(nullable=False, default=False)
    demo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    submission_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="not_submitted"
    )
    readiness_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    members: Mapped[list["Participant"]] = relationship(
        "Participant", back_populates="team", foreign_keys="Participant.team_id"
    )
    track: Mapped[Optional["Track"]] = relationship("Track", back_populates="teams")
    submission: Mapped[Optional["Submission"]] = relationship(
        "Submission", back_populates="team", uselist=False
    )
    issues: Mapped[list["Issue"]] = relationship("Issue", back_populates="team")
    resource_allocations: Mapped[list["ResourceAllocation"]] = relationship(
        "ResourceAllocation", back_populates="team"
    )
