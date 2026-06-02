from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.production import ProcessRecord, WorkOrder, WorkOrderStep
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.common import PageResponse
from app.schemas.production import (
    CompleteStepRequest,
    DispatchWorkOrderRequest,
    ProcessQueueRead,
    ProductionBoardRead,
    WorkOrderRead,
    WorkOrderStepTaskRead,
)
from app.schemas.timeline import TimelineItem
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.state_machine import FINISHED_STEP_STATUSES, StepStatus, WorkOrderStatus, can_start_step, next_status_after_complete
from app.services.timeline import build_sales_order_timeline

router = APIRouter()

ACTIVE_STEP_STATUSES = (
    StepStatus.PENDING_PROCESS,
    StepStatus.PROCESSING,
    StepStatus.PENDING_INSPECTION,
    StepStatus.INSPECTION_FAILED,
    StepStatus.REWORKING,
)


def is_step_overdue(step: WorkOrderStep, sales_order: SalesOrder, today: date) -> bool:
    if step.planned_end_at:
        return step.planned_end_at.date() < today
    return sales_order.due_date < today


def build_step_task(
    step: WorkOrderStep,
    work_order: WorkOrder,
    sales_order: SalesOrder,
    assigned_user: User | None,
    today: date,
) -> WorkOrderStepTaskRead:
    return WorkOrderStepTaskRead(
        step_id=step.id,
        work_order_id=work_order.id,
        work_order_no=work_order.work_order_no,
        sales_order_id=sales_order.id,
        order_no=sales_order.order_no,
        product_name=work_order.product_name,
        quantity=float(work_order.quantity),
        priority=work_order.priority,
        step_no=step.step_no,
        step_name=step.step_name,
        status=step.status,
        assigned_user_id=step.assigned_user_id,
        assigned_user_name=assigned_user.real_name if assigned_user else None,
        planned_start_at=step.planned_start_at,
        planned_end_at=step.planned_end_at,
        actual_start_at=step.actual_start_at,
        actual_end_at=step.actual_end_at,
        due_date=sales_order.due_date,
        is_overdue=is_step_overdue(step, sales_order, today),
    )


def _can_view_all_work_orders(user: User) -> bool:
    privileged_roles = {"admin", "boss", "sales", "designer", "production_manager", "inspector"}
    return "work_order:dispatch" in user.permission_codes or any(role.code in privileged_roles for role in user.roles)


def _restrict_work_orders_to_user(query, user: User):
    if _can_view_all_work_orders(user):
        return query
    return query.filter(WorkOrder.steps.any(WorkOrderStep.assigned_user_id == user.id))


def _ensure_work_order_visible(work_order: WorkOrder, user: User) -> None:
    if _can_view_all_work_orders(user):
        return
    if not any(step.assigned_user_id == user.id for step in work_order.steps):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")


@router.get("", response_model=PageResponse[WorkOrderRead])
def list_work_orders(
    status_filter: str | None = None,
    sales_order_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> PageResponse[WorkOrderRead]:
    query = db.query(WorkOrder).options(selectinload(WorkOrder.steps)).filter(WorkOrder.deleted_at.is_(None))
    query = _restrict_work_orders_to_user(query, current_user)
    if status_filter:
        query = query.filter(WorkOrder.status == status_filter)
    if sales_order_id:
        query = query.filter(WorkOrder.sales_order_id == sales_order_id)
    total = query.count()
    items = query.order_by(WorkOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
def export_work_orders(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    query = db.query(WorkOrder).filter(WorkOrder.deleted_at.is_(None))
    if status_filter:
        query = query.filter(WorkOrder.status == status_filter)
    work_orders = query.order_by(WorkOrder.created_at.desc()).all()
    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="export",
        target_type="work_order",
        after_data={"count": len(work_orders)},
    )
    db.commit()
    return build_xlsx_response(
        "work-orders.xlsx",
        ["工单编号", "产品", "数量", "优先级", "状态", "计划开始", "计划完成", "实际开始", "实际完成"],
        [
            [
                work_order.work_order_no,
                work_order.product_name,
                float(work_order.quantity),
                work_order.priority,
                work_order.status,
                work_order.planned_start_at.isoformat() if work_order.planned_start_at else "",
                work_order.planned_end_at.isoformat() if work_order.planned_end_at else "",
                work_order.actual_start_at.isoformat() if work_order.actual_start_at else "",
                work_order.actual_end_at.isoformat() if work_order.actual_end_at else "",
            ]
            for work_order in work_orders
        ],
    )


@router.get("/board", response_model=ProductionBoardRead)
def get_production_board(
    task_limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> ProductionBoardRead:
    today = date.today()
    rows_query = (
        db.query(WorkOrderStep, WorkOrder, SalesOrder, User)
        .join(WorkOrder, WorkOrderStep.work_order_id == WorkOrder.id)
        .join(SalesOrder, WorkOrder.sales_order_id == SalesOrder.id)
        .outerjoin(User, WorkOrderStep.assigned_user_id == User.id)
        .filter(WorkOrder.deleted_at.is_(None), WorkOrderStep.status.in_(ACTIVE_STEP_STATUSES))
    )
    if not _can_view_all_work_orders(current_user):
        rows_query = rows_query.filter(WorkOrderStep.assigned_user_id == current_user.id)
    rows = rows_query.all()

    queue_map: dict[str, ProcessQueueRead] = {}
    pending_steps = 0
    processing_steps = 0
    pending_inspection_steps = 0
    reworking_steps = 0
    unassigned_steps = 0
    overdue_steps = 0
    tasks: list[WorkOrderStepTaskRead] = []

    for step, work_order, sales_order, assigned_user in rows:
        queue = queue_map.setdefault(step.step_name, ProcessQueueRead(step_name=step.step_name))
        queue.total_count += 1
        if step.status == StepStatus.PENDING_PROCESS:
            pending_steps += 1
            queue.pending_count += 1
        elif step.status == StepStatus.PROCESSING:
            processing_steps += 1
            queue.processing_count += 1
        elif step.status == StepStatus.PENDING_INSPECTION:
            pending_inspection_steps += 1
            queue.pending_inspection_count += 1
        elif step.status in {StepStatus.INSPECTION_FAILED, StepStatus.REWORKING}:
            reworking_steps += 1
            queue.reworking_count += 1

        if step.assigned_user_id is None:
            unassigned_steps += 1
        if is_step_overdue(step, sales_order, today):
            overdue_steps += 1
            queue.overdue_count += 1
        tasks.append(build_step_task(step, work_order, sales_order, assigned_user, today))

    priority_rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    tasks.sort(
        key=lambda task: (
            not task.is_overdue,
            priority_rank.get(task.priority, 9),
            task.planned_end_at or datetime.max.replace(tzinfo=timezone.utc),
            task.due_date,
            task.step_no,
        )
    )

    due_today_orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.deleted_at.is_(None),
            SalesOrder.due_date <= today,
            ~SalesOrder.status.in_(("cancelled", "paid", "archived")),
        )
        .count()
    )

    return ProductionBoardRead(
        pending_steps=pending_steps,
        processing_steps=processing_steps,
        pending_inspection_steps=pending_inspection_steps,
        reworking_steps=reworking_steps,
        unassigned_steps=unassigned_steps,
        overdue_steps=overdue_steps,
        due_today_orders=due_today_orders,
        queues=sorted(queue_map.values(), key=lambda item: (-item.total_count, item.step_name)),
        active_tasks=tasks[:task_limit],
    )


@router.get("/my-steps", response_model=PageResponse[WorkOrderStepTaskRead])
def list_my_work_order_steps(
    status_filter: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> PageResponse[WorkOrderStepTaskRead]:
    today = date.today()
    query = (
        db.query(WorkOrderStep, WorkOrder, SalesOrder, User)
        .join(WorkOrder, WorkOrderStep.work_order_id == WorkOrder.id)
        .join(SalesOrder, WorkOrder.sales_order_id == SalesOrder.id)
        .outerjoin(User, WorkOrderStep.assigned_user_id == User.id)
        .filter(
            WorkOrder.deleted_at.is_(None),
            WorkOrderStep.assigned_user_id == current_user.id,
            WorkOrderStep.status.in_(ACTIVE_STEP_STATUSES),
        )
    )
    if status_filter:
        query = query.filter(WorkOrderStep.status == status_filter)
    total = query.count()
    rows = (
        query.order_by(WorkOrderStep.planned_end_at.asc().nulls_last(), WorkOrderStep.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [build_step_task(step, work_order, sales_order, assigned_user, today) for step, work_order, sales_order, assigned_user in rows]
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{work_order_id}", response_model=WorkOrderRead)
def get_work_order(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> WorkOrder:
    work_order = db.query(WorkOrder).options(selectinload(WorkOrder.steps)).filter(WorkOrder.id == work_order_id).first()
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")
    _ensure_work_order_visible(work_order, current_user)
    return work_order


@router.get("/{work_order_id}/timeline", response_model=list[TimelineItem])
def get_work_order_timeline(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> list[TimelineItem]:
    work_order = db.query(WorkOrder).options(selectinload(WorkOrder.steps)).filter(WorkOrder.id == work_order_id).first()
    if work_order is None or work_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")
    _ensure_work_order_visible(work_order, current_user)
    order = db.get(SalesOrder, work_order.sales_order_id)
    if order is None or order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return build_sales_order_timeline(db, order)


@router.post("/{work_order_id}/dispatch", response_model=WorkOrderRead)
def dispatch_work_order(
    work_order_id: UUID,
    payload: DispatchWorkOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:dispatch")),
) -> WorkOrder:
    work_order = db.query(WorkOrder).options(selectinload(WorkOrder.steps)).filter(WorkOrder.id == work_order_id).first()
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")

    step_map = {step.id: step for step in work_order.steps}
    for assignment in payload.assignments:
        step = step_map.get(assignment.step_id)
        if step is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Step does not belong to this work order.")
        user = db.get(User, assignment.assigned_user_id)
        if user is None or user.status != "active":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Assigned user is not active.")
        step.assigned_user_id = assignment.assigned_user_id
        step.planned_start_at = assignment.planned_start_at
        step.planned_end_at = assignment.planned_end_at

    if work_order.status == WorkOrderStatus.PENDING_SCHEDULE:
        work_order.status = WorkOrderStatus.SCHEDULED

    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="dispatch",
        target_type="work_order",
        target_id=work_order.id,
        after_data={"work_order_no": work_order.work_order_no, "assignment_count": len(payload.assignments)},
    )
    db.commit()
    db.refresh(work_order)
    return work_order


@router.post("/steps/{step_id}/start")
def start_step(
    step_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("step:start")),
) -> dict[str, str]:
    step = db.get(WorkOrderStep, step_id)
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")
    if (
        step.assigned_user_id is not None
        and step.assigned_user_id != current_user.id
        and "work_order:dispatch" not in current_user.permission_codes
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This step is assigned to another operator.")
    previous = (
        db.query(WorkOrderStep)
        .filter(WorkOrderStep.work_order_id == step.work_order_id, WorkOrderStep.step_no == step.step_no - 1)
        .first()
    )
    transition = can_start_step(step.status, previous.status if previous else None)
    if not transition.allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=transition.reason)

    step.status = StepStatus.PROCESSING
    step.actual_start_at = datetime.now(timezone.utc)
    if step.assigned_user_id is None:
        step.assigned_user_id = current_user.id

    work_order = db.get(WorkOrder, step.work_order_id)
    if work_order and work_order.status in {WorkOrderStatus.PENDING_SCHEDULE, WorkOrderStatus.SCHEDULED}:
        work_order.status = WorkOrderStatus.IN_PRODUCTION
        work_order.actual_start_at = step.actual_start_at

    db.add(
        ProcessRecord(
            work_order_id=step.work_order_id,
            work_order_step_id=step.id,
            operator_id=current_user.id,
            action="start",
            reported_at=step.actual_start_at,
        )
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="step_start",
        target_type="work_order_step",
        target_id=step.id,
        after_data={"step_name": step.step_name, "status": step.status},
    )
    db.commit()
    return {"status": step.status}


@router.post("/steps/{step_id}/complete")
def complete_step(
    step_id: UUID,
    payload: CompleteStepRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("step:complete")),
) -> dict[str, str]:
    step = db.get(WorkOrderStep, step_id)
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")
    if (
        step.assigned_user_id is not None
        and step.assigned_user_id != current_user.id
        and "work_order:dispatch" not in current_user.permission_codes
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This step is assigned to another operator.")
    if step.status != StepStatus.PROCESSING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only processing steps can be completed.")

    if payload.processed_qty < 0 or payload.qualified_qty < 0 or payload.defective_qty < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Quantities cannot be negative.")
    if payload.qualified_qty + payload.defective_qty > payload.processed_qty:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Qualified plus defective quantity cannot exceed processed quantity.")

    step.input_qty = payload.processed_qty
    step.qualified_qty = payload.qualified_qty
    step.defective_qty = payload.defective_qty
    step.actual_end_at = datetime.now(timezone.utc)
    step.status = next_status_after_complete(step.requires_inspection)
    step.remark = payload.remark

    db.add(
        ProcessRecord(
            work_order_id=step.work_order_id,
            work_order_step_id=step.id,
            operator_id=current_user.id,
            action="complete",
            processed_qty=payload.processed_qty,
            qualified_qty=payload.qualified_qty,
            defective_qty=payload.defective_qty,
            work_hours=payload.work_hours,
            reported_at=step.actual_end_at,
            remark=payload.remark,
        )
    )

    next_step = (
        db.query(WorkOrderStep)
        .filter(WorkOrderStep.work_order_id == step.work_order_id, WorkOrderStep.step_no == step.step_no + 1)
        .first()
    )
    if step.status in FINISHED_STEP_STATUSES and next_step and next_step.status == StepStatus.NOT_STARTED:
        next_step.status = StepStatus.PENDING_PROCESS

    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="step_complete",
        target_type="work_order_step",
        target_id=step.id,
        after_data={
            "step_name": step.step_name,
            "status": step.status,
            "processed_qty": payload.processed_qty,
            "qualified_qty": payload.qualified_qty,
            "defective_qty": payload.defective_qty,
        },
    )
    db.commit()
    return {"status": step.status}
