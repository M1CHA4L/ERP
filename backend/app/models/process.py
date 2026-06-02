from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProcessTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "process_templates"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requires_inspection: Mapped[bool] = mapped_column(Boolean, default=False)
    standard_hours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    default_cost_rate: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ProcessRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "process_routes"

    route_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_route_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("process_routes.id"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")

    source_route: Mapped["ProcessRoute | None"] = relationship(remote_side="ProcessRoute.id")

    steps: Mapped[list["ProcessRouteStep"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="ProcessRouteStep.step_no",
    )


class ProcessRouteStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "process_route_steps"
    __table_args__ = (UniqueConstraint("route_id", "step_no", name="uq_route_step_no"),)

    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("process_routes.id", ondelete="CASCADE"))
    process_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("process_templates.id"))
    step_no: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(64))
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_inspection: Mapped[bool] = mapped_column(Boolean, default=False)
    planned_hours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    route: Mapped[ProcessRoute] = relationship(back_populates="steps")
    process_template: Mapped[ProcessTemplate] = relationship()
