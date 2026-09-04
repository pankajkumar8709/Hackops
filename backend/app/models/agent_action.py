"""AgentAction model — explainability log for every autonomous action."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action_type: Mapped[str] = mapped_column(
        String(100), nullable=False
        # e.g. "send_notification", "create_escalation", "propose_mentor",
        #       "allocate_resource", "re_audit_submission"
    )
    # Snapshot of the state that triggered this action (JSON string)
    trigger_state_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Human-readable explanation of why this action was taken
    reasoning_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which policy rule allowed/blocked this action
    policy_check_result: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Outcome of the action
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Plain-language one-line summary for the dashboard feed / bot output
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nullable FKs — points to whichever entity this action touched
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="SET NULL"), nullable=True
    )
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True
    )
    escalation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("escalations.id", ondelete="SET NULL"), nullable=True
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
