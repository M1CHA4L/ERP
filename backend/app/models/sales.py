from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SalesOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_orders"

    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    legacy_bussiness_mst_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    legacy_bussiness_mst_rid: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    product_summary: Mapped[str] = mapped_column(String(255))
    order_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    route_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("process_routes.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rework_source_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    rework_source_work_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=True)
    rework_source_inspection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inspection_records.id"), nullable=True)
    plate_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    color_rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["SalesOrderItem"]] = relationship(back_populates="sales_order", cascade="all, delete-orphan")


class SalesOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_order_items"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(128))
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(18, 3))
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    route_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("process_routes.id"), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    sales_order: Mapped[SalesOrder] = relationship(back_populates="items")


class EntrustLayoutTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entrust_layout_templates"

    name: Mapped[str] = mapped_column(String(128), index=True)
    template_type: Mapped[str] = mapped_column(String(32), default="template", index=True)
    order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PlateNumberReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plate_number_reservations"

    plate_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(4), index=True)
    year_month: Mapped[str] = mapped_column(String(6), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default="reserved", index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    used_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
