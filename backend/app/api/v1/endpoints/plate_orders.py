from datetime import date, datetime
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
    details = order.plate_details or {}
    color_rows = order.color_rows or []
    for key in ("cylinder_id", "no", "sample_no", "original_no"):
        value = str(details.get(key) or "").strip()
        if value:
            return value
    for row in color_rows:
        for key in ("cylinder_no", "color_cylinder_no", "public_no"):
            value = str(row.get(key) or "").strip()
            if value:
                return value
    return order.order_no


def _order_type(order: SalesOrder) -> str:
    details = order.plate_details or {}
    return str(details.get("order_type") or details.get("business_type") or "new_cylinder")


def _serialize(order: SalesOrder) -> SalesOrderRead:
    return SalesOrderRead.model_validate(order)


def _h(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _print_text(value: object) -> str:
    text = str(value if value is not None else "")
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def _is_legacy_print_note(value: object) -> bool:
    text = _print_text(value)
    if not text:
        return False
    legacy_tokens = (
        "Legacy ",
        "ProductPlanID:",
        "RegNumber:",
        "CorSquRoller:",
        "TechType:",
        "ProductNote:",
        "CustomerNote:",
        "KHTSYQ:",
    )
    mojibake_tokens = ("\ufffd", "\u951f", "\u9403", "\u3085", "\u3083")
    return any(token in text for token in legacy_tokens) or any(token in text for token in mojibake_tokens)


def _business_print_text(*values: object) -> str:
    cleaned: list[str] = []
    for value in values:
        text = _print_text(value)
        if text and not _is_legacy_print_note(text) and text not in cleaned:
            cleaned.append(text)
    return "\n".join(cleaned)


def _production_order_snapshot(order: SalesOrder, customer: Customer | None) -> dict:
    details = order.plate_details or {}
    return {
        "order_no": order.order_no,
        "cylinder_no": _primary_cylinder_no(order),
        "customer_name": customer.name if customer else "",
        "product_name": order.product_summary,
        "qty": sum(float(item.quantity) for item in order.items),
        "c_value": details.get("c_value"),
        "l_value": details.get("l_value"),
        "order_datetime": details.get("order_datetime") or details.get("order_date"),
        "dia": details.get("dia"),
        "increase": details.get("increase"),
        "printing_method": details.get("printing_method"),
    }


def _order_datetime_text(order: SalesOrder) -> str:
    details = order.plate_details or {}
    value = details.get("order_datetime") or details.get("order_date") or order.order_date
    text = str(value or "").replace("T", " ").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text[:19]


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


@router.get("/{order_id}/production-order", response_class=HTMLResponse)
def print_production_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> HTMLResponse:
    order = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None))
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    customer = db.query(Customer).filter(Customer.id == order.customer_id, Customer.deleted_at.is_(None)).first()
    details = order.plate_details or {}
    color_rows = order.color_rows or []
    total_qty = sum(float(item.quantity) for item in order.items)
    cylinder_no = _primary_cylinder_no(order)

    if not color_rows:
        color_rows = [
            {
                "color_no": "1",
                "print_color": details.get("print_color") or "",
                "qty": details.get("total_qty") or f"{total_qty:g}",
                "dia": details.get("dia") or "",
                "real_dia": details.get("real_dia") or "",
                "printing_method": details.get("printing_method") or "",
                "remarks": details.get("common_remarks") or "",
            }
        ]

    production_remark = _business_print_text(
        details.get("production_requirement"),
        details.get("computer_requirement"),
        details.get("common_remarks"),
        details.get("remarks"),
        *(row.get("remarks") for row in color_rows),
        order.remark,
    )
    color_header = "".join(f"<th>{_h(row.get('color_no') or index)}</th>" for index, row in enumerate(color_rows, start=1))
    print_color_row = "".join(f"<td>{_h(row.get('print_color') or row.get('color') or '')}</td>" for row in color_rows)
    dia_row = "".join(f"<td>{_h(row.get('dia') or details.get('dia') or '')}</td>" for row in color_rows)
    real_dia_row = "".join(f"<td>{_h(row.get('real_dia') or '')}</td>" for row in color_rows)
    qty_row = "".join(f"<td>{_h(row.get('qty') or '')}</td>" for row in color_rows)
    remarks_row = "".join(f"<td class='remark-cell'>{_h(_business_print_text(row.get('remarks')))}</td>" for row in color_rows)
    order_time_text = _order_datetime_text(order)

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Production Order {order.order_no}</title>
  <style>
    @page {{ size: 297mm 70mm; margin: 4mm; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Arial, sans-serif; color: #111827; margin: 0; background: #fff; }}
    .sheet {{ width: 297mm; min-height: 70mm; max-width: none; margin: 0 auto; padding: 4mm; }}
    h1 {{ text-align: center; font-size: 18px; margin: 0 0 6px; letter-spacing: 0; line-height: 1; }}
    .actions {{ display: flex; justify-content: center; gap: 8px; margin: 10px 0; }}
    .actions button {{ border: 1px solid #111827; background: #ffffff; padding: 6px 12px; font: 700 12px Arial, sans-serif; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ border: 1px solid #111827; padding: 3.5px 4px; font-size: 10px; line-height: 1.12; text-align: center; vertical-align: middle; }}
    th {{ font-weight: 700; }}
    .left {{ text-align: left; }}
    .red {{ color: #dc2626; font-weight: 700; }}
    .production-table {{ margin-bottom: 4px; }}
    .main-data-row td {{ height: 34px; }}
    .spec-row th {{ height: 26px; }}
    .spec-value-row td {{ height: 25px; }}
    .color-table th,
    .color-table td {{ height: 22px; padding: 3px 4px; }}
    .remark-cell {{ white-space: pre-wrap; word-break: break-word; line-height: 1.25; }}
    .meta {{ display: flex; justify-content: space-between; font-size: 10px; margin-top: 5px; }}
    @media print {{
      .no-print {{ display: none !important; }}
      .sheet {{ width: 100%; min-height: 0; max-width: none; margin: 0 auto; padding: 0; }}
    }}
  </style>
</head>
<body>
  <div class="actions no-print">
    <button type="button" onclick="window.print()">PDF / Print</button>
    <button type="button" onclick="downloadPng()">PNG</button>
  </div>
  <section class="sheet" id="production-sheet">
    <h1>Bangla Platemaking Production Order</h1>
    <table class="production-table">
      <tbody>
        <tr>
          <th>Customer Name</th>
          <td colspan="3" class="left red">{_h(customer.name if customer else '')}</td>
          <th>Product Name</th>
          <td colspan="5" class="left">{_h(details.get('product_name') or order.product_summary)}</td>
          <th>Square</th>
          <td>{_h(details.get('square') or '')}</td>
        </tr>
        <tr>
          <th>NO.</th>
          <th>Printing Method</th>
          <th>QTY</th>
          <th>New</th>
          <th>Old</th>
          <th>C</th>
          <th>L</th>
          <th>Dia</th>
          <th>Increasing</th>
          <th colspan="3">Remarks</th>
        </tr>
        <tr class="red main-data-row">
          <td>{_h(cylinder_no)}</td>
          <td>{_h(details.get('printing_method') or '')}</td>
          <td>{_h(details.get('total_qty') or f'{total_qty:g}')}</td>
          <td>{_h(details.get('new_qty') or details.get('total_qty') or f'{total_qty:g}')}</td>
          <td>{_h(details.get('old_qty') or '0')}</td>
          <td>{_h(details.get('c_value') or '')}</td>
          <td>{_h(details.get('l_value') or details.get('unit_l') or '')}</td>
          <td>{_h(details.get('dia') or '')}</td>
          <td>{_h(details.get('increase') or '')}</td>
          <td colspan="3" class="remark-cell">{_h(production_remark)}</td>
        </tr>
        <tr class="spec-row">
          <th>Flange</th>
          <th>Slope</th>
          <th>Hole</th>
          <th>KeyWay</th>
          <th>Dynamic Balance</th>
          <th>Thickness</th>
          <th>Stock</th>
          <th>Copper Thickness</th>
          <th colspan="4">Plate Type</th>
        </tr>
        <tr class="red spec-value-row">
          <td>{_h(details.get('flange') or '')}</td>
          <td>{_h(details.get('slope') or '')}</td>
          <td>{_h(details.get('hole') or '')}</td>
          <td>{_h(details.get('key_way') or '')}</td>
          <td>{_h(details.get('dynamic_balance') or '')}</td>
          <td>{_h(details.get('plate_thickness') or '')}</td>
          <td>{_h(details.get('stock') or '')}</td>
          <td>{_h(details.get('copper_thickness') or '')}</td>
          <td colspan="4">{_h(details.get('plate_type') or details.get('cylinder_structure') or '')}</td>
        </tr>
      </tbody>
    </table>
    <table class="color-table">
      <tbody>
        <tr><th>PrintColor</th>{color_header}</tr>
        <tr><th>Color</th>{print_color_row}</tr>
        <tr><th>Dia</th>{dia_row}</tr>
        <tr><th>Real Dia</th>{real_dia_row}</tr>
        <tr><th>QTY</th>{qty_row}</tr>
        <tr><th>Remarks</th>{remarks_row}</tr>
      </tbody>
    </table>
    <div class="meta">
      <span>BeginTime: {_h(order_time_text)}</span>
      <span>Delivery Time: {_h(order.due_date)}</span>
      <span>Approve: {_h(current_user.real_name or current_user.username)}</span>
    </div>
  </section>
  <script>
    function collectStyles() {{
      return Array.from(document.styleSheets).map((styleSheet) => {{
        try {{
          return Array.from(styleSheet.cssRules).map((rule) => rule.cssText).join("\\n");
        }} catch (error) {{
          return "";
        }}
      }}).join("\\n");
    }}

    function downloadBlob(blob, filename) {{
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    }}

    async function downloadPng() {{
      const node = document.getElementById("production-sheet");
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const width = Math.ceil(node.scrollWidth || rect.width || 1200);
      const height = Math.ceil(node.scrollHeight || rect.height || 540);
      const clone = node.cloneNode(true);
      clone.setAttribute("xmlns", "http://www.w3.org/1999/xhtml");
      const serialized = new XMLSerializer().serializeToString(clone);
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${{width}}" height="${{height}}" viewBox="0 0 ${{width}} ${{height}}">
        <foreignObject width="100%" height="100%">
          <div xmlns="http://www.w3.org/1999/xhtml">
            <style>${{collectStyles().replace(/<\\/style/gi, "<\\\\/style")}}</style>
            ${{serialized}}
          </div>
        </foreignObject>
      </svg>`;
      const svgUrl = URL.createObjectURL(new Blob([svg], {{ type: "image/svg+xml;charset=utf-8" }}));
      const image = new Image();
      await new Promise((resolve, reject) => {{
        image.onload = resolve;
        image.onerror = reject;
        image.src = svgUrl;
      }});
      const scale = 2;
      const canvas = document.createElement("canvas");
      canvas.width = width * scale;
      canvas.height = height * scale;
      const context = canvas.getContext("2d");
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(svgUrl);
      canvas.toBlob((blob) => {{
        if (blob) downloadBlob(blob, "{_h(order.order_no)}-production-order.png");
      }}, "image/png");
    }}
  </script>
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
