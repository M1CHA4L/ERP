from datetime import datetime
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkOrderStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_no: int
    step_name: str
    requires_inspection: bool
    status: str
    assigned_user_id: UUID | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    actual_start_at: datetime | None
    actual_end_at: datetime | None


class WorkOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    work_order_no: str
    sales_order_id: UUID
    product_name: str
    quantity: float
    route_id: UUID
    status: str
    priority: str
    steps: list[WorkOrderStepRead] = []


class GenerateWorkOrdersRequest(BaseModel):
    route_id: UUID | None = None


class DispatchStepAssignment(BaseModel):
    step_id: UUID
    assigned_user_id: UUID
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None


class DispatchWorkOrderRequest(BaseModel):
    assignments: list[DispatchStepAssignment]


class CompleteStepRequest(BaseModel):
    processed_qty: float
    qualified_qty: float
    defective_qty: float = 0
    work_hours: float | None = None
    remark: str | None = None


class WorkOrderStepTaskRead(BaseModel):
    step_id: UUID
    work_order_id: UUID
    work_order_no: str
    sales_order_id: UUID
    order_no: str
    product_name: str
    quantity: float
    priority: str
    step_no: int
    step_name: str
    status: str
    assigned_user_id: UUID | None
    assigned_user_name: str | None
    planned_start_at: datetime | None
    planned_end_at: datetime | None
    actual_start_at: datetime | None
    actual_end_at: datetime | None
    due_date: date
    is_overdue: bool


class ProcessQueueRead(BaseModel):
    step_name: str
    pending_count: int = 0
    processing_count: int = 0
    pending_inspection_count: int = 0
    reworking_count: int = 0
    overdue_count: int = 0
    total_count: int = 0


class ProductionBoardRead(BaseModel):
    pending_steps: int
    processing_steps: int
    pending_inspection_steps: int
    reworking_steps: int
    unassigned_steps: int
    overdue_steps: int
    due_today_orders: int
    queues: list[ProcessQueueRead]
    active_tasks: list[WorkOrderStepTaskRead]
