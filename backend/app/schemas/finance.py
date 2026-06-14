from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReceivableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    receivable_no: str
    cylinder_no: str | None = None
    sales_order_id: UUID | None
    delivery_order_id: UUID | None
    customer_id: UUID
    amount: float
    received_amount: float
    balance_amount: float
    due_date: date
    source_type: str
    invoice_status: str
    finance_status: str
    status: str
    remark: str | None = None


class CreateReceivableRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_no: str
    receivable_id: UUID
    customer_id: UUID
    amount: float
    payment_date: date
    payment_method: str | None
    reference_no: str | None
    remark: str | None


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_date: date
    payment_method: Literal["cash", "check", "bank", "bank_check", "other"] = "cash"
    reference_no: str | None = None
    remark: str | None = None


class ReceiptAllocationCreate(BaseModel):
    cylinder_no: str = Field(min_length=1, max_length=64)
    amount: float = Field(gt=0)
    sales_order_id: UUID | None = None
    accounting_month: date | None = None
    remark: str | None = None


class ReceiptAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    daily_entry_id: UUID
    customer_id: UUID
    sales_order_id: UUID | None = None
    cylinder_no: str
    accounting_month: date
    amount: float
    remark: str | None = None


class ReceiptDailyEntryCreate(BaseModel):
    customer_id: UUID
    received_date: date
    payment_method: Literal["cash", "check", "bank", "bank_check", "other"] = "cash"
    cash_amount: float = Field(default=0, ge=0)
    bank_amount: float = Field(default=0, ge=0)
    other_amount: float = Field(default=0, ge=0)
    salesman_name: str | None = None
    payee_name: str | None = None
    abstract: str | None = None
    remark: str | None = None
    allocations: list[ReceiptAllocationCreate] = Field(min_length=1)


class ReceiptDailyEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    receipt_no: str
    customer_id: UUID
    received_date: date
    payment_method: str
    cash_amount: float
    bank_amount: float
    other_amount: float
    total_amount: float
    salesman_name: str | None = None
    payee_name: str | None = None
    abstract: str | None = None
    status: str
    checked_at: datetime | None = None
    checked_by: UUID | None = None
    remark: str | None = None
    allocations: list[ReceiptAllocationRead] = []


class MonthlyPaymentSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    cylinder_no: str
    accounting_month: date
    receivable_amount: float
    received_amount: float
    due_amount: float
    status: str
    calculated_at: datetime | None = None
    remark: str | None = None


class MonthCloseRequest(BaseModel):
    accounting_month: date
    customer_id: UUID | None = None


class CustomerStatementCreate(BaseModel):
    customer_id: UUID
    statement_month: date
    selected_cylinder_nos: list[str] = Field(min_length=1)
    include_previous_balance: bool = True
    remark: str | None = None


class CustomerStatementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    statement_no: str
    customer_id: UUID
    statement_month: date
    selected_cylinder_nos: list[str]
    previous_balance: float
    current_receivable: float
    received_amount: float
    due_amount: float
    status: str
    price_approval_status: str = "pending"
    price_approved_at: datetime | None = None
    price_approved_by: UUID | None = None
    price_approval_remark: str | None = None
    printed_at: datetime | None = None
    remark: str | None = None
