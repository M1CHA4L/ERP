from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Receivable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "receivables"

    receivable_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    delivery_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_orders.id"), nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    received_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    balance_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    due_date: Mapped[date] = mapped_column(Date)
    source_type: Mapped[str] = mapped_column(String(32), default="delivery")
    invoice_status: Mapped[str] = mapped_column(String(32), default="pending")
    finance_status: Mapped[str] = mapped_column(String(32), default="pending_invoice")
    status: Mapped[str] = mapped_column(String(32), default="active")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    invoice_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("receivables.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    invoice_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    payment_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("receivables.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    payment_date: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)


class ReceiptDailyEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "receipt_daily_entries"

    receipt_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    received_date: Mapped[date] = mapped_column(Date, index=True)
    payment_method: Mapped[str] = mapped_column(String(32), default="cash")
    cash_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bank_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    other_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    salesman_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payee_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    abstract: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    allocations: Mapped[list["ReceiptAllocation"]] = relationship(
        back_populates="daily_entry",
        cascade="all, delete-orphan",
    )


class ReceiptAllocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "receipt_allocations"

    daily_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("receipt_daily_entries.id", ondelete="CASCADE"),
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)
    cylinder_no: Mapped[str] = mapped_column(String(64), index=True)
    accounting_month: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    daily_entry: Mapped[ReceiptDailyEntry] = relationship(back_populates="allocations")


class MonthlyPaymentSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "monthly_payment_summaries"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    cylinder_no: Mapped[str] = mapped_column(String(64), index=True)
    accounting_month: Mapped[date] = mapped_column(Date, index=True)
    receivable_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    received_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    due_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class CustomerStatementRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_statement_runs"

    statement_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    statement_month: Mapped[date] = mapped_column(Date, index=True)
    selected_cylinder_nos: Mapped[list] = mapped_column(JSONB, default=list)
    previous_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    current_receivable: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    received_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    due_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class CostRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cost_records"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"))
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=True)
    work_order_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("work_order_steps.id"), nullable=True)
    cost_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    cost_date: Mapped[date] = mapped_column(Date)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_cost_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_records.id"), nullable=True)
