from datetime import date, datetime, timezone
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.production import InspectionRecord, ReworkRecord, WorkOrder, WorkOrderStep
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.schemas.common import PageResponse
from app.schemas.inspection import InspectionRead, InspectionSubmitRequest, PendingInspectionTask
from app.services.audit import log_operation
from app.services.numbering import generate_number
from app.services.plate_numbers import next_derived_plate_number, primary_plate_number_from_order
from app.services.printing import record_print_job
from app.services.state_machine import FINISHED_STEP_STATUSES, OrderStatus, StepStatus, WorkOrderStatus, validate_inspection_result

router = APIRouter()


def _h(value: object) -> str:
    return escape("" if value is None else str(value))


def _qty(value: object) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "-"


def _dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _result_label(result: str) -> str:
    labels = {
        "passed": "Passed",
        "failed": "Failed",
        "concession": "Concession Accepted",
        "rework": "Rework",
    }
    return labels.get(result, result)


def _inspection_document_type(inspection: InspectionRecord) -> str:
    return "quality_rework_report" if inspection.result in {"failed", "rework"} else "quality_report"


def _inspection_document_title(inspection: InspectionRecord) -> str:
    return "Quality Abnormality & Rework Report" if _inspection_document_type(inspection) == "quality_rework_report" else "Quality Inspection Report"


def _plate_detail(details: dict | None, *keys: str) -> str:
    details = details or {}
    for key in keys:
        value = details.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _inspection_print_html(
    *,
    inspection: InspectionRecord,
    work_order: WorkOrder | None,
    step: WorkOrderStep | None,
    target_step: WorkOrderStep | None,
    rework: ReworkRecord | None,
    order: SalesOrder | None,
    customer: Customer | None,
    inspector: User | None,
) -> str:
    title = _inspection_document_title(inspection)
    details = order.plate_details if order else {}
    is_rework_report = _inspection_document_type(inspection) == "quality_rework_report"
    result_class = "danger" if is_rework_report else "success"
    rework_section = ""
    if is_rework_report:
        rework_section = f"""
    <h2>Rework Handling</h2>
    <table>
      <tbody>
        <tr><th>Rework No.</th><td>{_h(rework.rework_no if rework else '')}</td><th>Rework Qty</th><td>{_qty(rework.quantity if rework else inspection.failed_qty or inspection.inspected_qty)}</td></tr>
        <tr><th>Abnormal Step</th><td>{_h(step.step_name if step else '')}</td><th>Return To Step</th><td>{_h(target_step.step_name if target_step else '')}</td></tr>
        <tr><th>Abnormality Reason</th><td colspan="3" class="left">{_h((inspection.reason or rework.reason) if rework else (inspection.reason or ''))}</td></tr>
        <tr><th>Preventive Action</th><td colspan="3" class="left">&nbsp;</td></tr>
      </tbody>
    </table>
"""

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{_h(title)} - {_h(inspection.inspection_no)}</title>
  <style>
    @page {{ size: A4 portrait; margin: 12mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .sheet {{ width: 760px; margin: 16px auto; }}
    h1 {{ text-align: center; font-size: 24px; letter-spacing: 0; margin: 0 0 12px; }}
    h2 {{ font-size: 15px; margin: 14px 0 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
    th, td {{ border: 1px solid #111827; padding: 7px 8px; font-size: 12px; text-align: center; }}
    th {{ width: 120px; background: #f3f4f6; }}
    .left {{ text-align: left; }}
    .status {{ display: inline-block; min-width: 72px; padding: 4px 10px; border-radius: 3px; color: #fff; }}
    .success {{ background: #16a34a; }}
    .danger {{ background: #dc2626; }}
    .signatures {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 28px; font-size: 13px; }}
    .line {{ border-bottom: 1px solid #111827; height: 26px; }}
    .actions {{ text-align: right; margin: 12px auto; width: 760px; }}
    button {{ border: 1px solid #111827; background: #fff; padding: 6px 12px; cursor: pointer; }}
    @media print {{ .actions {{ display: none; }} .sheet {{ margin: 0 auto; }} }}
  </style>
</head>
<body>
  <div class="actions"><button type="button" onclick="window.print()">Print / PDF</button></div>
  <section class="sheet">
    <h1>{_h(title)}</h1>
    <table>
      <tbody>
        <tr><th>Inspection No.</th><td>{_h(inspection.inspection_no)}</td><th>Inspection Time</th><td>{_h(_dt(inspection.inspected_at))}</td></tr>
        <tr><th>Order No.</th><td>{_h(order.order_no if order else '')}</td><th>Work Order No.</th><td>{_h(work_order.work_order_no if work_order else '')}</td></tr>
        <tr><th>Customer</th><td>{_h(customer.name if customer else '')}</td><th>Cylinder No.</th><td>{_h(_plate_detail(details, 'cylinder_id', 'sample_no', 'no'))}</td></tr>
        <tr><th>Artwork Name</th><td>{_h(work_order.product_name if work_order else order.product_summary if order else '')}</td><th>Process Step</th><td>{_h(step.step_name if step else '')}</td></tr>
        <tr><th>Inspector</th><td>{_h(inspector.real_name if inspector else '')}</td><th>Inspection Type</th><td>{_h('Final Inspection' if inspection.inspection_type == 'final' else 'Process Inspection')}</td></tr>
      </tbody>
    </table>

    <h2>Inspection Result</h2>
    <table>
      <tbody>
        <tr><th>Result</th><td><span class="status {result_class}">{_h(_result_label(inspection.result))}</span></td><th>Inspected Qty</th><td>{_qty(inspection.inspected_qty)}</td></tr>
        <tr><th>Passed Qty</th><td>{_qty(inspection.passed_qty)}</td><th>Defective Qty</th><td>{_qty(inspection.failed_qty)}</td></tr>
        <tr><th>Reason / Remarks</th><td colspan="3" class="left">{_h(inspection.reason or '')}</td></tr>
      </tbody>
    </table>
{rework_section}
    <div class="signatures">
      <div>Inspector<div class="line">{_h(inspector.real_name if inspector else '')}</div></div>
      <div>Production Confirmation<div class="line"></div></div>
      <div>Approved By<div class="line"></div></div>
    </div>
  </section>
</body>
</html>
"""
    return html


def _inspection_print_snapshot(
    *,
    inspection: InspectionRecord,
    work_order: WorkOrder | None,
    step: WorkOrderStep | None,
    order: SalesOrder | None,
    customer: Customer | None,
) -> dict:
    return {
        "inspection_no": inspection.inspection_no,
        "document_type": _inspection_document_type(inspection),
        "result": inspection.result,
        "order_no": order.order_no if order else None,
        "work_order_no": work_order.work_order_no if work_order else None,
        "customer_name": customer.name if customer else None,
        "step_name": step.step_name if step else None,
        "inspected_qty": float(inspection.inspected_qty),
        "failed_qty": float(inspection.failed_qty) if inspection.failed_qty is not None else None,
    }


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
    source_plate_no = primary_plate_number_from_order(original_order)
    rework_plate_no = next_derived_plate_number(db, source_plate_no=source_plate_no, derivation_type="internal_rework")
    plate_details["order_type"] = "rework"
    plate_details["original_no"] = source_plate_no
    plate_details["derived_source_cylinder_no"] = source_plate_no
    plate_details["rework_source_cylinder_no"] = source_plate_no
    plate_details["derivation_type"] = "internal_rework"
    plate_details["cylinder_id"] = rework_plate_no
    plate_details["no"] = rework_plate_no
    plate_details["sample_no"] = rework_plate_no
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
        order_no=rework_plate_no,
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


@router.get("/{inspection_id}/print", response_class=HTMLResponse)
def print_inspection_report(
    inspection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inspection:view")),
) -> HTMLResponse:
    inspection = db.get(InspectionRecord, inspection_id)
    if inspection is None or inspection.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found.")

    work_order = db.get(WorkOrder, inspection.work_order_id)
    step = db.get(WorkOrderStep, inspection.work_order_step_id)
    target_step = db.get(WorkOrderStep, inspection.rework_to_step_id) if inspection.rework_to_step_id else None
    order = db.get(SalesOrder, inspection.sales_order_id)
    customer = db.get(Customer, order.customer_id) if order else None
    inspector = db.get(User, inspection.inspector_id)
    rework = (
        db.query(ReworkRecord)
        .filter(ReworkRecord.inspection_record_id == inspection.id, ReworkRecord.deleted_at.is_(None))
        .order_by(ReworkRecord.created_at.desc())
        .first()
    )

    html = _inspection_print_html(
        inspection=inspection,
        work_order=work_order,
        step=step,
        target_step=target_step,
        rework=rework,
        order=order,
        customer=customer,
        inspector=inspector,
    )
    document_type = _inspection_document_type(inspection)
    print_job = record_print_job(
        db,
        document_type=document_type,
        target_type="inspection_record",
        target_id=inspection.id,
        printed_by=current_user.id,
        snapshot=_inspection_print_snapshot(
            inspection=inspection,
            work_order=work_order,
            step=step,
            order=order,
            customer=customer,
        ),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="inspection",
        action="print_report",
        target_type="inspection_record",
        target_id=inspection.id,
        after_data={"inspection_no": inspection.inspection_no, "document_type": document_type, "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)


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
