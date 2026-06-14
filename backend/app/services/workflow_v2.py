from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.models.sales import SalesOrder
from app.models.workflow_v2 import (
    AbnormalProcessRecord,
    EpinBatch,
    MakingAssignment,
    OrderWorkflow,
    OrderWorkflowNode,
    ProductionTask,
    WorkflowEdge,
    WorkflowNode,
    WorkflowTemplate,
)

DEFAULT_TEMPLATE_CODE = "normal_parallel_v2"
DEFAULT_TEMPLATE_NAME = "正常生产双线并行工作流程"
JOIN_NODE_CODE = "join_before_engraving"
EPIN_NODE_CODE = "epin"
COPPER_GRIND_NODE_CODE = "copper_grinding"
MAKING_DISPATCH_NODE_CODE = "making_dispatch"
MAKING_EMPLOYEE_NODE_CODE = "making_employee_task"
FORBIDDEN_ABNORMAL_PROCESS_NODES = {"delivery", "sign", "completed"}


@dataclass(frozen=True)
class JoinCheck:
    ready: bool
    waiting_for: list[str]
    epin_completed: bool
    copper_grind_completed: bool


DEFAULT_NODES: tuple[dict, ...] = (
    {"code": "formal_order", "name": "正式下单", "type": "start", "department": "业务", "sort": 10},
    {
        "code": MAKING_DISPATCH_NODE_CODE,
        "name": "制作主管派工",
        "type": "dispatch",
        "department": "制作",
        "branch": "making",
        "parallel": True,
        "sort": 20,
        "permission": "workflow_v2:making:assign",
    },
    {
        "code": MAKING_EMPLOYEE_NODE_CODE,
        "name": "制作员工任务",
        "type": "task",
        "department": "制作",
        "branch": "making",
        "parallel": True,
        "sort": 30,
    },
    {"code": EPIN_NODE_CODE, "name": "电拼", "type": "task", "department": "电拼", "branch": "making", "parallel": True, "sort": 40},
    {"code": "roll_bending", "name": "卷板", "type": "task", "department": "卷板", "branch": "processing", "parallel": True, "sort": 50},
    {"code": "flange_plate", "name": "法兰 / 法版", "type": "task", "department": "法版", "branch": "processing", "parallel": True, "sort": 60},
    {"code": "lathe", "name": "车床", "type": "task", "department": "车床", "branch": "processing", "parallel": True, "sort": 70},
    {"code": "basic_grinding", "name": "基磨 / 磨床", "type": "task", "department": "磨床", "branch": "processing", "parallel": True, "sort": 80},
    {"code": "copper_plating", "name": "镀铜", "type": "task", "department": "镀铜", "branch": "processing", "parallel": True, "sort": 90},
    {
        "code": COPPER_GRIND_NODE_CODE,
        "name": "铜磨 / 研磨",
        "type": "task",
        "department": "研磨",
        "branch": "processing",
        "parallel": True,
        "sort": 100,
    },
    {
        "code": JOIN_NODE_CODE,
        "name": "汇合等待",
        "type": "join",
        "department": "生产",
        "join": True,
        "sort": 110,
        "permission": "workflow_v2:join:release",
    },
    {"code": "engraving", "name": "电雕 / 雕刻", "type": "task", "department": "雕刻", "sort": 120},
    {"code": "chrome_plating", "name": "镀铬", "type": "task", "department": "镀铬", "sort": 130},
    {"code": "proofing", "name": "打样", "type": "task", "department": "打样", "sort": 140},
    {"code": "inspection", "name": "检验", "type": "task", "department": "检验", "sort": 150},
    {"code": "finance_bill", "name": "财务打印 Bill / 送货单", "type": "finance", "department": "财务", "sort": 160},
    {"code": "delivery", "name": "送货", "type": "delivery", "department": "送货", "sort": 170},
    {"code": "sign", "name": "签收", "type": "sign", "department": "送货", "sort": 180},
    {"code": "completed", "name": "订单完成", "type": "end", "department": "业务", "sort": 190},
)

DEFAULT_EDGES: tuple[tuple[str, str, str, str | None], ...] = (
    ("formal_order", MAKING_DISPATCH_NODE_CODE, "always", None),
    ("formal_order", "roll_bending", "always", None),
    (MAKING_DISPATCH_NODE_CODE, MAKING_EMPLOYEE_NODE_CODE, "always", None),
    (MAKING_EMPLOYEE_NODE_CODE, EPIN_NODE_CODE, "always", None),
    ("roll_bending", "flange_plate", "always", None),
    ("flange_plate", "lathe", "always", None),
    ("lathe", "basic_grinding", "always", None),
    ("basic_grinding", "copper_plating", "always", None),
    ("copper_plating", COPPER_GRIND_NODE_CODE, "always", None),
    (EPIN_NODE_CODE, JOIN_NODE_CODE, "all_success", None),
    (COPPER_GRIND_NODE_CODE, JOIN_NODE_CODE, "all_success", None),
    (JOIN_NODE_CODE, "engraving", "always", None),
    ("engraving", "chrome_plating", "always", None),
    ("chrome_plating", "proofing", "always", None),
    ("proofing", "inspection", "always", None),
    ("inspection", "finance_bill", "always", None),
    ("finance_bill", "delivery", "always", None),
    ("delivery", "sign", "always", None),
    ("sign", "completed", "always", None),
)


def seed_default_parallel_workflow_template(db: Session) -> WorkflowTemplate:
    template = (
        db.query(WorkflowTemplate)
        .options(selectinload(WorkflowTemplate.nodes), selectinload(WorkflowTemplate.edges))
        .filter(WorkflowTemplate.template_code == DEFAULT_TEMPLATE_CODE)
        .first()
    )
    if template is not None:
        if template.template_name != DEFAULT_TEMPLATE_NAME:
            template.template_name = DEFAULT_TEMPLATE_NAME
        return template

    template = WorkflowTemplate(
        template_code=DEFAULT_TEMPLATE_CODE,
        template_name=DEFAULT_TEMPLATE_NAME,
        template_type="normal",
        version=1,
        is_default=True,
        is_active=True,
    )
    db.add(template)
    db.flush()

    nodes_by_code: dict[str, WorkflowNode] = {}
    for item in DEFAULT_NODES:
        node = WorkflowNode(
            template_id=template.id,
            node_code=item["code"],
            node_name=item["name"],
            department=item.get("department"),
            node_type=item["type"],
            sort_order=item["sort"],
            branch_code=item.get("branch"),
            is_parallel_node=bool(item.get("parallel", False)),
            is_join_node=bool(item.get("join", False)),
            is_required=True,
            allow_skip=False,
            required_permission=item.get("permission"),
        )
        db.add(node)
        nodes_by_code[node.node_code] = node
    db.flush()

    for from_code, to_code, condition_type, expression in DEFAULT_EDGES:
        db.add(
            WorkflowEdge(
                template_id=template.id,
                from_node_id=nodes_by_code[from_code].id,
                to_node_id=nodes_by_code[to_code].id,
                condition_type=condition_type,
                condition_expression=expression,
            )
        )
    db.flush()
    db.refresh(template)
    return template


def get_default_template(db: Session) -> WorkflowTemplate:
    template = (
        db.query(WorkflowTemplate)
        .options(selectinload(WorkflowTemplate.nodes), selectinload(WorkflowTemplate.edges))
        .filter(
            WorkflowTemplate.template_type == "normal",
            WorkflowTemplate.is_default.is_(True),
            WorkflowTemplate.is_active.is_(True),
        )
        .order_by(WorkflowTemplate.version.desc())
        .first()
    )
    if template is None:
        template = seed_default_parallel_workflow_template(db)
    return template


def get_workflow_for_order(db: Session, sales_order_id: UUID) -> OrderWorkflow:
    workflow = (
        db.query(OrderWorkflow)
        .options(selectinload(OrderWorkflow.nodes), selectinload(OrderWorkflow.template).selectinload(WorkflowTemplate.edges))
        .filter(OrderWorkflow.sales_order_id == sales_order_id, OrderWorkflow.deleted_at.is_(None))
        .first()
    )
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found for this order.")
    return workflow


def start_workflow_for_order(db: Session, sales_order: SalesOrder, template_id: UUID | None = None) -> OrderWorkflow:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"workflow_v2:{sales_order.id}"},
    )
    existing = db.query(OrderWorkflow).filter(OrderWorkflow.sales_order_id == sales_order.id, OrderWorkflow.deleted_at.is_(None)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workflow already exists for this order.")

    if template_id is None:
        template = get_default_template(db)
    else:
        template = (
            db.query(WorkflowTemplate)
            .options(selectinload(WorkflowTemplate.nodes), selectinload(WorkflowTemplate.edges))
            .filter(WorkflowTemplate.id == template_id, WorkflowTemplate.is_active.is_(True))
            .first()
        )
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow template not found.")

    now = datetime.now(timezone.utc)
    workflow = OrderWorkflow(sales_order_id=sales_order.id, template_id=template.id, status="running", started_at=now)
    db.add(workflow)
    db.flush()

    for template_node in template.nodes:
        node_status = "completed" if template_node.node_type == "start" else "pending"
        workflow_node = OrderWorkflowNode(
            order_workflow_id=workflow.id,
            sales_order_id=sales_order.id,
            node_id=template_node.id,
            node_code=template_node.node_code,
            node_name=template_node.node_name,
            department=template_node.department,
            node_type=template_node.node_type,
            branch_code=template_node.branch_code,
            sort_order=template_node.sort_order,
            status=node_status,
            completed_at=now if node_status == "completed" else None,
            is_current=False,
        )
        db.add(workflow_node)
    sales_order.status = "in_production"
    db.flush()
    _advance_ready_nodes(db, workflow)
    db.flush()
    db.refresh(workflow)
    return get_workflow_for_order(db, sales_order.id)


def start_node(db: Session, node: OrderWorkflowNode, assigned_user_id: UUID | None = None, remarks: str | None = None) -> OrderWorkflowNode:
    if node.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only active workflow nodes can be started.")
    node.status = "in_progress"
    node.started_at = datetime.now(timezone.utc)
    node.assigned_user_id = assigned_user_id or node.assigned_user_id
    node.remarks = remarks or node.remarks
    _sync_task_from_node(db, node)
    db.flush()
    return node


def complete_node(db: Session, node: OrderWorkflowNode, remarks: str | None = None) -> OrderWorkflowNode:
    if node.status not in {"active", "in_progress", "waiting"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only active, in-progress, or waiting nodes can be completed.")
    if node.node_type == "join":
        join = check_join(db, node.sales_order_id)
        if not join.ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "WORKFLOW_JOIN_NOT_READY",
                    "waiting_for": join.waiting_for,
                    "epin_completed": join.epin_completed,
                    "copper_grind_completed": join.copper_grind_completed,
                },
            )
    _mark_node_completed(db, node, remarks=remarks)
    workflow = get_workflow_for_order(db, node.sales_order_id)
    _advance_ready_nodes(db, workflow)
    db.flush()
    return node


def check_join(db: Session, sales_order_id: UUID) -> JoinCheck:
    workflow = get_workflow_for_order(db, sales_order_id)
    nodes = {node.node_code: node for node in workflow.nodes}
    epin_completed = nodes.get(EPIN_NODE_CODE) is not None and nodes[EPIN_NODE_CODE].status == "completed"
    copper_completed = nodes.get(COPPER_GRIND_NODE_CODE) is not None and nodes[COPPER_GRIND_NODE_CODE].status == "completed"
    waiting_for: list[str] = []
    if not epin_completed:
        waiting_for.append("电拼")
    if not copper_completed:
        waiting_for.append("铜磨 / 研磨")
    return JoinCheck(
        ready=epin_completed and copper_completed,
        waiting_for=waiting_for,
        epin_completed=epin_completed,
        copper_grind_completed=copper_completed,
    )


def create_making_assignments(
    db: Session,
    *,
    sales_order: SalesOrder,
    supervisor_id: UUID,
    assignments: list[tuple[UUID, float, str | None]],
    allow_over_assign: bool = False,
) -> list[MakingAssignment]:
    workflow = get_workflow_for_order(db, sales_order.id)
    dispatch_node = _node_by_code(workflow, MAKING_DISPATCH_NODE_CODE)
    if dispatch_node.status not in {"active", "in_progress"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Making dispatch node is not active.")

    order_qty = _sales_order_quantity(sales_order)
    already_assigned = sum(float(item.assigned_sets) for item in db.query(MakingAssignment).filter(MakingAssignment.sales_order_id == sales_order.id).all())
    new_total = sum(item[1] for item in assignments)
    total_assigned = already_assigned + new_total
    if not allow_over_assign and total_assigned > order_qty:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned sets cannot exceed order quantity.")

    task = _ensure_production_task(db, dispatch_node)
    created: list[MakingAssignment] = []
    for employee_id, assigned_sets, remarks in assignments:
        assignment = MakingAssignment(
            sales_order_id=sales_order.id,
            making_task_id=task.id,
            supervisor_id=supervisor_id,
            employee_id=employee_id,
            assigned_sets=assigned_sets,
            completed_sets=0,
            status="assigned",
            remarks=remarks,
        )
        db.add(assignment)
        created.append(assignment)

    if order_qty > 0 and total_assigned >= order_qty:
        _mark_node_completed(db, dispatch_node, remarks="制作派工已完成")
        workflow = get_workflow_for_order(db, sales_order.id)
        _advance_ready_nodes(db, workflow)
    elif dispatch_node.status == "active":
        dispatch_node.status = "in_progress"
        dispatch_node.started_at = datetime.now(timezone.utc)
    db.flush()
    return created


def complete_making_assignment(db: Session, assignment: MakingAssignment, completed_sets: float, remarks: str | None = None) -> MakingAssignment:
    total_completed = float(assignment.completed_sets) + completed_sets
    if total_completed > float(assignment.assigned_sets):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Completed sets cannot exceed assigned sets.")
    assignment.completed_sets = total_completed
    assignment.remarks = remarks or assignment.remarks
    assignment.status = "completed" if total_completed == float(assignment.assigned_sets) else "processing"
    db.flush()
    return assignment


def submit_making_assignment_to_epin(db: Session, assignment: MakingAssignment) -> EpinBatch:
    if float(assignment.completed_sets) <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nothing completed to submit to epin.")
    if assignment.submitted_to_epin_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assignment already submitted to epin.")

    now = datetime.now(timezone.utc)
    assignment.submitted_to_epin_at = now
    assignment.status = "submitted"
    batch = EpinBatch(
        sales_order_id=assignment.sales_order_id,
        making_assignment_id=assignment.id,
        employee_id=assignment.employee_id,
        sets_count=assignment.completed_sets,
        status="submitted",
    )
    db.add(batch)
    _complete_making_employee_node_if_ready(db, assignment.sales_order_id)
    db.flush()
    return batch


def receive_epin_batch(db: Session, batch: EpinBatch, user_id: UUID) -> EpinBatch:
    if batch.status != "submitted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted epin batches can be received.")
    batch.status = "received"
    batch.received_by = user_id
    batch.received_at = datetime.now(timezone.utc)
    db.flush()
    return batch


def complete_epin_batch(db: Session, batch: EpinBatch, remarks: str | None = None) -> EpinBatch:
    if batch.status not in {"submitted", "received", "processing"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Epin batch cannot be completed from current status.")
    batch.status = "completed"
    batch.completed_at = datetime.now(timezone.utc)
    batch.remarks = remarks or batch.remarks
    _complete_epin_node_if_ready(db, batch.sales_order_id)
    db.flush()
    return batch


def approve_abnormal_process_record(db: Session, record: AbnormalProcessRecord, approved_by: UUID) -> AbnormalProcessRecord:
    if record.status != "pending_approval":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending abnormal records can be approved.")

    workflow = get_workflow_for_order(db, record.sales_order_id)
    nodes_by_code = {node.node_code: node for node in workflow.nodes}
    selected_codes = _unique_node_codes([record.selected_start_node, *record.selected_process_nodes])
    missing_nodes = [node_code for node_code in selected_codes if node_code not in nodes_by_code]
    if missing_nodes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Workflow nodes not found: {', '.join(missing_nodes)}",
        )

    illegal_nodes = [
        node_code
        for node_code in selected_codes
        if node_code in FORBIDDEN_ABNORMAL_PROCESS_NODES or nodes_by_code[node_code].node_type in {"start", "end"}
    ]
    if illegal_nodes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nodes cannot be reopened for abnormal processing: {', '.join(sorted(illegal_nodes))}",
        )

    workflow.status = "running"
    workflow.completed_at = None
    record.status = "processing"
    record.approved_by = approved_by
    for node_code in selected_codes:
        _reopen_workflow_node_for_abnormal(db, nodes_by_code[node_code], record.reason)
    db.flush()
    return record


def reject_abnormal_process_record(db: Session, record: AbnormalProcessRecord, approved_by: UUID) -> AbnormalProcessRecord:
    if record.status != "pending_approval":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending abnormal records can be rejected.")
    record.status = "rejected"
    record.approved_by = approved_by
    db.flush()
    return record


def complete_abnormal_process_record(db: Session, record: AbnormalProcessRecord) -> AbnormalProcessRecord:
    if record.status != "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only processing abnormal records can be completed.")

    workflow = get_workflow_for_order(db, record.sales_order_id)
    nodes_by_code = {node.node_code: node for node in workflow.nodes}
    selected_codes = _unique_node_codes([record.selected_start_node, *record.selected_process_nodes])
    waiting_nodes = [
        nodes_by_code[node_code].node_name
        for node_code in selected_codes
        if node_code in nodes_by_code and nodes_by_code[node_code].status != "completed"
    ]
    if waiting_nodes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ABNORMAL_REWORK_NOT_DONE", "waiting_for": waiting_nodes},
        )

    record.status = "completed"
    db.flush()
    return record


def _advance_ready_nodes(db: Session, workflow: OrderWorkflow) -> None:
    changed = True
    while changed:
        changed = False
        workflow = get_workflow_for_order(db, workflow.sales_order_id)
        for node in workflow.nodes:
            if node.status not in {"pending", "waiting"}:
                continue
            if _is_node_ready(workflow, node):
                if node.node_type == "join":
                    node.status = "active"
                    node.is_current = True
                    node.waiting_reason = None
                    _ensure_production_task(db, node)
                    changed = True
                    continue
                if node.node_type == "end":
                    _mark_node_completed(db, node)
                    workflow.status = "completed"
                    workflow.completed_at = datetime.now(timezone.utc)
                    changed = True
                    continue
                node.status = "active"
                node.is_current = True
                node.waiting_reason = None
                _ensure_production_task(db, node)
                changed = True
            elif node.node_type == "join" and _has_any_completed_predecessor(workflow, node):
                waiting = _waiting_predecessor_names(workflow, node)
                node.status = "waiting"
                node.is_current = True
                node.waiting_reason = f"等待：{'、'.join(waiting)}" if waiting else None
    db.flush()


def _mark_node_completed(db: Session, node: OrderWorkflowNode, remarks: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    node.status = "completed"
    node.completed_at = node.completed_at or now
    node.started_at = node.started_at or now
    node.is_current = False
    node.waiting_reason = None
    node.remarks = remarks or node.remarks
    task = (
        db.query(ProductionTask)
        .filter(ProductionTask.workflow_node_instance_id == node.id, ProductionTask.deleted_at.is_(None))
        .first()
    )
    if task is not None:
        task.task_status = "completed"
        task.completed_at = task.completed_at or now


def _sync_task_from_node(db: Session, node: OrderWorkflowNode) -> None:
    task = _ensure_production_task(db, node)
    task.task_status = "processing"
    task.assigned_user_id = node.assigned_user_id
    task.started_at = task.started_at or node.started_at


def _ensure_production_task(db: Session, node: OrderWorkflowNode) -> ProductionTask:
    task = (
        db.query(ProductionTask)
        .filter(ProductionTask.workflow_node_instance_id == node.id, ProductionTask.deleted_at.is_(None))
        .first()
    )
    if task is None:
        task = ProductionTask(
            sales_order_id=node.sales_order_id,
            workflow_node_instance_id=node.id,
            department=node.department,
            assigned_user_id=node.assigned_user_id,
            task_status="pending",
            planned_num=0,
            completed_num=0,
            bad_num=0,
        )
        db.add(task)
        db.flush()
    return task


def _reopen_workflow_node_for_abnormal(db: Session, node: OrderWorkflowNode, reason: str) -> None:
    node.status = "active"
    node.started_at = None
    node.completed_at = None
    node.is_current = True
    node.waiting_reason = None
    node.remarks = f"异常返工：{reason}"
    task = _ensure_production_task(db, node)
    task.task_status = "pending"
    task.started_at = None
    task.completed_at = None
    task.remarks = node.remarks


def _unique_node_codes(node_codes: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for node_code in node_codes:
        if node_code in seen:
            continue
        seen.add(node_code)
        result.append(node_code)
    return result


def _incoming_edges(workflow: OrderWorkflow, node: OrderWorkflowNode) -> list[WorkflowEdge]:
    return [edge for edge in workflow.template.edges if edge.to_node_id == node.node_id]


def _predecessor_instances(workflow: OrderWorkflow, node: OrderWorkflowNode) -> list[OrderWorkflowNode]:
    instances = {item.node_id: item for item in workflow.nodes}
    return [instances[edge.from_node_id] for edge in _incoming_edges(workflow, node) if edge.from_node_id in instances]


def _is_node_ready(workflow: OrderWorkflow, node: OrderWorkflowNode) -> bool:
    incoming = _incoming_edges(workflow, node)
    if not incoming:
        return False
    predecessors = _predecessor_instances(workflow, node)
    if not predecessors:
        return False
    if any(edge.condition_type == "any_success" for edge in incoming):
        return any(item.status == "completed" for item in predecessors)
    return all(item.status == "completed" for item in predecessors)


def _has_any_completed_predecessor(workflow: OrderWorkflow, node: OrderWorkflowNode) -> bool:
    return any(item.status == "completed" for item in _predecessor_instances(workflow, node))


def _waiting_predecessor_names(workflow: OrderWorkflow, node: OrderWorkflowNode) -> list[str]:
    return [item.node_name for item in _predecessor_instances(workflow, node) if item.status != "completed"]


def _node_by_code(workflow: OrderWorkflow, node_code: str) -> OrderWorkflowNode:
    for node in workflow.nodes:
        if node.node_code == node_code:
            return node
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow node {node_code} not found.")


def _sales_order_quantity(sales_order: SalesOrder) -> float:
    if sales_order.items:
        return sum(float(item.quantity) for item in sales_order.items)
    details = sales_order.plate_details or {}
    for key in ("total_qty", "num", "new_qty", "production_qty"):
        value = details.get(key)
        if value is not None:
            try:
                return float(str(value).replace(",", "").strip())
            except ValueError:
                continue
    return 0


def _complete_making_employee_node_if_ready(db: Session, sales_order_id: UUID) -> None:
    workflow = get_workflow_for_order(db, sales_order_id)
    employee_node = _node_by_code(workflow, MAKING_EMPLOYEE_NODE_CODE)
    if employee_node.status not in {"active", "in_progress"}:
        return
    assignments = db.query(MakingAssignment).filter(MakingAssignment.sales_order_id == sales_order_id).all()
    if assignments and all(item.submitted_to_epin_at is not None for item in assignments):
        _mark_node_completed(db, employee_node)
        _advance_ready_nodes(db, workflow)


def _complete_epin_node_if_ready(db: Session, sales_order_id: UUID) -> None:
    workflow = get_workflow_for_order(db, sales_order_id)
    epin_node = _node_by_code(workflow, EPIN_NODE_CODE)
    if epin_node.status not in {"active", "in_progress"}:
        return
    batches = db.query(EpinBatch).filter(EpinBatch.sales_order_id == sales_order_id).all()
    if batches and all(batch.status == "completed" for batch in batches):
        _mark_node_completed(db, epin_node)
        _advance_ready_nodes(db, workflow)
