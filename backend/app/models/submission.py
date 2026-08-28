"""Submission and SubmissionRequirement models."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Float, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    readme_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    demo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_audited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    team: Mapped["Team"] = relationship("Team", back_populates="submission")


class SubmissionRequirement(Base):
    """Per-track required fields for a submission (deterministic audit logic reads these)."""
    __tablename__ = "submission_requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "repo_url", "demo_url", "description", "readme_url"
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    track: Mapped["Track"] = relationship("Track", back_populates="submission_requirements")


from app.models.team import Team  # noqa: E402
from app.models.event import Track  # noqa: E402
