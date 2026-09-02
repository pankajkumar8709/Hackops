"""MentorAllocation model (stub for Phase 7)."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MentorAllocation(Base):
    """Proposed (not committed) pairing of a mentor to a team issue."""
    __tablename__ = "mentor_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mentor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="proposed"
        # values: "proposed", "accepted", "declined", "timed_out"
    )
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    timed_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reoffer_count: Mapped[int] = mapped_column(nullable=False, default=0)

    mentor: Mapped["Mentor"] = relationship("Mentor", back_populates="allocations")
    issue: Mapped["Issue"] = relationship("Issue", back_populates="mentor_allocations")


from app.models.mentor import Mentor  # noqa: E402
from app.models.issue import Issue  # noqa: E402
