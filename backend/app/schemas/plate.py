from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.schemas.finance import MonthlyPaymentSummaryRead
from app.schemas.inventory import CylinderStockRead
from app.schemas.sales import SalesOrderRead


class CylinderLedger(BaseModel):
    cylinder_no: str
    orders: list[SalesOrderRead]
    monthly_receipts: list[MonthlyPaymentSummaryRead]
    stocks: list[CylinderStockRead]


class ProductionOrderPrint(BaseModel):
    order_id: UUID
    order_no: str
    cylinder_no: str | None = None
    print_date: date
    html: str
