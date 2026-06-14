from datetime import date, datetime, timezone
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.production import InspectionRecord, ProcessRecord, ReworkRecord, WorkOrder, WorkOrderStep
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.common import PageResponse
from app.schemas.production import (
    CompleteStepRequest,
    DispatchWorkOrderRequest,
    ProcessQueueRead,
    ProductionBoardRead,
    ProductionFlowInspectionRead,
    ProductionFlowProcessRecordRead,
    ProductionFlowRequirementRead,
    ProductionFlowReworkRead,
    ProductionFlowRowRead,
    ProductionFlowStepRead,
    WorkOrderRead,
    WorkOrderStepTaskRead,
)
from app.schemas.timeline import TimelineItem
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.printing import record_print_job
from app.services.state_machine import (
    FINISHED_STEP_STATUSES,
    OrderStatus,
    StepStatus,
    WorkOrderStatus,
    can_start_step,
    next_status_after_complete,
)
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


def _text_value(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_text(source: dict, *keys: str) -> str | None:
    for key in keys:
        value = _text_value(source.get(key))
        if value:
            return value
    return None


def _date_value(value: object, fallback: date) -> date:
    if isinstance(value, date):
        return value
    text = _text_value(value)
    if not text:
        return fallback
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return fallback


def _float_value(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _format_number(value: float | None, precision: int = 3) -> str | None:
    if value is None:
        return None
    return f"{value:.{precision}f}".rstrip("0").rstrip(".")


def _h(value: object) -> str:
    return escape("" if value is None else str(value))


def _qty(value: object) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "-"


def _date_time(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _computed_c_number(details: dict) -> float | None:
    c_value = _float_value(details.get("c_value"))
    if c_value is not None:
        return c_value
    unit_l = _float_value(details.get("unit_l"))
    straight = _float_value(details.get("straight"))
    if unit_l is not None and straight is not None:
        return unit_l * straight
    return unit_l or _float_value(details.get("l_value"))


def _computed_l_number(details: dict) -> float | None:
    return _float_value(details.get("l_value")) or _float_value(details.get("unit_w"))


def _computed_c_text(details: dict) -> str | None:
    explicit = _text_value(details.get("c_value"))
    if explicit:
        return explicit
    return _format_number(_computed_c_number(details), 3)


def _computed_l_text(details: dict) -> str | None:
    return _first_text(details, "l_value", "unit_w")


def _sum_color_qty(color_rows: list[dict]) -> float | None:
    total = 0.0
    has_qty = False
    for row in color_rows:
        qty = _float_value(row.get("qty"))
        if qty is None:
            continue
        total += qty
        has_qty = True
    return total if has_qty else None


def _total_qty(details: dict, color_rows: list[dict], fallback: float) -> float:
    return (
        _sum_color_qty(color_rows)
        or _float_value(details.get("total_qty"))
        or _float_value(details.get("total_branch"))
        or _float_value(details.get("production_qty"))
        or _float_value(details.get("customer_material_qty"))
        or fallback
    )


def _first_color_text(color_rows: list[dict], *keys: str) -> str | None:
    for row in color_rows:
        for key in keys:
            value = _text_value(row.get(key))
            if value:
                return value
    return None


def _calculate_square(details: dict, total_qty: float) -> str | None:
    explicit = _text_value(details.get("square"))
    if explicit:
        return explicit
    c_value = _computed_c_number(details)
    l_value = _computed_l_number(details)
    if c_value is None or l_value is None:
        return None
    return _format_number(c_value * l_value * total_qty / 1_000_000, 3)


def _plate_no_from_order(order: SalesOrder) -> str:
    details = order.plate_details or {}
    for key in ("cylinder_id", "no", "sample_no", "original_no"):
        value = _text_value(details.get(key))
        if value:
            return value
    for row in order.color_rows or []:
        value = _text_value(row.get("public_no") or row.get("color_cylinder_no"))
        if value:
            return value
    return order.order_no


def _current_step(steps: list[WorkOrderStep]) -> WorkOrderStep | None:
    active_steps = [step for step in steps if step.status in ACTIVE_STEP_STATUSES]
    if active_steps:
        return sorted(active_steps, key=lambda item: item.step_no)[0]
    unfinished_steps = [step for step in steps if step.status not in FINISHED_STEP_STATUSES]
    if unfinished_steps:
        return sorted(unfinished_steps, key=lambda item: item.step_no)[0]
    return steps[-1] if steps else None


def _row_has_finished(work_order: WorkOrder, sales_order: SalesOrder, current_step: WorkOrderStep | None) -> bool:
    if work_order.status == WorkOrderStatus.COMPLETED:
        return True
    if sales_order.status in {OrderStatus.PENDING_DELIVERY, OrderStatus.DELIVERED, OrderStatus.PENDING_PAYMENT, OrderStatus.PAID, OrderStatus.ARCHIVED}:
        return True
    return current_step is not None and current_step.status in FINISHED_STEP_STATUSES and all(step.status in FINISHED_STEP_STATUSES for step in work_order.steps)


def _production_requirement(details: dict, order_remark: str | None, work_order_remark: str | None) -> ProductionFlowRequirementRead:
    return ProductionFlowRequirementRead(
        engraving_requirement=_first_text(details, "engraving_note", "engraving_requirement"),
        proofing_requirement=_first_text(details, "proofing_requirement", "polishing_requirement"),
        inspection_requirement=_first_text(details, "inspection_requirement", "chrome_requirement"),
        color_separation=_text_value(details.get("color_separation")),
        computer_requirement=_first_text(details, "computer_requirement", "computer_position"),
        design_requirement=_first_text(details, "common_remarks", "production_position"),
        production_remark=_text_value(work_order_remark or order_remark),
    )


def _can_view_all_work_orders(user: User) -> bool:
    privileged_roles = {"admin", "boss", "sales", "designer", "production_manager", "inspector"}
    return "work_order:dispatch" in user.permission_codes or any(role.code in privileged_roles for role in user.roles)


def _ensure_production_board_visible(user: User) -> None:
    allowed_roles = {"admin", "boss", "production_manager"}
    if "work_order:dispatch" in user.permission_codes or any(role.code in allowed_roles for role in user.roles):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Production board is restricted to management users.")


def _restrict_work_orders_to_user(query, user: User):
    if _can_view_all_work_orders(user):
        return query
    return query.filter(WorkOrder.steps.any(WorkOrderStep.assigned_user_id == user.id))


def _ensure_work_order_visible(work_order: WorkOrder, user: User) -> None:
    if _can_view_all_work_orders(user):
        return
    if not any(step.assigned_user_id == user.id for step in work_order.steps):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")


def _finalize_work_order_if_ready(db: Session, work_order: WorkOrder, completed_at: datetime) -> None:
    all_steps = (
        db.query(WorkOrderStep)
        .filter(WorkOrderStep.work_order_id == work_order.id, WorkOrderStep.deleted_at.is_(None))
        .all()
    )
    if not all_steps or not all(step.status in FINISHED_STEP_STATUSES for step in all_steps):
        return

    work_order.status = WorkOrderStatus.COMPLETED
    work_order.actual_end_at = completed_at

    sibling_work_orders = (
        db.query(WorkOrder)
        .filter(WorkOrder.sales_order_id == work_order.sales_order_id, WorkOrder.deleted_at.is_(None))
        .all()
    )
    if all(item.id == work_order.id or item.status == WorkOrderStatus.COMPLETED for item in sibling_work_orders):
        sales_order = db.get(SalesOrder, work_order.sales_order_id)
        if sales_order:
            sales_order.status = OrderStatus.PENDING_DELIVERY


def _self_inspection_card_html(
    *,
    work_order: WorkOrder,
    sales_order: SalesOrder,
    customer: Customer | None,
    assigned_users: dict[UUID, User],
) -> str:
    details = dict(sales_order.plate_details or {})
    cylinder_no = _plate_no_from_order(sales_order)
    c_value = _computed_c_text(details) or ""
    l_value = _computed_l_text(details) or ""
    inspection_points = [
        "Artwork, text and barcode match approved file",
        "Cylinder size, C/L value and direction checked",
        "Surface finish, chrome/copper condition checked",
        "Color sequence and engraving depth checked",
        "Defects recorded and reported before transfer",
    ]
    point_rows = "".join(f"<li>{_h(point)}</li>" for point in inspection_points)
    step_rows = []
    for step in sorted(work_order.steps, key=lambda item: item.step_no):
        assigned = assigned_users.get(step.assigned_user_id) if step.assigned_user_id else None
        step_rows.append(
            "<tr>"
            f"<td>{step.step_no}</td>"
            f"<td class='left'>{_h(step.step_name)}</td>"
            f"<td>{_h(assigned.real_name if assigned else '')}</td>"
            "<td></td>"
            "<td></td>"
            "<td></td>"
            "<td></td>"
            "</tr>"
        )

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Self Inspection Card - {_h(work_order.work_order_no)}</title>
  <style>
    @page {{ size: A4 portrait; margin: 11mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .sheet {{ width: 760px; margin: 16px auto; }}
    h1 {{ text-align: center; font-size: 23px; letter-spacing: 0; margin: 0 0 10px; }}
    h2 {{ font-size: 14px; margin: 12px 0 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
    th, td {{ border: 1px solid #111827; padding: 6px; font-size: 12px; text-align: center; }}
    th {{ background: #f3f4f6; }}
    .left {{ text-align: left; }}
    .meta th {{ width: 120px; }}
    ul {{ margin: 6px 0 10px 20px; padding: 0; font-size: 12px; line-height: 1.5; }}
    .signatures {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 24px; font-size: 13px; }}
    .line {{ border-bottom: 1px solid #111827; height: 26px; }}
    .actions {{ text-align: right; margin: 12px auto; width: 760px; }}
    button {{ border: 1px solid #111827; background: #fff; padding: 6px 12px; cursor: pointer; }}
    @media print {{ .actions {{ display: none; }} .sheet {{ margin: 0 auto; }} }}
  </style>
</head>
<body>
  <div class="actions"><button type="button" onclick="window.print()">Print / PDF</button></div>
  <section class="sheet">
    <h1>Self Inspection Card</h1>
    <table class="meta">
      <tbody>
        <tr><th>Work Order No.</th><td>{_h(work_order.work_order_no)}</td><th>Order No.</th><td>{_h(sales_order.order_no)}</td></tr>
        <tr><th>Customer</th><td>{_h(customer.name if customer else '')}</td><th>Cylinder No.</th><td>{_h(cylinder_no)}</td></tr>
        <tr><th>Artwork Name</th><td>{_h(work_order.product_name)}</td><th>Quantity</th><td>{_qty(work_order.quantity)}</td></tr>
        <tr><th>C Value</th><td>{_h(c_value)}</td><th>L Value</th><td>{_h(l_value)}</td></tr>
        <tr><th>Due Date</th><td>{_h(sales_order.due_date.isoformat())}</td><th>Printed At</th><td>{_h(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'))}</td></tr>
      </tbody>
    </table>

    <h2>Inspection Check Points</h2>
    <ul>{point_rows}</ul>

    <h2>Process Self Inspection</h2>
    <table>
      <thead>
        <tr><th style="width: 42px;">No.</th><th>Process Step</th><th>Operator</th><th>Self Check Result</th><th>Defect / Remark</th><th>Operator Signature</th><th>QC Confirmation</th></tr>
      </thead>
      <tbody>{''.join(step_rows) or "<tr><td colspan='7'>No process steps</td></tr>"}</tbody>
    </table>
    <div class="signatures">
      <div>Production Supervisor<div class="line"></div></div>
      <div>Quality Inspector<div class="line"></div></div>
      <div>Final Approval<div class="line"></div></div>
    </div>
  </section>
</body>
</html>
"""
    return html


def _self_inspection_snapshot(
    *,
    work_order: WorkOrder,
    sales_order: SalesOrder,
    customer: Customer | None,
) -> dict:
    return {
        "work_order_no": work_order.work_order_no,
        "order_no": sales_order.order_no,
        "customer_name": customer.name if customer else None,
        "cylinder_no": _plate_no_from_order(sales_order),
        "step_count": len(work_order.steps),
        "quantity": float(work_order.quantity),
    }


def _process_task_sheet_html(
    *,
    work_order: WorkOrder,
    sales_order: SalesOrder,
    customer: Customer | None,
    assigned_users: dict[UUID, User],
) -> str:
    details = dict(sales_order.plate_details or {})
    color_rows = list(sales_order.color_rows or [])
    total_qty = _total_qty(details, color_rows, float(work_order.quantity))
    requirements = _production_requirement(details, sales_order.remark, work_order.remark)
    requirement_rows = [
        ("Engraving Requirement", requirements.engraving_requirement),
        ("Proofing / Polishing", requirements.proofing_requirement),
        ("Inspection Requirement", requirements.inspection_requirement),
        ("Computer / Design", requirements.computer_requirement or requirements.design_requirement),
        ("Production Remarks", requirements.production_remark),
    ]
    requirement_html = "".join(
        f"<tr><th>{_h(label)}</th><td class='left'>{_h(value or '')}</td></tr>"
        for label, value in requirement_rows
        if value
    )
    if not requirement_html:
        requirement_html = "<tr><td class='left' colspan='2'>No special production requirements</td></tr>"

    color_html = ""
    for index, row in enumerate(color_rows, start=1):
        color_html += (
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{_h(row.get('color_no') or '')}</td>"
            f"<td class='left'>{_h(row.get('print_color') or '')}</td>"
            f"<td>{_h(row.get('qty') or '')}</td>"
            f"<td>{_h(row.get('dia') or '')}</td>"
            f"<td>{_h(row.get('real_dia') or '')}</td>"
            f"<td>{_h(row.get('public_no') or '')}</td>"
            "</tr>"
        )
    if not color_html:
        color_html = "<tr><td colspan='7'>No color rows</td></tr>"

    step_html = ""
    for step in sorted(work_order.steps, key=lambda item: item.step_no):
        assigned = assigned_users.get(step.assigned_user_id) if step.assigned_user_id else None
        step_html += (
            "<tr>"
            f"<td>{step.step_no}</td>"
            f"<td class='left'>{_h(step.step_name)}</td>"
            f"<td>{_h(assigned.real_name if assigned else '')}</td>"
            f"<td>{_h(_date_time(step.planned_start_at))}</td>"
            f"<td>{_h(_date_time(step.planned_end_at))}</td>"
            f"<td>{_h(_date_time(step.actual_start_at))}</td>"
            f"<td>{_h(_date_time(step.actual_end_at))}</td>"
            "<td></td>"
            "<td></td>"
            "</tr>"
        )
    if not step_html:
        step_html = "<tr><td colspan='9'>No process steps</td></tr>"

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Process Task Sheet - {_h(work_order.work_order_no)}</title>
  <style>
    @page {{ size: A4 landscape; margin: 10mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .sheet {{ width: 1040px; margin: 14px auto; }}
    h1 {{ text-align: center; font-size: 23px; letter-spacing: 0; margin: 0 0 10px; }}
    h2 {{ font-size: 14px; margin: 12px 0 7px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
    th, td {{ border: 1px solid #111827; padding: 5px 6px; font-size: 11px; text-align: center; }}
    th {{ background: #f3f4f6; }}
    .left {{ text-align: left; }}
    .meta th {{ width: 120px; }}
    .actions {{ text-align: right; margin: 12px auto; width: 1040px; }}
    button {{ border: 1px solid #111827; background: #fff; padding: 6px 12px; cursor: pointer; }}
    @media print {{ .actions {{ display: none; }} .sheet {{ margin: 0 auto; }} }}
  </style>
</head>
<body>
  <div class="actions"><button type="button" onclick="window.print()">Print / PDF</button></div>
  <section class="sheet">
    <h1>Process Task Sheet</h1>
    <table class="meta">
      <tbody>
        <tr><th>Work Order No.</th><td>{_h(work_order.work_order_no)}</td><th>Order No.</th><td>{_h(sales_order.order_no)}</td><th>Priority</th><td>{_h(work_order.priority)}</td></tr>
        <tr><th>Customer</th><td>{_h(customer.name if customer else '')}</td><th>Cylinder No.</th><td>{_h(_plate_no_from_order(sales_order))}</td><th>Due Date</th><td>{_h(sales_order.due_date.isoformat())}</td></tr>
        <tr><th>Artwork Name</th><td>{_h(work_order.product_name)}</td><th>Total Qty</th><td>{_qty(total_qty)}</td><th>Printed At</th><td>{_h(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'))}</td></tr>
        <tr><th>C Value</th><td>{_h(_computed_c_text(details) or '')}</td><th>L Value</th><td>{_h(_computed_l_text(details) or '')}</td><th>Square</th><td>{_h(_calculate_square(details, total_qty) or '')}</td></tr>
      </tbody>
    </table>

    <h2>Production Requirements</h2>
    <table>
      <tbody>{requirement_html}</tbody>
    </table>

    <h2>Color / Cylinder Rows</h2>
    <table>
      <thead><tr><th>No.</th><th>Color No.</th><th>Print Color</th><th>Qty</th><th>Dia</th><th>Real Dia</th><th>Public No.</th></tr></thead>
      <tbody>{color_html}</tbody>
    </table>

    <h2>Process Assignment</h2>
    <table>
      <thead>
        <tr><th>No.</th><th>Process Step</th><th>Operator</th><th>Planned Start</th><th>Planned End</th><th>Actual Start</th><th>Actual End</th><th>Output / Remark</th><th>Signature</th></tr>
      </thead>
      <tbody>{step_html}</tbody>
    </table>
  </section>
</body>
</html>
"""
    return html


def _process_task_snapshot(
    *,
    work_order: WorkOrder,
    sales_order: SalesOrder,
    customer: Customer | None,
) -> dict:
    return {
        "work_order_no": work_order.work_order_no,
        "order_no": sales_order.order_no,
        "customer_name": customer.name if customer else None,
        "cylinder_no": _plate_no_from_order(sales_order),
        "step_count": len(work_order.steps),
        "quantity": float(work_order.quantity),
    }


@router.get("", response_model=PageResponse[WorkOrderRead])
def list_work_orders(
    status_filter: str | None = None,
    sales_order_id: UUID | None = None,
    keyword: str | None = None,
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
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.join(SalesOrder, WorkOrder.sales_order_id == SalesOrder.id).join(Customer, SalesOrder.customer_id == Customer.id).filter(
            or_(
                WorkOrder.work_order_no.ilike(term),
                WorkOrder.product_name.ilike(term),
                SalesOrder.order_no.ilike(term),
                SalesOrder.product_summary.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
    total = query.count()
    items = query.order_by(WorkOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
def export_work_orders(
    status_filter: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    query = db.query(WorkOrder).filter(WorkOrder.deleted_at.is_(None))
    if status_filter:
        query = query.filter(WorkOrder.status == status_filter)
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.join(SalesOrder, WorkOrder.sales_order_id == SalesOrder.id).join(Customer, SalesOrder.customer_id == Customer.id).filter(
            or_(
                WorkOrder.work_order_no.ilike(term),
                WorkOrder.product_name.ilike(term),
                SalesOrder.order_no.ilike(term),
                SalesOrder.product_summary.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
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
    _ensure_production_board_visible(current_user)
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


@router.get("/production-flow", response_model=PageResponse[ProductionFlowRowRead])
def list_production_flow_rows(
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    production_position: str | None = None,
    cylinder_making: str | None = None,
    salesman: str | None = None,
    unfinished_only: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> PageResponse[ProductionFlowRowRead]:
    _ensure_production_board_visible(current_user)
    query = (
        db.query(WorkOrder, SalesOrder, Customer)
        .join(SalesOrder, WorkOrder.sales_order_id == SalesOrder.id)
        .join(Customer, SalesOrder.customer_id == Customer.id)
        .options(selectinload(WorkOrder.steps))
        .filter(
            WorkOrder.deleted_at.is_(None),
            SalesOrder.deleted_at.is_(None),
            SalesOrder.status != OrderStatus.CANCELLED,
        )
    )
    query = _restrict_work_orders_to_user(query, current_user)
    if date_from:
        query = query.filter(SalesOrder.order_date >= date_from)
    if date_to:
        query = query.filter(SalesOrder.order_date <= date_to)

    rows = query.order_by(SalesOrder.order_date.desc(), WorkOrder.created_at.desc()).all()
    normalized_search = (search or "").strip().lower()
    normalized_position = (production_position or "").strip().lower()
    normalized_making = (cylinder_making or "").strip().lower()
    normalized_salesman = (salesman or "").strip().lower()
    base_entries: list[tuple[WorkOrder, SalesOrder, Customer, WorkOrderStep | None, str, str | None, dict]] = []

    for work_order, sales_order, customer in rows:
        details = dict(sales_order.plate_details or {})
        current_step = _current_step(list(work_order.steps))
        cylinder_no = _plate_no_from_order(sales_order)
        salesman_text = _text_value(details.get("salesman") or details.get("sign_in_person") or customer.salesperson_name)
        position_text = _text_value(current_step.step_name if current_step else None) or _text_value(details.get("production_position"))
        making_text = _text_value(details.get("cylinder_making"))
        if unfinished_only and _row_has_finished(work_order, sales_order, current_step):
            continue
        if normalized_position and normalized_position not in (position_text or "").lower():
            continue
        if normalized_making and normalized_making not in (making_text or "").lower():
            continue
        if normalized_salesman and normalized_salesman not in (salesman_text or "").lower():
            continue
        searchable = " ".join(
            item
            for item in [
                cylinder_no,
                sales_order.order_no,
                work_order.work_order_no,
                customer.name,
                work_order.product_name,
                salesman_text or "",
                position_text or "",
                making_text or "",
            ]
            if item
        ).lower()
        if normalized_search and normalized_search not in searchable:
            continue
        base_entries.append((work_order, sales_order, customer, current_step, cylinder_no, salesman_text, details))

    total = len(base_entries)
    page_entries = base_entries[(page - 1) * page_size : page * page_size]
    work_order_ids = [entry[0].id for entry in page_entries]
    step_name_by_id: dict[UUID, str] = {}
    user_ids: set[UUID] = set()
    for work_order, *_rest in page_entries:
        for step in work_order.steps:
            step_name_by_id[step.id] = step.step_name
            if step.assigned_user_id:
                user_ids.add(step.assigned_user_id)

    process_records_by_work_order: dict[UUID, list[ProcessRecord]] = {work_order_id: [] for work_order_id in work_order_ids}
    inspections_by_work_order: dict[UUID, list[InspectionRecord]] = {work_order_id: [] for work_order_id in work_order_ids}
    reworks_by_work_order: dict[UUID, list[ReworkRecord]] = {work_order_id: [] for work_order_id in work_order_ids}
    if work_order_ids:
        for record in (
            db.query(ProcessRecord)
            .filter(ProcessRecord.work_order_id.in_(work_order_ids))
            .order_by(ProcessRecord.reported_at.desc())
            .all()
        ):
            process_records_by_work_order.setdefault(record.work_order_id, []).append(record)
            user_ids.add(record.operator_id)
        for inspection in (
            db.query(InspectionRecord)
            .filter(InspectionRecord.work_order_id.in_(work_order_ids))
            .order_by(InspectionRecord.inspected_at.desc())
            .all()
        ):
            inspections_by_work_order.setdefault(inspection.work_order_id, []).append(inspection)
            user_ids.add(inspection.inspector_id)
        for rework in (
            db.query(ReworkRecord)
            .filter(ReworkRecord.work_order_id.in_(work_order_ids))
            .order_by(ReworkRecord.created_at.desc())
            .all()
        ):
            reworks_by_work_order.setdefault(rework.work_order_id, []).append(rework)

    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_name_by_id = {user.id: user.real_name or user.username for user in users}
    flow_rows: list[ProductionFlowRowRead] = []
    for work_order, sales_order, customer, current_step, cylinder_no, salesman_text, details in page_entries:
        color_rows = list(sales_order.color_rows or [])
        color_numbers = ", ".join(
            str(row.get("color_no") or index)
            for index, row in enumerate(color_rows, start=1)
            if row.get("color_no") or row
        )
        completed_at = work_order.actual_end_at or max((step.actual_end_at for step in work_order.steps if step.actual_end_at), default=None)
        total_qty = _total_qty(details, color_rows, float(work_order.quantity))
        display_order_date = _date_value(details.get("order_date"), sales_order.order_date)
        period_end = completed_at.date() if completed_at else sales_order.due_date
        period_days = (period_end - display_order_date).days
        order_type = str(details.get("order_type") or "new_cylinder")
        customer_name = _text_value(customer.name) or _text_value(details.get("customer_text")) or "-"
        product_name = _first_text(details, "product_name") or work_order.product_name or sales_order.product_summary
        sign_in_person = _first_text(details, "sign_in_person", "receiver_name")
        lister_text = _first_text(details, "lister", "form_filler", "sign_in_person")
        print_color = _first_color_text(color_rows, "print_color")
        real_dia = _first_color_text(color_rows, "real_dia")
        dia = real_dia or _first_color_text(color_rows, "dia") or _first_text(details, "real_dia", "dia")
        step_details = [
            ProductionFlowStepRead(
                step_id=step.id,
                step_no=step.step_no,
                step_name=step.step_name,
                status=step.status,
                assigned_user_name=user_name_by_id.get(step.assigned_user_id) if step.assigned_user_id else None,
                planned_start_at=step.planned_start_at,
                planned_end_at=step.planned_end_at,
                actual_start_at=step.actual_start_at,
                actual_end_at=step.actual_end_at,
                input_qty=_float_value(step.input_qty),
                qualified_qty=_float_value(step.qualified_qty),
                defective_qty=_float_value(step.defective_qty),
                remark=step.remark,
            ).model_dump(mode="json")
            for step in work_order.steps
        ]
        process_details = [
            ProductionFlowProcessRecordRead(
                record_id=record.id,
                step_name=step_name_by_id.get(record.work_order_step_id, ""),
                operator_name=user_name_by_id.get(record.operator_id),
                action=record.action,
                processed_qty=_float_value(record.processed_qty),
                qualified_qty=_float_value(record.qualified_qty),
                defective_qty=_float_value(record.defective_qty),
                work_hours=_float_value(record.work_hours),
                reported_at=record.reported_at,
                remark=record.remark,
            ).model_dump(mode="json")
            for record in process_records_by_work_order.get(work_order.id, [])
        ]
        inspection_details = [
            ProductionFlowInspectionRead(
                inspection_id=inspection.id,
                inspection_no=inspection.inspection_no,
                step_name=step_name_by_id.get(inspection.work_order_step_id),
                inspector_name=user_name_by_id.get(inspection.inspector_id),
                result=inspection.result,
                inspected_qty=float(inspection.inspected_qty),
                passed_qty=_float_value(inspection.passed_qty),
                failed_qty=_float_value(inspection.failed_qty),
                reason=inspection.reason,
                inspected_at=inspection.inspected_at,
            ).model_dump(mode="json")
            for inspection in inspections_by_work_order.get(work_order.id, [])
        ]
        rework_details = [
            ProductionFlowReworkRead(
                rework_id=rework.id,
                rework_no=rework.rework_no,
                from_step_name=step_name_by_id.get(rework.from_step_id),
                to_step_name=step_name_by_id.get(rework.to_step_id),
                reason=rework.reason,
                quantity=float(rework.quantity),
                status=rework.status,
                completed_at=rework.completed_at,
            ).model_dump(mode="json")
            for rework in reworks_by_work_order.get(work_order.id, [])
        ]
        flow_rows.append(
            ProductionFlowRowRead(
                work_order_id=work_order.id,
                sales_order_id=sales_order.id,
                work_order_no=work_order.work_order_no,
                order_no=sales_order.order_no,
                cylinder_no=cylinder_no,
                salesman=salesman_text,
                order_date=display_order_date,
                due_date=sales_order.due_date,
                completed_date=completed_at.date() if completed_at else None,
                period=f"{period_days}days",
                customer_name=customer_name,
                product_name=product_name,
                c_value=_computed_c_text(details),
                l_value=_computed_l_text(details),
                total_qty=total_qty,
                new_base=str(total_qty).rstrip("0").rstrip(".") if order_type == "new_cylinder" else None,
                old_base=str(total_qty).rstrip("0").rstrip(".") if order_type != "new_cylinder" else None,
                production_position=_text_value(current_step.step_name if current_step else None),
                computer_position=_first_text(details, "computer_position", "production_position"),
                square=_calculate_square(details, total_qty),
                dia=dia,
                hole=_first_text(details, "hole", "inner_hole"),
                slope=_first_text(details, "slope", "obliquity"),
                keyway=_first_text(details, "key_way", "keyway", "keyway_size"),
                single_double=_first_text(details, "single_double", "set_type"),
                order_status=sales_order.status,
                work_order_status=work_order.status,
                current_step_status=current_step.status if current_step else None,
                order_by=lister_text,
                sign_in_person=sign_in_person,
                printing_method=_text_value(details.get("printing_method")),
                unit_l=_text_value(details.get("unit_l")),
                unit_w=_text_value(details.get("unit_w")),
                straight=_text_value(details.get("straight")),
                increase=_text_value(details.get("increase")),
                flange=_text_value(details.get("flange")),
                cylinder_model=_text_value(details.get("cylinder_model")),
                cylinder_making=_text_value(details.get("cylinder_making")),
                material_model=_text_value(details.get("material_model")),
                new_material=_first_text(details, "material_new", "new_material"),
                placing_member=lister_text,
                color_numbers=color_numbers or None,
                print_color=print_color,
                real_dia=real_dia,
                customer_material_qty=_first_text(details, "customer_material_qty", "self_bring"),
                production_qty=_first_text(details, "production_qty", "total_qty", "total_branch"),
                details={
                    "steps": step_details,
                    "process_records": process_details,
                    "inspections": inspection_details,
                    "reworks": rework_details,
                    "requirements": _production_requirement(details, sales_order.remark, work_order.remark).model_dump(mode="json"),
                },
            )
        )

    return PageResponse(items=flow_rows, total=total, page=page, page_size=page_size)


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


@router.get("/{work_order_id}/self-inspection-card", response_class=HTMLResponse)
def print_self_inspection_card(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> HTMLResponse:
    work_order = db.query(WorkOrder).options(selectinload(WorkOrder.steps)).filter(WorkOrder.id == work_order_id).first()
    if work_order is None or work_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")
    _ensure_work_order_visible(work_order, current_user)
    sales_order = db.get(SalesOrder, work_order.sales_order_id)
    if sales_order is None or sales_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    customer = db.get(Customer, sales_order.customer_id)
    assigned_user_ids = [step.assigned_user_id for step in work_order.steps if step.assigned_user_id]
    users = db.query(User).filter(User.id.in_(assigned_user_ids)).all() if assigned_user_ids else []
    assigned_users = {user.id: user for user in users}

    html = _self_inspection_card_html(
        work_order=work_order,
        sales_order=sales_order,
        customer=customer,
        assigned_users=assigned_users,
    )
    print_job = record_print_job(
        db,
        document_type="self_inspection_card",
        target_type="work_order",
        target_id=work_order.id,
        printed_by=current_user.id,
        snapshot=_self_inspection_snapshot(work_order=work_order, sales_order=sales_order, customer=customer),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="print_self_inspection_card",
        target_type="work_order",
        target_id=work_order.id,
        after_data={"work_order_no": work_order.work_order_no, "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)


@router.get("/{work_order_id}/process-task-sheet", response_class=HTMLResponse)
def print_process_task_sheet(
    work_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> HTMLResponse:
    work_order = db.query(WorkOrder).options(selectinload(WorkOrder.steps)).filter(WorkOrder.id == work_order_id).first()
    if work_order is None or work_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found.")
    _ensure_work_order_visible(work_order, current_user)
    sales_order = db.get(SalesOrder, work_order.sales_order_id)
    if sales_order is None or sales_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    customer = db.get(Customer, sales_order.customer_id)
    assigned_user_ids = [step.assigned_user_id for step in work_order.steps if step.assigned_user_id]
    users = db.query(User).filter(User.id.in_(assigned_user_ids)).all() if assigned_user_ids else []
    assigned_users = {user.id: user for user in users}

    html = _process_task_sheet_html(
        work_order=work_order,
        sales_order=sales_order,
        customer=customer,
        assigned_users=assigned_users,
    )
    print_job = record_print_job(
        db,
        document_type="process_task_sheet",
        target_type="work_order",
        target_id=work_order.id,
        printed_by=current_user.id,
        snapshot=_process_task_snapshot(work_order=work_order, sales_order=sales_order, customer=customer),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="print_process_task_sheet",
        target_type="work_order",
        target_id=work_order.id,
        after_data={"work_order_no": work_order.work_order_no, "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)


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
    if step.status in FINISHED_STEP_STATUSES:
        work_order = db.get(WorkOrder, step.work_order_id)
        if work_order:
            _finalize_work_order_if_ready(db, work_order, step.actual_end_at)

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
