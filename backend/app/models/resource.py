"""ResourceItem and ResourceAllocation models."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ResourceItem(Base):
    """A pool of a specific resource type (e.g. API keys, hardware kits)."""
    __tablename__ = "resource_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False
        # e.g. "api_key", "hardware_kit"
    )
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    allocations: Mapped[list["ResourceAllocation"]] = relationship(
        "ResourceAllocation", back_populates="resource_item"
    )


class ResourceAllocation(Base):
    """Records which team holds which resource unit, and when."""
    __tablename__ = "resource_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resource_items.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="allocated"
        # values: "allocated", "returned", "overdue"
    )
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resource_item: Mapped["ResourceItem"] = relationship("ResourceItem", back_populates="allocations")
    team: Mapped["Team"] = relationship("Team", back_populates="resource_allocations")


from app.models.team import Team  # noqa: E402
