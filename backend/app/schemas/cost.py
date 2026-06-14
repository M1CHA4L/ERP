from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CostRecordCreate(BaseModel):
    sales_order_id: UUID
    work_order_id: UUID | None = None
    work_order_step_id: UUID | None = None
    cost_type: str
    amount: float = Field(gt=0)
    cost_date: date
    remark: str | None = None


class CostRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sales_order_id: UUID
    work_order_id: UUID | None
    work_order_step_id: UUID | None
    cost_type: str
    amount: float
    cost_date: date
    remark: str | None


class ProfitReportRow(BaseModel):
    sales_order_id: UUID
    order_no: str
    customer_name: str
    product_summary: str
    order_date: date
    due_date: date
    revenue: float
    total_cost: float
    gross_profit: float
    gross_margin: float


class ProfitReportSummary(BaseModel):
    revenue: float
    total_cost: float
    gross_profit: float
    gross_margin: float


class ProfitReportResponse(BaseModel):
    rows: list[ProfitReportRow]
    summary: ProfitReportSummary


class SalespersonMonthlyRow(BaseModel):
    salesperson: str
    customer_id: UUID
    customer_name: str
    settlement_type: str
    new_pcs: float
    old_pcs: float
    total_amount: float


class CustomerMonthlySalesRow(BaseModel):
    salesperson: str
    customer_id: UUID
    customer_name: str
    settlement_type: str
    pcs: float
    new_pcs: float
    old_pcs: float
    total_amount: float
    price: float


class SalesMonthlySummary(BaseModel):
    new_pcs: float
    old_pcs: float
    total_amount: float


class SalespersonMonthlyReport(BaseModel):
    rows: list[SalespersonMonthlyRow]
    summary: SalesMonthlySummary


class CustomerMonthlySalesReport(BaseModel):
    rows: list[CustomerMonthlySalesRow]
    summary: SalesMonthlySummary
