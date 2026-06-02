from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PendingInspectionTask(BaseModel):
    step_id: UUID
    work_order_id: UUID
    work_order_no: str
    product_name: str
    step_no: int
    step_name: str
    quantity: float
    status: str


class InspectionSubmitRequest(BaseModel):
    result: str
    inspected_qty: float
    passed_qty: float | None = None
    failed_qty: float | None = None
    reason: str | None = None
    rework_to_step_id: UUID | None = None


class InspectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inspection_no: str
    sales_order_id: UUID
    work_order_id: UUID
    work_order_step_id: UUID
    inspector_id: UUID
    inspection_type: str
    result: str
    inspected_qty: float
    passed_qty: float | None
    failed_qty: float | None
    reason: str | None
    rework_to_step_id: UUID | None
    inspected_at: datetime
