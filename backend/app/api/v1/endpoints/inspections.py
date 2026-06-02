from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.production import InspectionRecord, ReworkRecord, WorkOrder, WorkOrderStep
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.schemas.common import PageResponse
from app.schemas.inspection import InspectionRead, InspectionSubmitRequest, PendingInspectionTask
from app.services.audit import log_operation
from app.services.numbering import generate_number
from app.services.state_machine import FINISHED_STEP_STATUSES, OrderStatus, StepStatus, WorkOrderStatus, validate_inspection_result

router = APIRouter()


def _generate_rework_order_no(db: Session, original_order_no: str) -> str:
    candidate = f"{original_order_no}G"
    while db.query(SalesOrder.id).filter(SalesOrder.order_no == candidate).first():
        candidate = f"{candidate}G"
    return candidate


def _create_rework_sales_order(
    db: Session,
    *,
    original_order: SalesOrder,
    source_work_order: WorkOrder,
    source_item: SalesOrderItem | None,
    inspection: InspectionRecord,
    current_user: User,
    quantity: float,
    reason: str | None,
    inspected_at: datetime,
) -> SalesOrder:
    product_name = source_item.product_name if source_item else source_work_order.product_name
    route_id = source_item.route_id if source_item and source_item.route_id else source_work_order.route_id
    plate_details = dict(original_order.plate_details or {})
    plate_details["original_no"] = plate_details.get("original_no") or original_order.order_no
    plate_details["sample_no"] = _generate_rework_order_no(db, original_order.order_no)
    rework_item = SalesOrderItem(
        product_id=source_item.product_id if source_item else source_work_order.product_id,
        product_name=product_name,
        specification=source_item.specification if source_item else None,
        quantity=quantity,
        unit=source_item.unit if source_item else "pcs",
        unit_price=0,
        amount=0,
        route_id=route_id,
        remark=f"Rework from {original_order.order_no}",
    )
    rework_order = SalesOrder(
        order_no=plate_details["sample_no"],
        customer_id=original_order.customer_id,
        product_summary=product_name,
        order_date=date.today(),
        due_date=original_order.due_date,
        total_amount=0,
        status=OrderStatus.CONFIRMED,
        priority=source_work_order.priority,
        route_id=route_id,
        confirmed_at=inspected_at,
        confirmed_by=current_user.id,
        rework_source_order_id=original_order.id,
        rework_source_work_order_id=source_work_order.id,
        rework_source_inspection_id=inspection.id,
        plate_details=plate_details,
        color_rows=list(original_order.color_rows or []),
        remark=f"Rework generated from {original_order.order_no}. Reason: {reason or ''}".strip(),
        items=[rework_item],
    )
    db.add(rework_order)
    db.flush()
    return rework_order


@router.get("/pending", response_model=list[PendingInspectionTask])
def list_pending_inspections(
    db: Session = Depends(get_db),
    _=Depends(require_permission("inspection:view")),
) -> list[PendingInspectionTask]:
    rows = (
        db.query(WorkOrderStep, WorkOrder)
        .join(WorkOrder, WorkOrder.id == WorkOrderStep.work_order_id)
        .filter(WorkOrderStep.status == StepStatus.PENDING_INSPECTION, WorkOrderStep.deleted_at.is_(None))
        .order_by(WorkOrderStep.created_at.desc())
        .all()
    )
    return [
        PendingInspectionTask(
            step_id=step.id,
            work_order_id=work_order.id,
            work_order_no=work_order.work_order_no,
            product_name=work_order.product_name,
            step_no=step.step_no,
            step_name=step.step_name,
            quantity=work_order.quantity,
            status=step.status,
        )
        for step, work_order in rows
    ]


@router.get("", response_model=PageResponse[InspectionRead])
def list_inspections(
    sales_order_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inspection:view")),
) -> PageResponse[InspectionRead]:
    query = db.query(InspectionRecord).order_by(InspectionRecord.inspected_at.desc())
    if sales_order_id:
        query = query.filter(InspectionRecord.sales_order_id == sales_order_id)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/work-order-steps/{step_id}", response_model=InspectionRead, status_code=status.HTTP_201_CREATED)
def submit_inspection(
    step_id: UUID,
    payload: InspectionSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("inspection:submit")),
) -> InspectionRecord:
    step = db.get(WorkOrderStep, step_id)
    if step is None or step.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")
    if step.status != StepStatus.PENDING_INSPECTION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending inspection steps can be inspected.")

    work_order = db.get(WorkOrder, step.work_order_id)
    if work_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")

    transition = validate_inspection_result(
        payload.result,
        payload.reason,
        str(payload.rework_to_step_id) if payload.rework_to_step_id else None,
    )
    if not transition.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=transition.reason)

    target_step: WorkOrderStep | None = None
    if payload.rework_to_step_id:
        target_step = db.get(WorkOrderStep, payload.rework_to_step_id)
        if target_step is None or target_step.work_order_id != work_order.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rework target step is invalid.")
        if target_step.step_no > step.step_no:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rework target cannot be after current step.")

    inspected_at = datetime.now(timezone.utc)
    next_step_for_type = (
        db.query(WorkOrderStep)
        .filter(WorkOrderStep.work_order_id == work_order.id, WorkOrderStep.step_no == step.step_no + 1)
        .first()
    )
    inspection = InspectionRecord(
        inspection_no=generate_number("QC"),
        sales_order_id=work_order.sales_order_id,
        work_order_id=work_order.id,
        work_order_step_id=step.id,
        inspector_id=current_user.id,
        inspection_type="final" if next_step_for_type is None else "process",
        result=payload.result,
        inspected_qty=payload.inspected_qty,
        passed_qty=payload.passed_qty,
        failed_qty=payload.failed_qty,
        reason=payload.reason,
        rework_to_step_id=payload.rework_to_step_id,
        inspected_at=inspected_at,
    )
    db.add(inspection)
    db.flush()

    if payload.result in {"passed", "concession"}:
        step.status = StepStatus.INSPECTION_PASSED
        next_step = (
            db.query(WorkOrderStep)
            .filter(WorkOrderStep.work_order_id == work_order.id, WorkOrderStep.step_no == step.step_no + 1)
            .first()
        )
        if next_step and next_step.status == StepStatus.NOT_STARTED:
            next_step.status = StepStatus.PENDING_PROCESS

        all_steps = db.query(WorkOrderStep).filter(WorkOrderStep.work_order_id == work_order.id).all()
        if all(item.status in FINISHED_STEP_STATUSES for item in all_steps):
            work_order.status = WorkOrderStatus.COMPLETED
            work_order.actual_end_at = inspected_at
            sibling_work_orders = db.query(WorkOrder).filter(WorkOrder.sales_order_id == work_order.sales_order_id).all()
            if all(item.status == WorkOrderStatus.COMPLETED for item in sibling_work_orders):
                sales_order = db.get(SalesOrder, work_order.sales_order_id)
                if sales_order:
                    sales_order.status = "pending_delivery"
    else:
        step.status = StepStatus.INSPECTION_FAILED
        work_order.status = WorkOrderStatus.REWORKING
        sales_order = db.get(SalesOrder, work_order.sales_order_id)
        if sales_order:
            sales_order.status = OrderStatus.REWORKING
        assert target_step is not None
        target_step.status = StepStatus.PENDING_PROCESS
        later_steps = (
            db.query(WorkOrderStep)
            .filter(
                WorkOrderStep.work_order_id == work_order.id,
                WorkOrderStep.step_no > target_step.step_no,
                WorkOrderStep.step_no <= step.step_no,
            )
            .all()
        )
        for later_step in later_steps:
            if later_step.id != step.id:
                later_step.status = StepStatus.NOT_STARTED

        rework_sales_order: SalesOrder | None = None
        if sales_order:
            source_item = db.get(SalesOrderItem, work_order.sales_order_item_id) if work_order.sales_order_item_id else None
            rework_sales_order = _create_rework_sales_order(
                db,
                original_order=sales_order,
                source_work_order=work_order,
                source_item=source_item,
                inspection=inspection,
                current_user=current_user,
                quantity=float(payload.failed_qty or payload.inspected_qty),
                reason=payload.reason,
                inspected_at=inspected_at,
            )

        db.add(
            ReworkRecord(
                rework_no=generate_number("RW"),
                inspection_record_id=inspection.id,
                work_order_id=work_order.id,
                rework_sales_order_id=rework_sales_order.id if rework_sales_order else None,
                from_step_id=step.id,
                to_step_id=target_step.id,
                reason=payload.reason or "",
                quantity=payload.failed_qty or payload.inspected_qty,
                status="pending",
            )
        )

    log_operation(
        db,
        user_id=current_user.id,
        module="inspection",
        action="submit",
        target_type="inspection_record",
        target_id=inspection.id,
        after_data={"inspection_no": inspection.inspection_no, "result": inspection.result},
    )
    db.commit()
    db.refresh(inspection)
    return inspection
