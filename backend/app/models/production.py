from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_orders"

    work_order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"))
    sales_order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_order_items.id"), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[float] = mapped_column(Numeric(18, 3))
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("process_routes.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending_schedule", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["WorkOrderStep"]] = relationship(
        back_populates="work_order",
        cascade="all, delete-orphan",
        order_by="WorkOrderStep.step_no",
    )


class WorkOrderStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_order_steps"

    work_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id", ondelete="CASCADE"))
    process_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("process_templates.id"), nullable=True)
    step_no: Mapped[int] = mapped_column()
    step_name: Mapped[str] = mapped_column(String(64))
    requires_inspection: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    qualified_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    defective_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    is_skipped: Mapped[bool] = mapped_column(default=False)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    work_order: Mapped[WorkOrder] = relationship(back_populates="steps")


class ProcessRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "process_records"

    work_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"))
    work_order_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_order_steps.id"))
    operator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    processed_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    qualified_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    defective_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    work_hours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("process_records.id"), nullable=True)


class InspectionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inspection_records"

    inspection_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"))
    work_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"))
    work_order_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_order_steps.id"))
    inspector_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    inspection_type: Mapped[str] = mapped_column(String(32), default="final")
    result: Mapped[str] = mapped_column(String(32))
    inspected_qty: Mapped[float] = mapped_column(Numeric(18, 3))
    passed_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    failed_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rework_to_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_order_steps.id"), nullable=True)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReworkRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rework_records"

    rework_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    inspection_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inspection_records.id"))
    work_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"))
    rework_sales_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    from_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_order_steps.id"))
    to_step_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_order_steps.id"))
    reason: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Numeric(18, 3))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
