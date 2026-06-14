from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PreOrderCreate(BaseModel):
    sample_no: str
    customer_id: UUID | None = None
    customer_name: str
    product_name: str
    type: str | None = None
    order_time: datetime | None = None
    salesperson_id: UUID | None = None
    num: float = Field(gt=0)
    receiver_id: UUID | None = None
    print_color: str | None = None
    remarks: str | None = None


class PreOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pre_order_no: str
    sample_no: str
    customer_id: UUID | None
    customer_name: str
    product_name: str
    type: str | None
    order_time: datetime
    salesperson_id: UUID | None
    num: float
    receiver_id: UUID | None
    print_color: str | None
    remarks: str | None
    status: str
    customer_confirmed_at: datetime | None
    converted_order_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ConvertPreOrderRequest(BaseModel):
    customer_id: UUID | None = None
    due_date: date
    priority: str = "normal"
    unit_price: float = Field(default=0, ge=0)
    route_id: UUID | None = None


class WorkflowTemplateNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_code: str
    node_name: str
    department: str | None
    node_type: str
    sort_order: int
    branch_code: str | None
    is_parallel_node: bool
    is_join_node: bool
    is_required: bool
    allow_skip: bool
    required_permission: str | None


class WorkflowTemplateEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_node_id: UUID
    to_node_id: UUID
    condition_type: str
    condition_expression: str | None


class WorkflowTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_code: str
    template_name: str
    template_type: str
    version: int
    is_default: bool
    is_active: bool
    nodes: list[WorkflowTemplateNodeRead] = []
    edges: list[WorkflowTemplateEdgeRead] = []


class WorkflowStartRequest(BaseModel):
    template_id: UUID | None = None


class WorkflowNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_workflow_id: UUID
    sales_order_id: UUID
    node_id: UUID
    node_code: str
    node_name: str
    department: str | None
    node_type: str
    branch_code: str | None
    sort_order: int
    status: str
    assigned_user_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    waiting_reason: str | None
    is_current: bool
    remarks: str | None


class WorkflowEdgeGraphRead(BaseModel):
    from_node_code: str
    to_node_code: str
    condition_type: str
    condition_expression: str | None = None


class WorkflowGraphRead(BaseModel):
    workflow_id: UUID
    sales_order_id: UUID
    template_id: UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    nodes: list[WorkflowNodeRead]
    edges: list[WorkflowEdgeGraphRead]


class WorkflowNodeActionRequest(BaseModel):
    remarks: str | None = None
    assigned_user_id: UUID | None = None
    bill_no: str | None = None
    delivery_note_no: str | None = None
    bill_amount: float | None = Field(default=None, ge=0)
    delivery_time: datetime | None = None
    delivery_person: str | None = None
    logistics: str | None = None
    delivery_address: str | None = None
    signer: str | None = None
    signed_at: datetime | None = None
    sign_proof_no: str | None = None


class WorkflowFinanceBillSummary(BaseModel):
    id: UUID
    bill_no: str
    amount: float | None = None
    bill_status: str
    printed_at: datetime | None = None
    released_at: datetime | None = None
    remarks: str | None = None


class WorkflowDeliverySummary(BaseModel):
    id: UUID
    delivery_no: str
    status: str
    address: str
    delivery_time: datetime
    driver_name: str | None = None
    logistics_no: str | None = None
    signed_by: str | None = None
    signed_at: datetime | None = None
    remark: str | None = None


class WorkflowSignSummary(BaseModel):
    id: UUID
    signed_by: str
    signed_at: datetime
    remarks: str | None = None


class WorkflowFulfillmentSummary(BaseModel):
    sales_order_id: UUID
    bill: WorkflowFinanceBillSummary | None = None
    delivery: WorkflowDeliverySummary | None = None
    sign: WorkflowSignSummary | None = None
    current_stage: str
    can_view_amount: bool = False


class JoinCheckRead(BaseModel):
    ready: bool
    join_node_code: str
    waiting_for: list[str]
    epin_completed: bool
    copper_grind_completed: bool


class MakingAssignmentItem(BaseModel):
    employee_id: UUID
    assigned_sets: float = Field(gt=0)
    remarks: str | None = None


class MakingAssignmentCreate(BaseModel):
    assignments: list[MakingAssignmentItem]
    allow_over_assign: bool = False


class MakingAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sales_order_id: UUID
    making_task_id: UUID | None
    supervisor_id: UUID
    employee_id: UUID
    assigned_sets: float
    completed_sets: float
    status: str
    submitted_to_epin_at: datetime | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class MakingCompleteRequest(BaseModel):
    completed_sets: float = Field(gt=0)
    remarks: str | None = None


class EpinBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sales_order_id: UUID
    making_assignment_id: UUID
    employee_id: UUID
    sets_count: float
    status: str
    received_by: UUID | None
    received_at: datetime | None
    completed_at: datetime | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class AbnormalFlowCreate(BaseModel):
    abnormal_type: str
    reason: str
    selected_start_node: str
    selected_process_nodes: list[str]
    need_inspection: bool = True
    need_finance_bill: bool = False
    need_delivery: bool = False


class AbnormalFlowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sales_order_id: UUID
    abnormal_type: str
    reason: str
    selected_start_node: str
    selected_process_nodes: list[str]
    need_inspection: bool
    need_finance_bill: bool
    need_delivery: bool
    initiated_by: UUID
    approved_by: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
