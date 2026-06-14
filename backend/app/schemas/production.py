from datetime import datetime
from datetime import date
from typing import Any
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


class ProductionFlowStepRead(BaseModel):
    step_id: UUID
    step_no: int
    step_name: str
    status: str
    assigned_user_name: str | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    input_qty: float | None = None
    qualified_qty: float | None = None
    defective_qty: float | None = None
    remark: str | None = None


class ProductionFlowProcessRecordRead(BaseModel):
    record_id: UUID
    step_name: str
    operator_name: str | None = None
    action: str
    processed_qty: float | None = None
    qualified_qty: float | None = None
    defective_qty: float | None = None
    work_hours: float | None = None
    reported_at: datetime
    remark: str | None = None


class ProductionFlowInspectionRead(BaseModel):
    inspection_id: UUID
    inspection_no: str
    step_name: str | None = None
    inspector_name: str | None = None
    result: str
    inspected_qty: float
    passed_qty: float | None = None
    failed_qty: float | None = None
    reason: str | None = None
    inspected_at: datetime


class ProductionFlowReworkRead(BaseModel):
    rework_id: UUID
    rework_no: str
    from_step_name: str | None = None
    to_step_name: str | None = None
    reason: str
    quantity: float
    status: str
    completed_at: datetime | None = None


class ProductionFlowRequirementRead(BaseModel):
    engraving_requirement: str | None = None
    proofing_requirement: str | None = None
    inspection_requirement: str | None = None
    color_separation: str | None = None
    computer_requirement: str | None = None
    design_requirement: str | None = None
    production_remark: str | None = None


class ProductionFlowRowRead(BaseModel):
    work_order_id: UUID
    sales_order_id: UUID
    work_order_no: str
    order_no: str
    cylinder_no: str
    salesman: str | None = None
    order_date: date
    due_date: date
    completed_date: date | None = None
    period: str | None = None
    customer_name: str
    product_name: str
    c_value: str | None = None
    l_value: str | None = None
    total_qty: float
    new_base: str | None = None
    old_base: str | None = None
    production_position: str | None = None
    computer_position: str | None = None
    square: str | None = None
    dia: str | None = None
    hole: str | None = None
    slope: str | None = None
    keyway: str | None = None
    single_double: str | None = None
    order_status: str
    work_order_status: str
    current_step_status: str | None = None
    order_by: str | None = None
    sign_in_person: str | None = None
    printing_method: str | None = None
    unit_l: str | None = None
    unit_w: str | None = None
    straight: str | None = None
    increase: str | None = None
    flange: str | None = None
    cylinder_model: str | None = None
    cylinder_making: str | None = None
    material_model: str | None = None
    new_material: str | None = None
    placing_member: str | None = None
    color_numbers: str | None = None
    print_color: str | None = None
    real_dia: str | None = None
    customer_material_qty: str | None = None
    production_qty: str | None = None
    details: dict[str, Any]
