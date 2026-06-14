from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.rbac import User


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    customer_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    legacy_company_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    customer_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_key_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salesperson_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    payment_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    minimum_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    vat_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ait_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    advance_percent: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    lister: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    credit_limit: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    office: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opening_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    copper_thickness: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    chrome_time: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    stripping_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    reconciliation_cycle: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reconciliation_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")

    salesperson: Mapped[User | None] = relationship()

    @property
    def salesperson_name(self) -> str | None:
        if not self.salesperson:
            return None
        return self.salesperson.real_name or self.salesperson.username
