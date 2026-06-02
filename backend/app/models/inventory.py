from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InventoryLot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_lots"

    lot_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    owner_type: Mapped[str] = mapped_column(String(32), default="company", index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), default="Main")
    supplier_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_name: Mapped[str] = mapped_column(String(128), index=True)
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    quantity_on_hand: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    status: Mapped[str] = mapped_column(String(32), default="available", index=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class InventoryTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_transactions"

    movement_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(32), index=True)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_lots.id"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=True)
    cylinder_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), default="Main")
    supplier_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_name: Mapped[str] = mapped_column(String(128))
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="pcs")
    quantity: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    movement_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(32), default="checked", index=True)
    handler_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class CylinderStock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cylinder_stocks"

    stock_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    cylinder_no: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    warehouse_name: Mapped[str] = mapped_column(String(128), default="Cylinder Warehouse")
    diameter: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    cylinder_length: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    hole: Mapped[str | None] = mapped_column(String(64), nullable=True)
    area_cm2: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    quantity: Mapped[float] = mapped_column(Numeric(18, 3), default=1)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    stock_status: Mapped[str] = mapped_column(String(32), default="in_stock", index=True)
    stock_in_date: Mapped[date] = mapped_column(Date, index=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
