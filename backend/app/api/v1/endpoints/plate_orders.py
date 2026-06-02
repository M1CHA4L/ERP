from datetime import date
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.finance import MonthlyPaymentSummary
from app.models.inventory import CylinderStock
from app.models.sales import SalesOrder
from app.models.rbac import User
from app.schemas.common import PageResponse
from app.schemas.plate import CylinderLedger
from app.schemas.sales import SalesOrderRead
from app.services.audit import log_operation
from app.services.printing import record_print_job

router = APIRouter()


def _order_cylinder_nos(order: SalesOrder) -> set[str]:
    details = order.plate_details or {}
    color_rows = order.color_rows or []
    candidates = [
        details.get("cylinder_id"),
        details.get("no"),
        details.get("sample_no"),
        details.get("original_no"),
    ]
    for row in color_rows:
        candidates.extend([row.get("public_no"), row.get("color_cylinder_no"), row.get("cylinder_no")])
    cleaned = {str(item).strip() for item in candidates if str(item or "").strip()}
    return cleaned or {order.order_no}


def _primary_cylinder_no(order: SalesOrder) -> str:
    return sorted(_order_cylinder_nos(order))[0]


def _order_type(order: SalesOrder) -> str:
    details = order.plate_details or {}
    return str(details.get("order_type") or details.get("business_type") or "new_cylinder")


def _serialize(order: SalesOrder) -> SalesOrderRead:
    return SalesOrderRead.model_validate(order)


def _h(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _production_order_snapshot(order: SalesOrder, customer: Customer | None) -> dict:
    details = order.plate_details or {}
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "customer_id": order.customer_id,
        "customer_name": customer.name if customer else None,
        "product_summary": order.product_summary,
        "order_date": order.order_date,
        "due_date": order.due_date,
        "cylinder_nos": sorted(_order_cylinder_nos(order)),
        "plate_details": details,
        "color_rows": order.color_rows or [],
    }


@router.get("", response_model=PageResponse[SalesOrderRead])
def list_plate_orders(
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    order_type: str | None = None,
    status_filter: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("order:view")),
) -> PageResponse[SalesOrderRead]:
    query = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.deleted_at.is_(None))
    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)
    if status_filter:
        query = query.filter(SalesOrder.status == status_filter)
    if date_from:
        query = query.filter(SalesOrder.order_date >= date_from)
    if date_to:
        query = query.filter(SalesOrder.order_date <= date_to)
    orders = query.order_by(SalesOrder.created_at.desc()).all()
    if cylinder_no:
        orders = [order for order in orders if cylinder_no.strip() in _order_cylinder_nos(order)]
    if order_type:
        orders = [order for order in orders if _order_type(order) == order_type]
    if keyword:
        needle = keyword.strip().lower()
        customers = {
            str(customer.id): customer.name.lower()
            for customer in db.query(Customer).filter(Customer.deleted_at.is_(None)).all()
        }

        def matches_keyword(order: SalesOrder) -> bool:
            details = order.plate_details or {}
            color_rows = order.color_rows or []
            values: list[str] = [
                order.order_no,
                order.product_summary,
                order.remark or "",
                customers.get(str(order.customer_id), ""),
            ]
            values.extend(str(value) for value in details.values() if value is not None)
            for row in color_rows:
                values.extend(str(value) for value in row.values() if value is not None)
            return any(needle in value.lower() for value in values)

        orders = [order for order in orders if matches_keyword(order)]
    total = len(orders)
    sliced = orders[(page - 1) * page_size : page * page_size]
    return PageResponse(items=[_serialize(order) for order in sliced], total=total, page=page, page_size=page_size)


@router.get("/cylinders/{cylinder_no}", response_model=CylinderLedger)
def get_cylinder_ledger(
    cylinder_no: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("cylinder:view")),
) -> CylinderLedger:
    orders = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.deleted_at.is_(None))
        .order_by(SalesOrder.order_date.desc())
        .all()
    )
    matched_orders = [order for order in orders if cylinder_no in _order_cylinder_nos(order)]
    summaries = (
        db.query(MonthlyPaymentSummary)
        .filter(MonthlyPaymentSummary.cylinder_no == cylinder_no, MonthlyPaymentSummary.deleted_at.is_(None))
        .order_by(MonthlyPaymentSummary.accounting_month.desc())
        .all()
    )
    stocks = (
        db.query(CylinderStock)
        .filter(CylinderStock.cylinder_no == cylinder_no, CylinderStock.deleted_at.is_(None))
        .order_by(CylinderStock.stock_in_date.desc())
        .all()
    )
    return CylinderLedger(
        cylinder_no=cylinder_no,
        orders=[_serialize(order) for order in matched_orders],
        monthly_receipts=summaries,
        stocks=stocks,
    )


@router.get("/{order_id}/production-order", response_class=HTMLResponse)
def print_production_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> HTMLResponse:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id).first()
    if order is None or order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    customer = db.get(Customer, order.customer_id)
    details = order.plate_details or {}
    color_rows = order.color_rows or []
    total_qty = sum(float(item.quantity) for item in order.items)
    cylinder_no = _primary_cylinder_no(order)
    color_cells = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{_h(row.get('print_color') or row.get('color') or '-')}</td>"
        f"<td>{_h(row.get('qty') or '-')}</td>"
        f"<td>{_h(row.get('dia') or '-')}</td>"
        f"<td>{_h(row.get('real_dia') or '-')}</td>"
        f"<td>{_h(row.get('public_no') or '-')}</td>"
        f"<td>{_h(row.get('printing_method') or details.get('printing_method') or '-')}</td>"
        f"<td>{_h(row.get('remarks') or '')}</td>"
        "</tr>"
        for index, row in enumerate(color_rows, start=1)
    )
    if not color_cells:
        color_cells = "<tr><td colspan='8'>No color rows</td></tr>"
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Production Order {order.order_no}</title>
  <style>
    @page {{ size: A4 landscape; margin: 9mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .sheet {{ width: 1040px; margin: 14px auto; }}
    h1 {{ text-align: center; margin: 0 0 10px; font-size: 22px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; table-layout: fixed; }}
    th, td {{ border: 1px solid #111827; padding: 5px 6px; font-size: 12px; text-align: center; vertical-align: middle; }}
    th {{ font-weight: 700; }}
    .red {{ color: #d60000; font-weight: 700; }}
    .left {{ text-align: left; }}
    .footer {{ display: flex; justify-content: space-between; font-size: 12px; margin-top: 10px; }}
  </style>
</head>
<body>
  <section class="sheet">
    <h1>Bangla Platemaking Production Order</h1>
    <table>
      <tr><th>Customer Name</th><td colspan="3" class="left">{_h(customer.name if customer else '-')}</td><th>Product Name</th><td colspan="4" class="left">{_h(details.get('product_name') or order.product_summary)}</td><th>Square</th><td>{_h(details.get('square') or '-')}</td></tr>
      <tr><th>NO.</th><td class="red">{_h(cylinder_no)}</td><th>Printing Method</th><td>{_h(details.get('printing_method') or '-')}</td><th>QTY</th><td class="red">{_h(details.get('total_qty') or f'{total_qty:g}')}</td><th>New</th><td>{_h(details.get('new_qty') or '-')}</td><th>Old</th><td>{_h(details.get('old_qty') or '-')}</td></tr>
      <tr><th>C</th><td class="red">{_h(details.get('c_value') or '-')}</td><th>L</th><td class="red">{_h(details.get('l_value') or '-')}</td><th>Dia</th><td class="red">{_h(details.get('dia') or (color_rows[0].get('dia') if color_rows else '-'))}</td><th>Increasing</th><td>{_h(details.get('increase') or details.get('increasing') or '-')}</td><th>Remarks</th><td>{_h(order.remark or details.get('remarks') or '')}</td></tr>
      <tr><th>Flange</th><td>{_h(details.get('flange') or '-')}</td><th>Slope</th><td>{_h(details.get('slope') or '-')}</td><th>Hole</th><td>{_h(details.get('hole') or '-')}</td><th>KeyWay</th><td>{_h(details.get('key_way') or '-')}</td><th>Plate Type</th><td>{_h(details.get('plate_type') or '-')}</td></tr>
      <tr><th>Diamic Balance</th><td>{_h(details.get('diamic_balance') or '-')}</td><th>Thickness</th><td>{_h(details.get('thickness') or details.get('plate_thickness') or '-')}</td><th>Stock</th><td>{_h(details.get('stock') or '-')}</td><th>Copper Thickness</th><td>{_h(details.get('copper_thickness') or '-')}</td><th>Material</th><td>{_h(details.get('material_model') or details.get('new_material') or '-')}</td></tr>
    </table>
    <table>
      <thead><tr><th>#</th><th>PrintColor</th><th>QTY</th><th>Dia</th><th>Real Dia</th><th>Public No.</th><th>Printing Method</th><th>Remarks</th></tr></thead>
      <tbody>{color_cells}</tbody>
    </table>
    <div class="footer"><span>BeginTime: {order.order_date.isoformat()}</span><span>Delivery Time: {order.due_date.isoformat()}</span><span>Approve: __________________</span></div>
  </section>
</body>
</html>
"""
    print_job = record_print_job(
        db,
        document_type="production_order",
        target_type="sales_order",
        target_id=order.id,
        printed_by=current_user.id,
        snapshot=_production_order_snapshot(order, customer),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="plate_orders",
        action="print_production_order",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)


@router.get("/workshop-daily", response_class=HTMLResponse)
def print_workshop_daily(
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:view")),
) -> HTMLResponse:
    orders = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.deleted_at.is_(None), SalesOrder.order_date >= date_from, SalesOrder.order_date <= date_to)
        .order_by(SalesOrder.order_date)
        .all()
    )
    rows = []
    total_qty = 0
    customer_ids = {order.customer_id for order in orders}
    customer_names = {
        customer.id: customer.name
        for customer in db.query(Customer).filter(Customer.id.in_(list(customer_ids))).all()
    } if customer_ids else {}
    for order in orders:
        details = order.plate_details or {}
        qty = sum(float(item.quantity) for item in order.items)
        total_qty += qty
        rows.append(
            "<tr>"
            f"<td>{_h(_primary_cylinder_no(order))}</td>"
            f"<td class='left'>{_h(customer_names.get(order.customer_id, '-'))}</td>"
            f"<td>{_h(details.get('c_value') or '-')}</td>"
            f"<td>{_h(details.get('l_value') or '-')}</td>"
            f"<td>{_h(details.get('new_qty') or f'{qty:g}')}</td>"
            f"<td>{_h(details.get('old_qty') or '0')}</td>"
            f"<td>{_h(details.get('production_position') or '-')}</td>"
            f"<td class='left'>{_h(order.remark or details.get('remarks') or '')}</td>"
            "</tr>"
        )
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Daily production plan of workshop</title>
  <style>
    @page {{ size: A4 landscape; margin: 10mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .sheet {{ width: 1000px; margin: 16px auto; }}
    h1 {{ text-align: center; border-bottom: 1px solid #111827; font-size: 22px; margin: 0 0 10px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #111827; padding: 6px; font-size: 12px; text-align: center; }}
    .left {{ text-align: left; }}
    .meta {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 8px; }}
  </style>
</head>
<body>
  <section class="sheet">
    <h1>BSPM Daily production plan of workshop</h1>
    <div class="meta"><span>Date: {date_from.isoformat()} TO {date_to.isoformat()}</span><span>PrintTime: {date.today().isoformat()}</span></div>
    <table>
      <thead><tr><th>Cylinder NO.</th><th>Customer Name</th><th>C</th><th>L</th><th>New QTY</th><th>Old QTY</th><th>Production location</th><th>Remarks</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="8">No data</td></tr>'}</tbody>
      <tfoot><tr><th colspan="4">Total</th><th>{total_qty:g}</th><th colspan="3"></th></tr></tfoot>
    </table>
  </section>
</body>
</html>
"""
    print_job = record_print_job(
        db,
        document_type="workshop_daily",
        target_type="workshop_daily",
        printed_by=current_user.id,
        snapshot={
            "date_from": date_from,
            "date_to": date_to,
            "order_count": len(orders),
            "total_qty": total_qty,
            "order_nos": [order.order_no for order in orders],
        },
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="plate_orders",
        action="print_workshop_daily",
        target_type="workshop_daily",
        after_data={"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)
