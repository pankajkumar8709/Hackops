"""Issue and Notification models — no late circular imports."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Text, Float, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.participant import Participant
    from app.models.team import Team
    from app.models.escalation import Escalation
    from app.models.mentor_allocation import MentorAllocation


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    urgency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    severity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    participant: Mapped[Optional["Participant"]] = relationship("Participant", back_populates="issues")
    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="issues")
    escalation: Mapped[Optional["Escalation"]] = relationship("Escalation", back_populates="issue", uselist=False)
    mentor_allocations: Mapped[list["MentorAllocation"]] = relationship("MentorAllocation", back_populates="issue")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="in_app")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    recipient: Mapped["Participant"] = relationship("Participant", back_populates="notifications")
