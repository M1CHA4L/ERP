from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeliveryOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_orders"

    delivery_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    legacy_order_mst_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    legacy_order_mst_rid: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    legacy_bill_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    address: Mapped[str] = mapped_column(String(255))
    delivery_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    driver_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    logistics_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    signed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["DeliveryOrderItem"]] = relationship(back_populates="delivery_order", cascade="all, delete-orphan")


class DeliveryOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "delivery_order_items"

    delivery_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_orders.id", ondelete="CASCADE"))
    sales_order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_order_items.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(128))
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(18, 3))
    unit: Mapped[str] = mapped_column(String(20), default="pcs")

    delivery_order: Mapped[DeliveryOrder] = relationship(back_populates="items")
