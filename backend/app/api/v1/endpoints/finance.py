import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.finance import (
    CustomerStatementRun,
    MonthlyPaymentSummary,
    Payment,
    Receivable,
    ReceiptAllocation,
    ReceiptDailyEntry,
)
from app.models.logistics import DeliveryOrder
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.common import PageResponse
from app.schemas.finance import (
    CreateReceivableRequest,
    CustomerStatementCreate,
    CustomerStatementRead,
    MonthCloseRequest,
    MonthlyPaymentSummaryRead,
    PaymentCreate,
    PaymentRead,
    ReceivableRead,
    ReceiptDailyEntryCreate,
    ReceiptDailyEntryRead,
)
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.numbering import generate_number
from app.services.printing import record_print_job
from app.services.state_machine import OrderStatus

router = APIRouter()

FINANCE_MODULE_ROLES = {"admin", "boss", "finance"}
BILL_PRICE_APPROVER_ROLES = {"admin", "boss"}
VAT_RATE = Decimal("0.15")


def _has_finance_module_role(current_user: User) -> bool:
    return any(role.code in FINANCE_MODULE_ROLES for role in current_user.roles)


def _assert_finance_module_role(current_user: User) -> None:
    if not _has_finance_module_role(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Finance module access requires finance role.")


def _has_bill_price_approver_role(current_user: User) -> bool:
    return any(role.code in BILL_PRICE_APPROVER_ROLES for role in current_user.roles)


def _assert_bill_price_approver_role(current_user: User) -> None:
    if not _has_bill_price_approver_role(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bill price approval requires boss/admin role.")


def _assert_receivable_scope(current_user: User, sales_order_id: UUID | None) -> None:
    if _has_finance_module_role(current_user):
        return
    if sales_order_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Receivable ledger access requires finance role.")


def _decimal(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _next_month(value: date) -> date:
    return date(value.year + (1 if value.month == 12 else 0), 1 if value.month == 12 else value.month + 1, 1)


def _money(value: Decimal | float | int | None) -> str:
    return f"{_decimal(value):,.2f}"


def _numeric_decimal(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return Decimal(match.group(0)) if match else Decimal("0")


def _round_2(value: Decimal | float | int | None) -> Decimal:
    return _decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _bill_decimal(value: Decimal | float | int | None) -> str:
    return f"{_round_2(value):,.2f}"


def _bill_amount(value: Decimal | float | int | None) -> str:
    return f"{_decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP):,.0f}"


def _length_cm(value: object) -> str:
    number = _numeric_decimal(value)
    if number == 0:
        return ""
    return _bill_decimal(number / Decimal("10"))


def _h(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _document_header(title: str, document_no: str, document_date: date | str, customer: Customer | None, *, label: str = "Name") -> str:
    date_text = document_date.isoformat() if isinstance(document_date, date) else str(document_date)
    customer_name = customer.name if customer else "-"
    address = customer.address if customer and customer.address else ""
    return f"""
    <header class="doc-header">
      <div class="brand-row">
        <div class="logo-mark">
          <span class="logo-left">B</span><span class="logo-right">S</span>
        </div>
        <div class="brand-text">
          <div class="company-en">Bangla Shanghai Plate Making Ltd.</div>
          <div class="company-zh">孟加拉上海制版有限公司</div>
          <div class="doc-title">{_h(title)}</div>
        </div>
      </div>
      <div class="doc-meta">
        <div>
          <div>{_h(label)}: <strong>{_h(customer_name)}</strong></div>
          <div>Address: {_h(address)}</div>
        </div>
        <div class="doc-meta-right">
          <div>No. {_h(document_no)}</div>
          <div>Date: {_h(date_text)}</div>
        </div>
      </div>
    </header>
"""


def _first_selected_cylinder(order: SalesOrder, selected: set[str]) -> str:
    matches = [cylinder_no for cylinder_no in _order_cylinder_nos(order) if cylinder_no in selected]
    return matches[0] if matches else next(iter(_order_cylinder_nos(order)))


def _order_quantity(order: SalesOrder) -> Decimal:
    item_total = sum((_decimal(item.quantity) for item in order.items), Decimal("0"))
    if item_total:
        return item_total
    details = order.plate_details or {}
    return _decimal(details.get("total_qty") or details.get("new_qty") or details.get("old_qty") or 0)


def _order_size(order: SalesOrder) -> tuple[str, str]:
    details = order.plate_details or {}
    return (
        _length_cm(details.get("c_value") or details.get("c") or details.get("cylinder_circumference")),
        _length_cm(details.get("l_value") or details.get("l") or details.get("cylinder_length") or details.get("unit_l")),
    )


def _statement_orders(db: Session, statement: CustomerStatementRun) -> list[SalesOrder]:
    selected = {str(cylinder_no).strip() for cylinder_no in statement.selected_cylinder_nos if str(cylinder_no).strip()}
    start = _month_start(statement.statement_month)
    end = _next_month(start)
    orders = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(
            SalesOrder.customer_id == statement.customer_id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.order_date >= start,
            SalesOrder.order_date < end,
        )
        .order_by(SalesOrder.order_date.asc(), SalesOrder.order_no.asc())
        .all()
    )
    return [order for order in orders if _order_cylinder_nos(order) & selected]


def _quantity_text(value: Decimal) -> str:
    return f"{value:g}" if value else ""


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


def _sum_order_receivable(db: Session, customer_id: UUID, cylinder_no: str, accounting_month: date) -> Decimal:
    start = _month_start(accounting_month)
    end = _next_month(start)
    orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.customer_id == customer_id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.order_date >= start,
            SalesOrder.order_date < end,
        )
        .all()
    )
    return sum((_decimal(order.total_amount) for order in orders if cylinder_no in _order_cylinder_nos(order)), Decimal("0"))


def _matching_orders_by_cylinder(
    db: Session,
    *,
    cylinder_no: str,
    accounting_month: date,
    customer_id: UUID | None = None,
) -> list[SalesOrder]:
    start = _month_start(accounting_month)
    end = _next_month(start)
    query = db.query(SalesOrder).filter(
        SalesOrder.deleted_at.is_(None),
        SalesOrder.order_date >= start,
        SalesOrder.order_date < end,
    )
    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)
    return [order for order in query.all() if cylinder_no in _order_cylinder_nos(order)]


def _previous_due(db: Session, customer_id: UUID, cylinder_no: str, accounting_month: date) -> Decimal:
    previous = (
        db.query(MonthlyPaymentSummary)
        .filter(
            MonthlyPaymentSummary.customer_id == customer_id,
            MonthlyPaymentSummary.cylinder_no == cylinder_no,
            MonthlyPaymentSummary.accounting_month < _month_start(accounting_month),
            MonthlyPaymentSummary.deleted_at.is_(None),
        )
        .order_by(MonthlyPaymentSummary.accounting_month.desc())
        .first()
    )
    return _decimal(previous.due_amount) if previous else Decimal("0")


def _receipt_html(receipt: ReceiptDailyEntry, customer: Customer | None) -> str:
    month_text = receipt.received_date.strftime("%B %Y")
    allocation_rows = "".join(
        "<tr>"
        f"<td>{_h(allocation.cylinder_no)}</td>"
        f"<td>{allocation.accounting_month.strftime('%y/%m')}</td>"
        f"<td>{_h(allocation.remark or '')}</td>"
        f"<td class='num'>{_money(allocation.amount)}</td>"
        "</tr>"
        for allocation in receipt.allocations
    )
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Money Receipt {receipt.receipt_no}</title>
  <style>
    @page {{ size: A5 landscape; margin: 10mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .receipt {{ width: 780px; margin: 18px auto; border: 1px solid #111827; padding: 18px 26px; }}
    h1, h2, h3 {{ text-align: center; margin: 0; font-weight: 700; }}
    h1 {{ font-size: 18px; }}
    h2 {{ font-size: 16px; margin-top: 2px; }}
    h3 {{ font-size: 15px; margin-top: 6px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #111827; padding: 6px 7px; font-size: 12px; }}
    .meta {{ display: flex; justify-content: space-between; gap: 20px; margin-top: 10px; font-size: 12px; }}
    .num {{ text-align: right; }}
    .stamp {{ display: inline-block; border: 2px solid #111827; padding: 4px 18px; }}
    .signatures {{ display: flex; justify-content: space-between; margin-top: 32px; font-size: 12px; }}
    .muted {{ color: #374151; }}
  </style>
</head>
<body>
  <section class="receipt">
    <h1>Bangla Shanghai Plate Making Ltd.</h1>
    <h2>Money Receipt</h2>
    <h3>No. {receipt.receipt_no}</h3>
    <div class="meta"><span>Customer Name: <strong>{_h(customer.name if customer else receipt.customer_id)}</strong></span><span>Date: {receipt.received_date.isoformat()}</span></div>
    <div class="meta"><span>Description: {_h(receipt.abstract or month_text)}</span><span>Payments: {_h(receipt.payment_method)}</span></div>
    <table>
      <thead><tr><th>Cylinder No.</th><th>Month</th><th>Remark</th><th>Received Amount (Tk)</th></tr></thead>
      <tbody>{allocation_rows}</tbody>
      <tfoot><tr><th colspan="3">Total</th><th class="num">{_money(receipt.total_amount)}</th></tr></tfoot>
    </table>
    <div class="meta"><span>Cash: {_money(receipt.cash_amount)}</span><span>Bank/Cheque: {_money(receipt.bank_amount)}</span><span>Other: {_money(receipt.other_amount)}</span></div>
    <div class="meta"><span class="stamp">For internal use only</span><span>Payee: {_h(receipt.payee_name or '-')}</span></div>
    <div class="signatures"><span>Salesman: {_h(receipt.salesman_name or '-')}</span><span>Received By: __________________</span></div>
  </section>
</body>
</html>
"""


def _statement_html(statement: CustomerStatementRun, customer: Customer | None) -> str:
    cylinder_rows = "".join(f"<tr><td>{index}</td><td>{_h(cylinder_no)}</td></tr>" for index, cylinder_no in enumerate(statement.selected_cylinder_nos, start=1))
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Invoice {statement.statement_no}</title>
  <style>
    @page {{ size: A4; margin: 16mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .bill {{ width: 760px; margin: 20px auto; padding: 28px; border: 1px solid #111827; }}
    h1, h2, h3 {{ text-align: center; margin: 0; }}
    h1 {{ font-size: 21px; }}
    h2 {{ font-size: 18px; margin-top: 2px; }}
    h3 {{ font-size: 27px; margin-top: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 14px; }}
    th, td {{ border: 1px solid #111827; padding: 7px; font-size: 12px; }}
    .meta {{ display: flex; justify-content: space-between; gap: 24px; margin-top: 12px; font-size: 12px; }}
    .num {{ text-align: right; }}
    .footer {{ margin-top: 36px; font-size: 12px; }}
  </style>
</head>
<body>
  <section class="bill">
    <h1>Bangla Shanghai Plate Making Ltd.</h1>
    <h2>孟加拉上海制版有限公司</h2>
    <h3>Invoice/Bill</h3>
    <div class="meta"><span>Name: <strong>{_h(customer.name if customer else statement.customer_id)}</strong></span><span>No. {statement.statement_no}</span></div>
    <div class="meta"><span>Month: {statement.statement_month.strftime('%B %Y')}</span><span>Date: {date.today().isoformat()}</span></div>
    <table>
      <thead><tr><th>SI</th><th>Cylinder No.</th></tr></thead>
      <tbody>{cylinder_rows}</tbody>
    </table>
    <table>
      <tbody>
        <tr><th>Previous balance (Tk)</th><td class="num">{_money(statement.previous_balance)}</td></tr>
        <tr><th>Current receivable (Tk)</th><td class="num">{_money(statement.current_receivable)}</td></tr>
        <tr><th>Received (Tk)</th><td class="num">{_money(statement.received_amount)}</td></tr>
        <tr><th>Total due (Tk)</th><td class="num">{_money(statement.due_amount)}</td></tr>
      </tbody>
    </table>
    <p class="footer">Payment Bank Details: Company Name: Bangla Shanghai Plate Making Limited.</p>
    <p class="footer">Authorized Signature: __________________________</p>
  </section>
</body>
</html>
"""


def _receipt_html_v2(receipt: ReceiptDailyEntry, customer: Customer | None) -> str:
    month_text = receipt.received_date.strftime("%B %Y")
    allocations = receipt.allocations or []
    allocation_rows = "".join(
        "<tr>"
        f"<td>{_h(allocation.remark or allocation.accounting_month.strftime('%B %Y'))}</td>"
        f"<td>{_h(allocation.cylinder_no)}</td>"
        f"<td>{receipt.received_date.strftime('%d-%m-%Y')}</td>"
        f"<td>{_h(receipt.payment_method)}</td>"
        f"<td class='num'>{_money(receipt.other_amount if index == 1 else 0)}</td>"
        f"<td class='num'>{_money(allocation.amount)}</td>"
        "</tr>"
        for index, allocation in enumerate(allocations, start=1)
    )
    if not allocation_rows:
        allocation_rows = (
            "<tr>"
            f"<td>{_h(receipt.abstract or month_text)}</td>"
            f"<td>{_h(receipt.receipt_no)}</td>"
            f"<td>{receipt.received_date.strftime('%d-%m-%Y')}</td>"
            f"<td>{_h(receipt.payment_method)}</td>"
            f"<td class='num'>{_money(receipt.other_amount)}</td>"
            f"<td class='num'>{_money(receipt.total_amount)}</td>"
            "</tr>"
        )
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Money Receipt {receipt.receipt_no}</title>
  <style>
    @page {{ size: A5 landscape; margin: 8mm; }}
    body {{ font-family: "Courier New", Arial, 'Microsoft YaHei', sans-serif; color: #111; margin: 0; }}
    .receipt {{ width: 840px; margin: 12px auto; padding: 16px 24px 20px; }}
    .brand-row {{ display: grid; grid-template-columns: 82px 1fr 82px; align-items: center; }}
    .logo-mark {{ width: 58px; height: 58px; border: 2px solid #5b214f; color: #5b214f; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 23px; letter-spacing: -2px; transform: skew(-8deg); }}
    .logo-left {{ color: #5b214f; }}
    .logo-right {{ color: #b82742; margin-left: -4px; }}
    .brand-text {{ text-align: center; }}
    .company-en {{ color: #3f2f5f; font-size: 18px; font-weight: 800; }}
    .company-zh {{ font-size: 18px; font-weight: 800; margin-top: 2px; }}
    .doc-title {{ font-size: 20px; font-weight: 800; letter-spacing: 1px; margin-top: 3px; }}
    .doc-meta {{ display: flex; justify-content: space-between; gap: 28px; margin-top: 8px; font-size: 12px; }}
    .doc-meta-right {{ min-width: 170px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ border: 1px solid #111; padding: 5px 6px; font-size: 12px; text-align: center; }}
    .num {{ text-align: right; }}
    .total-line {{ display: grid; grid-template-columns: 1fr 170px; border: 1px solid #111; border-top: 0; font-size: 12px; }}
    .total-line > div {{ padding: 5px 6px; }}
    .total-line > div + div {{ border-left: 1px solid #111; text-align: right; }}
    .meta {{ display: flex; justify-content: space-between; gap: 20px; margin-top: 10px; font-size: 12px; }}
    .stamp {{ display: inline-block; border: 2px solid #111; padding: 3px 18px; }}
    .signatures {{ display: flex; justify-content: space-between; margin-top: 32px; font-size: 12px; }}
  </style>
</head>
<body>
  <section class="receipt">
    {_document_header("Money Receipt", receipt.receipt_no, receipt.received_date, customer, label="Customer Name")}
    <table>
      <thead><tr><th>Description</th><th>No.</th><th>Deposit Date</th><th>Payments</th><th>Other income</th><th>Received Amount(Tk)</th></tr></thead>
      <tbody>{allocation_rows}</tbody>
    </table>
    <div class="total-line"><div>Total in Total: {_h(receipt.abstract or month_text)}</div><div>Total&nbsp;&nbsp;{_money(receipt.total_amount)}</div></div>
    <div class="meta"><span>Cash: {_money(receipt.cash_amount)}</span><span>Bank/Cheque: {_money(receipt.bank_amount)}</span><span>Other: {_money(receipt.other_amount)}</span></div>
    <div class="meta"><span class="stamp">For internal use only</span><span>Payee: {_h(receipt.payee_name or '-')}</span></div>
    <div class="signatures"><span>Salesman: {_h(receipt.salesman_name or '-')}</span><span>Received By: __________________</span></div>
  </section>
</body>
</html>
"""


def _statement_html_v2(statement: CustomerStatementRun, customer: Customer | None, db: Session, *, with_header: bool = True) -> str:
    selected = {str(cylinder_no).strip() for cylinder_no in statement.selected_cylinder_nos if str(cylinder_no).strip()}
    orders = _statement_orders(db, statement)
    total_new = Decimal("0")
    total_old = Decimal("0")
    line_rows = []
    for index, order in enumerate(orders, start=1):
        details = order.plate_details or {}
        first_item = order.items[0] if order.items else None
        quantity = _order_quantity(order)
        is_old = str(details.get("order_type") or "new_cylinder") == "old_cylinder"
        if is_old:
            total_old += quantity
        else:
            total_new += quantity
        c_size, l_size = _order_size(order)
        unit_price = _decimal(first_item.unit_price if first_item else 0)
        price_per_pc = (_decimal(order.total_amount) / quantity) if quantity else Decimal("0")
        line_rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{order.order_date.strftime('%d/%m/%Y')}</td>"
            f"<td>{_h(_first_selected_cylinder(order, selected))}</td>"
            f"<td class='product-name'>{_h(details.get('product_name') or (first_item.product_name if first_item else order.product_summary))}</td>"
            f"<td>{_h(c_size)}</td>"
            f"<td>{_h(l_size)}</td>"
            f"<td class='num'>{_bill_decimal(unit_price)}</td>"
            f"<td class='num'>{_bill_decimal(price_per_pc)}</td>"
            f"<td>{_quantity_text(quantity) if not is_old else ''}</td>"
            f"<td>{_quantity_text(quantity) if is_old else ''}</td>"
            f"<td class='num'>{_bill_amount(order.total_amount)}</td>"
            "</tr>"
        )
    if not line_rows:
        line_rows.append(
            "<tr>"
            "<td>1</td><td></td>"
            f"<td>{_h(', '.join(statement.selected_cylinder_nos))}</td>"
            "<td class='product-name'>Selected cylinders</td><td></td><td></td><td></td><td></td><td></td><td></td>"
            f"<td class='num'>{_bill_amount(statement.current_receivable)}</td>"
            "</tr>"
        )
    rows_html = "".join(line_rows)
    bill_date = date.today()
    vat_amount = _round_2(_decimal(statement.current_receivable) * VAT_RATE)
    total_receivable = _round_2(_decimal(statement.current_receivable) + vat_amount)
    header_html = (
        _document_header("Invoice/Bill", statement.statement_no, bill_date, customer)
        if with_header
        else f"""
    <header class="doc-header compact-header">
      <div class="doc-title">Invoice/Bill</div>
      <div class="doc-meta">
        <div>
          <div>Name: <strong>{_h(customer.name if customer else "-")}</strong></div>
          <div>Address: {_h(customer.address if customer and customer.address else "")}</div>
        </div>
        <div class="doc-meta-right">
          <div>No. {_h(statement.statement_no)}</div>
          <div>Date: {_h(bill_date.isoformat())}</div>
        </div>
      </div>
    </header>
"""
    )
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Invoice {statement.statement_no}</title>
  <style>
    @page {{ size: A4; margin: 14mm; }}
    body {{ font-family: "Courier New", Arial, 'Microsoft YaHei', sans-serif; color: #111; margin: 0; }}
    .bill {{ width: 780px; margin: 0 auto; padding: 14px 10px 28px; }}
    .brand-row {{ display: grid; grid-template-columns: 82px 1fr 82px; align-items: center; }}
    .logo-mark {{ width: 58px; height: 58px; border: 2px solid #5b214f; color: #5b214f; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 23px; letter-spacing: -2px; transform: skew(-8deg); }}
    .logo-left {{ color: #5b214f; }}
    .logo-right {{ color: #b82742; margin-left: -4px; }}
    .brand-text {{ text-align: center; }}
    .company-en {{ color: #3f2f5f; font-size: 23px; font-weight: 800; }}
    .company-zh {{ font-size: 24px; font-weight: 800; margin-top: 3px; }}
    .doc-title {{ font-size: 28px; font-weight: 800; letter-spacing: 2px; margin-top: 4px; }}
    .compact-header .doc-title {{ text-align: center; margin-top: 0; }}
    .doc-meta {{ display: flex; justify-content: space-between; gap: 28px; margin-top: 8px; font-size: 13px; }}
    .doc-meta-right {{ min-width: 190px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border: 1px solid #111; padding: 5px 4px; font-size: 11px; text-align: center; vertical-align: middle; }}
    .product-name {{ line-height: 1.25; }}
    .num {{ text-align: right; }}
    .summary {{ margin-left: auto; width: 300px; margin-top: 0; }}
    .summary th {{ text-align: left; }}
    .amount-words {{ border: 1px solid #111; border-top: 0; padding: 8px 6px; min-height: 38px; font-size: 12px; }}
    .bank {{ margin-top: 8px; font-size: 12px; line-height: 1.35; }}
    .signature {{ margin-top: 64px; font-size: 12px; }}
  </style>
</head>
<body>
  <section class="bill">
    {header_html}
    <table>
      <thead>
        <tr><th>SI</th><th>Date</th><th>Cylinder No.</th><th>Product Name</th><th colspan="2">Size(cm)</th><th>Rate/cm2</th><th>Price/Pc</th><th>New QTY</th><th>Old QTY</th><th>Amount(TK)</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
      <tfoot><tr><th colspan="8">Total</th><th>{_quantity_text(total_new)}</th><th>{_quantity_text(total_old)}</th><th class="num">{_bill_amount(statement.current_receivable)}</th></tr></tfoot>
    </table>
    <table class="summary">
      <tbody>
        <tr><th>VAT 15%</th><td class="num">{_bill_decimal(vat_amount)}</td></tr>
        <tr><th>Total Receivable(TK)</th><td class="num">{_bill_decimal(total_receivable)}</td></tr>
      </tbody>
    </table>
    <div class="amount-words">Total In Receivable: {_bill_decimal(total_receivable)} TK ONLY</div>
    <div class="bank">Payment Bank Details: Company Name: Bangla Shanghai Plate Making Limited. Bank Name: Dutch Bangla Bank PLC. Bank Account No: 101-308-0001081 Branch: Local Office, Dhaka Routing No: 090273889</div>
    <div class="signature">Authorized Signature: __________________________</div>
  </section>
</body>
</html>
"""


def _receipt_snapshot(receipt: ReceiptDailyEntry, customer: Customer | None) -> dict:
    return {
        "receipt_no": receipt.receipt_no,
        "customer_id": receipt.customer_id,
        "customer_name": customer.name if customer else None,
        "received_date": receipt.received_date,
        "payment_method": receipt.payment_method,
        "cash_amount": receipt.cash_amount,
        "bank_amount": receipt.bank_amount,
        "other_amount": receipt.other_amount,
        "total_amount": receipt.total_amount,
        "allocations": [
            {
                "cylinder_no": allocation.cylinder_no,
                "accounting_month": allocation.accounting_month,
                "amount": allocation.amount,
                "remark": allocation.remark,
            }
            for allocation in receipt.allocations
        ],
    }


def _statement_snapshot(statement: CustomerStatementRun, customer: Customer | None, *, with_header: bool = True) -> dict:
    vat_amount = _round_2(_decimal(statement.current_receivable) * VAT_RATE)
    return {
        "statement_no": statement.statement_no,
        "customer_id": statement.customer_id,
        "customer_name": customer.name if customer else None,
        "statement_month": statement.statement_month,
        "selected_cylinder_nos": statement.selected_cylinder_nos,
        "previous_balance": statement.previous_balance,
        "current_receivable": statement.current_receivable,
        "received_amount": statement.received_amount,
        "due_amount": statement.due_amount,
        "vat_rate": float(VAT_RATE),
        "vat_amount": float(vat_amount),
        "total_receivable_with_vat": float(_round_2(_decimal(statement.current_receivable) + vat_amount)),
        "with_header": with_header,
        "price_approval_status": statement.price_approval_status,
        "price_approved_at": statement.price_approved_at,
        "price_approved_by": statement.price_approved_by,
        "status": statement.status,
    }


def _customer_name_map(db: Session, customer_ids: set[UUID]) -> dict[UUID, str]:
    if not customer_ids:
        return {}
    customers = db.query(Customer).filter(Customer.id.in_(list(customer_ids))).all()
    return {customer.id: customer.name for customer in customers}


def _allocation_text(allocations: list[ReceiptAllocation]) -> str:
    return "; ".join(
        f"{allocation.cylinder_no} {allocation.accounting_month.strftime('%y/%m')} {_money(allocation.amount)}"
        for allocation in allocations
    )


def _order_cylinder_text(order: SalesOrder | None) -> str:
    if order is None:
        return ""
    return ", ".join(sorted(_order_cylinder_nos(order)))


def _receivable_reads(db: Session, receivables: list[Receivable]) -> list[ReceivableRead]:
    order_ids = {receivable.sales_order_id for receivable in receivables if receivable.sales_order_id}
    orders = {}
    if order_ids:
        orders = {order.id: order for order in db.query(SalesOrder).filter(SalesOrder.id.in_(list(order_ids))).all()}
    return [
        ReceivableRead.model_validate(receivable).model_copy(
            update={"cylinder_no": _order_cylinder_text(orders.get(receivable.sales_order_id))}
        )
        for receivable in receivables
    ]


def _filter_receivable_reads(db: Session, reads: list[ReceivableRead], keyword: str | None) -> list[ReceivableRead]:
    needle = str(keyword or "").strip().lower()
    if not needle:
        return reads
    customer_names = _customer_name_map(db, {item.customer_id for item in reads})
    order_ids = {item.sales_order_id for item in reads if item.sales_order_id}
    orders = {}
    if order_ids:
        orders = {order.id: order for order in db.query(SalesOrder).filter(SalesOrder.id.in_(list(order_ids))).all()}

    def haystack(item: ReceivableRead) -> str:
        order = orders.get(item.sales_order_id)
        parts = [
            item.receivable_no,
            item.cylinder_no,
            item.source_type,
            item.finance_status,
            item.status,
            item.remark,
            customer_names.get(item.customer_id),
            order.order_no if order else None,
            order.product_summary if order else None,
        ]
        return " ".join(str(part or "").lower() for part in parts)

    return [item for item in reads if needle in haystack(item)]


@router.get("/receivables", response_model=PageResponse[ReceivableRead])
def list_receivables(
    status_filter: str | None = None,
    sales_order_id: UUID | None = None,
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    keyword: str | None = None,
    overdue_only: bool = False,
    include_archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receivable:view")),
) -> PageResponse[ReceivableRead]:
    _assert_receivable_scope(current_user, sales_order_id)
    query = db.query(Receivable).filter(Receivable.deleted_at.is_(None))
    if status_filter == "archived":
        query = query.filter(Receivable.status == "archived")
    elif status_filter:
        query = query.filter(Receivable.finance_status == status_filter)
    elif not include_archived:
        query = query.filter(Receivable.status != "archived")
    if sales_order_id:
        query = query.filter(Receivable.sales_order_id == sales_order_id)
    if customer_id:
        query = query.filter(Receivable.customer_id == customer_id)
    if overdue_only:
        query = query.filter(Receivable.balance_amount > 0, Receivable.due_date < date.today())
    ordered = query.order_by(Receivable.created_at.desc())
    if cylinder_no or keyword:
        all_items = ordered.all()
        reads = _receivable_reads(db, all_items)
        if cylinder_no:
            needle = cylinder_no.strip().lower()
            reads = [item for item in reads if needle in (item.cylinder_no or "").lower()]
        reads = _filter_receivable_reads(db, reads, keyword)
        total = len(reads)
        items = reads[(page - 1) * page_size : page * page_size]
    else:
        total = query.count()
        rows = ordered.offset((page - 1) * page_size).limit(page_size).all()
        items = _receivable_reads(db, rows)
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/receivables/export")
def export_receivables(
    status_filter: str | None = None,
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    keyword: str | None = None,
    overdue_only: bool = False,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    _assert_finance_module_role(current_user)
    query = db.query(Receivable).filter(Receivable.deleted_at.is_(None))
    if status_filter == "archived":
        query = query.filter(Receivable.status == "archived")
    elif status_filter:
        query = query.filter(Receivable.finance_status == status_filter)
    elif not include_archived:
        query = query.filter(Receivable.status != "archived")
    if customer_id:
        query = query.filter(Receivable.customer_id == customer_id)
    if overdue_only:
        query = query.filter(Receivable.balance_amount > 0, Receivable.due_date < date.today())
    receivables = query.order_by(Receivable.created_at.desc()).all()
    reads = _receivable_reads(db, receivables)
    if cylinder_no:
        needle = cylinder_no.strip().lower()
        reads = [item for item in reads if needle in (item.cylinder_no or "").lower()]
    reads = _filter_receivable_reads(db, reads, keyword)
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="export_receivables",
        target_type="receivable",
        after_data={"count": len(reads)},
    )
    db.commit()
    return build_xlsx_response(
        "receivables.xlsx",
        ["应收编号", "来源", "版号", "应收金额(Tk)", "已收金额(Tk)", "未收金额(Tk)", "到期日", "开票状态", "财务状态", "状态", "备注"],
        [
            [
                receivable.receivable_no,
                receivable.source_type,
                receivable.cylinder_no or "",
                float(receivable.amount),
                float(receivable.received_amount),
                float(receivable.balance_amount),
                receivable.due_date.isoformat(),
                receivable.invoice_status,
                receivable.finance_status,
                receivable.status,
                receivable.remark or "",
            ]
            for receivable in reads
        ],
    )


@router.post("/delivery-orders/{delivery_id}/receivable", response_model=ReceivableRead, status_code=status.HTTP_201_CREATED)
def create_receivable_from_delivery(
    delivery_id: UUID,
    payload: CreateReceivableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receivable:create")),
) -> ReceivableRead:
    delivery = db.query(DeliveryOrder).filter(DeliveryOrder.id == delivery_id).with_for_update().first()
    if delivery is None or delivery.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery order not found.")
    if delivery.status != "signed":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery must be signed before receivable creation.")
    existing = (
        db.query(Receivable)
        .filter(Receivable.delivery_order_id == delivery.id, Receivable.deleted_at.is_(None), Receivable.status != "cancelled")
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Receivable already exists for this delivery.")

    order = db.get(SalesOrder, delivery.sales_order_id)
    customer = db.get(Customer, delivery.customer_id)
    if order is None or customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order or customer not found.")

    amount = Decimal(str(payload.amount if payload.amount is not None else order.total_amount))
    due_base = delivery.signed_at.date() if delivery.signed_at else delivery.delivery_time.date()
    receivable = Receivable(
        receivable_no=generate_number("AR"),
        sales_order_id=order.id,
        delivery_order_id=delivery.id,
        customer_id=customer.id,
        amount=amount,
        received_amount=Decimal("0"),
        balance_amount=amount,
        due_date=due_base + timedelta(days=customer.payment_terms_days),
        source_type="delivery",
        invoice_status="pending",
        finance_status="pending_invoice",
        status="active",
    )
    order.status = OrderStatus.PENDING_PAYMENT
    db.add(receivable)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="create_receivable",
        target_type="receivable",
        target_id=receivable.id,
        after_data={"receivable_no": receivable.receivable_no, "amount": float(receivable.amount)},
    )
    db.commit()
    db.refresh(receivable)
    return _receivable_reads(db, [receivable])[0]


@router.get("/receivables/{receivable_id}/payments", response_model=list[PaymentRead])
def list_payments(
    receivable_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receivable:view")),
) -> list[Payment]:
    _assert_finance_module_role(current_user)
    return db.query(Payment).filter(Payment.receivable_id == receivable_id, Payment.deleted_at.is_(None)).order_by(Payment.payment_date.desc()).all()


@router.post("/receivables/{receivable_id}/archive", response_model=ReceivableRead)
def archive_receivable(
    receivable_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:adjust")),
) -> ReceivableRead:
    receivable = db.query(Receivable).filter(Receivable.id == receivable_id).with_for_update().first()
    if receivable is None or receivable.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receivable not found.")
    if receivable.status == "archived":
        return _receivable_reads(db, [receivable])[0]
    if receivable.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cancelled receivable cannot be archived.")
    if _decimal(receivable.balance_amount) > 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only fully paid receivables can be archived.")

    receivable.status = "archived"
    receivable.finance_status = "closed"
    order = db.get(SalesOrder, receivable.sales_order_id) if receivable.sales_order_id else None
    if order and order.deleted_at is None:
        order.status = OrderStatus.ARCHIVED

    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="archive_receivable",
        target_type="receivable",
        target_id=receivable.id,
        after_data={
            "receivable_no": receivable.receivable_no,
            "sales_order_id": str(receivable.sales_order_id) if receivable.sales_order_id else None,
        },
    )
    db.commit()
    db.refresh(receivable)
    return _receivable_reads(db, [receivable])[0]


@router.post("/receivables/{receivable_id}/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    receivable_id: UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:payment:create")),
) -> Payment:
    receivable = db.query(Receivable).filter(Receivable.id == receivable_id).with_for_update().first()
    if receivable is None or receivable.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receivable not found.")
    if receivable.status in {"cancelled", "archived"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cancelled or archived receivable cannot accept payments.")
    amount = Decimal(str(payload.amount))
    if amount > receivable.balance_amount:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payment amount cannot exceed receivable balance.")
    reference_no = payload.reference_no.strip() if payload.reference_no else None
    if reference_no:
        duplicate = (
            db.query(Payment)
            .filter(
                Payment.receivable_id == receivable.id,
                Payment.reference_no == reference_no,
                Payment.deleted_at.is_(None),
                Payment.reversed_payment_id.is_(None),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reference no already exists for this receivable.")

    payment = Payment(
        payment_no=generate_number("PAY"),
        receivable_id=receivable.id,
        customer_id=receivable.customer_id,
        amount=amount,
        payment_date=payload.payment_date,
        payment_method=payload.payment_method,
        reference_no=reference_no,
        remark=payload.remark,
    )
    receivable.received_amount = Decimal(str(receivable.received_amount or 0)) + amount
    receivable.balance_amount = max(Decimal("0"), Decimal(str(receivable.amount)) - Decimal(str(receivable.received_amount)))
    if receivable.balance_amount <= 0:
        receivable.finance_status = "closed"
        receivable.status = "closed"
        order = db.get(SalesOrder, receivable.sales_order_id) if receivable.sales_order_id else None
        if order:
            order.status = OrderStatus.PAID
    else:
        receivable.finance_status = "partial_paid"

    db.add(payment)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="create_payment",
        target_type="payment",
        target_id=payment.id,
        after_data={"payment_no": payment.payment_no, "amount": float(payment.amount)},
    )
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/receipts/daily", response_model=PageResponse[ReceiptDailyEntryRead])
def list_daily_receipts(
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receivable:view")),
) -> PageResponse[ReceiptDailyEntryRead]:
    _assert_finance_module_role(current_user)
    query = db.query(ReceiptDailyEntry).options(selectinload(ReceiptDailyEntry.allocations)).filter(ReceiptDailyEntry.deleted_at.is_(None))
    if customer_id:
        query = query.filter(ReceiptDailyEntry.customer_id == customer_id)
    if status_filter:
        query = query.filter(ReceiptDailyEntry.status == status_filter)
    if date_from:
        query = query.filter(ReceiptDailyEntry.received_date >= date_from)
    if date_to:
        query = query.filter(ReceiptDailyEntry.received_date <= date_to)
    if cylinder_no:
        query = query.join(ReceiptAllocation).filter(ReceiptAllocation.cylinder_no == cylinder_no)
    total = query.distinct().count()
    items = query.order_by(ReceiptDailyEntry.received_date.desc(), ReceiptDailyEntry.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/receipts/daily/export")
def export_daily_receipts(
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    status_filter: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    _assert_finance_module_role(current_user)
    query = db.query(ReceiptDailyEntry).options(selectinload(ReceiptDailyEntry.allocations)).filter(ReceiptDailyEntry.deleted_at.is_(None))
    if customer_id:
        query = query.filter(ReceiptDailyEntry.customer_id == customer_id)
    if status_filter:
        query = query.filter(ReceiptDailyEntry.status == status_filter)
    if date_from:
        query = query.filter(ReceiptDailyEntry.received_date >= date_from)
    if date_to:
        query = query.filter(ReceiptDailyEntry.received_date <= date_to)
    if cylinder_no:
        query = query.join(ReceiptAllocation).filter(ReceiptAllocation.cylinder_no == cylinder_no)

    receipts = query.distinct().order_by(ReceiptDailyEntry.received_date.desc(), ReceiptDailyEntry.created_at.desc()).all()
    customer_names = _customer_name_map(db, {receipt.customer_id for receipt in receipts})
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="export_daily_receipts",
        target_type="receipt_daily_entry",
        after_data={"count": len(receipts)},
    )
    db.commit()
    return build_xlsx_response(
        "daily_receipts.xlsx",
        [
            "Receipt No.",
            "Customer",
            "Received Date",
            "Payment Method",
            "Cash Amount",
            "Bank Amount",
            "Other Amount",
            "Salesman",
            "VAT",
            "AIT",
            "Total Tax",
            "Total Amount",
            "Remark",
        ],
        [
            [
                receipt.receipt_no,
                customer_names.get(receipt.customer_id, str(receipt.customer_id)),
                receipt.received_date.isoformat(),
                receipt.payment_method,
                float(receipt.cash_amount),
                float(receipt.bank_amount),
                float(receipt.other_amount),
                receipt.salesman_name or "",
                0,
                0,
                0,
                float(receipt.total_amount),
                receipt.remark or "",
            ]
            for receipt in receipts
        ],
    )


@router.post("/receipts/daily", response_model=ReceiptDailyEntryRead, status_code=status.HTTP_201_CREATED)
def create_daily_receipt(
    payload: ReceiptDailyEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:payment:create")),
) -> ReceiptDailyEntry:
    customer = db.get(Customer, payload.customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    total_amount = _decimal(payload.cash_amount) + _decimal(payload.bank_amount) + _decimal(payload.other_amount)
    if total_amount <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Receipt amount must be greater than 0.")
    allocation_total = sum((_decimal(allocation.amount) for allocation in payload.allocations), Decimal("0"))
    if allocation_total != total_amount:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Allocation total must match receipt total.")

    allocations: list[ReceiptAllocation] = []
    for allocation in payload.allocations:
        cylinder_no = allocation.cylinder_no.strip()
        accounting_month = _month_start(allocation.accounting_month or payload.received_date)
        sales_order_id = allocation.sales_order_id
        if sales_order_id:
            order = db.get(SalesOrder, sales_order_id)
            if order is None or order.deleted_at is not None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation sales order not found.")
            if order.customer_id != payload.customer_id:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Allocation order does not belong to the selected customer.")
            if cylinder_no not in _order_cylinder_nos(order):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cylinder no does not belong to the selected order.")
        else:
            matches = _matching_orders_by_cylinder(
                db,
                cylinder_no=cylinder_no,
                accounting_month=accounting_month,
                customer_id=payload.customer_id,
            )
            if len(matches) == 1:
                sales_order_id = matches[0].id
            elif not matches:
                other_matches = _matching_orders_by_cylinder(db, cylinder_no=cylinder_no, accounting_month=accounting_month)
                if any(order.customer_id != payload.customer_id for order in other_matches):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cylinder no belongs to another customer in this accounting month.")

        allocations.append(
            ReceiptAllocation(
                customer_id=payload.customer_id,
                sales_order_id=sales_order_id,
                cylinder_no=cylinder_no,
                accounting_month=accounting_month,
                amount=allocation.amount,
                remark=allocation.remark,
            )
        )

    entry = ReceiptDailyEntry(
        receipt_no=generate_number("RCPT"),
        customer_id=payload.customer_id,
        received_date=payload.received_date,
        payment_method=payload.payment_method,
        cash_amount=payload.cash_amount,
        bank_amount=payload.bank_amount,
        other_amount=payload.other_amount,
        total_amount=total_amount,
        salesman_name=payload.salesman_name,
        payee_name=payload.payee_name,
        abstract=payload.abstract,
        status="received",
        remark=payload.remark,
        allocations=allocations,
    )
    db.add(entry)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="create_daily_receipt",
        target_type="receipt_daily_entry",
        target_id=entry.id,
        after_data={"receipt_no": entry.receipt_no, "total_amount": float(entry.total_amount)},
    )
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/receipts/daily/{receipt_id}/check", response_model=ReceiptDailyEntryRead)
def check_daily_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:payment:create")),
) -> ReceiptDailyEntry:
    receipt = db.query(ReceiptDailyEntry).options(selectinload(ReceiptDailyEntry.allocations)).filter(ReceiptDailyEntry.id == receipt_id).first()
    if receipt is None or receipt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")
    if receipt.status == "checked":
        return receipt
    receipt.status = "checked"
    receipt.checked_at = datetime.now(timezone.utc)
    receipt.checked_by = current_user.id
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="check_daily_receipt",
        target_type="receipt_daily_entry",
        target_id=receipt.id,
        after_data={"receipt_no": receipt.receipt_no, "status": receipt.status},
    )
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/receipts/daily/{receipt_id}/uncheck", response_model=ReceiptDailyEntryRead)
def uncheck_daily_receipt(
    receipt_id: UUID,
    reason: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:adjust")),
) -> ReceiptDailyEntry:
    receipt = db.query(ReceiptDailyEntry).options(selectinload(ReceiptDailyEntry.allocations)).filter(ReceiptDailyEntry.id == receipt_id).first()
    if receipt is None or receipt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")
    receipt.status = "received"
    receipt.checked_at = None
    receipt.checked_by = None
    receipt.remark = f"{receipt.remark or ''}\n反审核原因: {reason}".strip()
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="uncheck_daily_receipt",
        target_type="receipt_daily_entry",
        target_id=receipt.id,
        after_data={"receipt_no": receipt.receipt_no, "reason": reason},
    )
    db.commit()
    db.refresh(receipt)
    return receipt


@router.get("/receipts/daily/{receipt_id}/print", response_class=HTMLResponse)
def print_daily_receipt(
    receipt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receipt:print")),
) -> HTMLResponse:
    receipt = db.query(ReceiptDailyEntry).options(selectinload(ReceiptDailyEntry.allocations)).filter(ReceiptDailyEntry.id == receipt_id).first()
    if receipt is None or receipt.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")
    if receipt.status != "checked":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Receipt must be checked before printing.")
    customer = db.get(Customer, receipt.customer_id)
    html = _receipt_html_v2(receipt, customer)
    print_job = record_print_job(
        db,
        document_type="money_receipt",
        target_type="receipt_daily_entry",
        target_id=receipt.id,
        printed_by=current_user.id,
        snapshot=_receipt_snapshot(receipt, customer),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="print_daily_receipt",
        target_type="receipt_daily_entry",
        target_id=receipt.id,
        after_data={"receipt_no": receipt.receipt_no, "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)


@router.get("/monthly-receipts", response_model=PageResponse[MonthlyPaymentSummaryRead])
def list_monthly_receipts(
    accounting_month: date | None = None,
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receivable:view")),
) -> PageResponse[MonthlyPaymentSummaryRead]:
    _assert_finance_module_role(current_user)
    query = db.query(MonthlyPaymentSummary).filter(MonthlyPaymentSummary.deleted_at.is_(None))
    if accounting_month:
        query = query.filter(MonthlyPaymentSummary.accounting_month == _month_start(accounting_month))
    if customer_id:
        query = query.filter(MonthlyPaymentSummary.customer_id == customer_id)
    if cylinder_no:
        query = query.filter(MonthlyPaymentSummary.cylinder_no == cylinder_no)
    total = query.count()
    items = query.order_by(MonthlyPaymentSummary.accounting_month.desc(), MonthlyPaymentSummary.cylinder_no).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/monthly-receipts/export")
def export_monthly_receipts(
    accounting_month: date | None = None,
    customer_id: UUID | None = None,
    cylinder_no: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    _assert_finance_module_role(current_user)
    query = db.query(MonthlyPaymentSummary).filter(MonthlyPaymentSummary.deleted_at.is_(None))
    if accounting_month:
        query = query.filter(MonthlyPaymentSummary.accounting_month == _month_start(accounting_month))
    if customer_id:
        query = query.filter(MonthlyPaymentSummary.customer_id == customer_id)
    if cylinder_no:
        query = query.filter(MonthlyPaymentSummary.cylinder_no == cylinder_no)

    summaries = query.order_by(MonthlyPaymentSummary.accounting_month.desc(), MonthlyPaymentSummary.cylinder_no).all()
    customer_names = _customer_name_map(db, {summary.customer_id for summary in summaries})
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="export_monthly_receipts",
        target_type="monthly_payment_summary",
        after_data={"count": len(summaries)},
    )
    db.commit()
    return build_xlsx_response(
        "monthly_receipts.xlsx",
        [
            "Customer",
            "Cylinder No.",
            "Accounting Month",
            "Receivable Amount",
            "Received Amount",
            "Due Amount",
            "Status",
            "Calculated At",
            "Remark",
        ],
        [
            [
                customer_names.get(summary.customer_id, str(summary.customer_id)),
                summary.cylinder_no,
                summary.accounting_month.strftime("%Y-%m"),
                float(summary.receivable_amount),
                float(summary.received_amount),
                float(summary.due_amount),
                summary.status,
                summary.calculated_at.isoformat() if summary.calculated_at else "",
                summary.remark or "",
            ]
            for summary in summaries
        ],
    )


@router.post("/monthly-receipts/close", response_model=list[MonthlyPaymentSummaryRead])
def close_monthly_receipts(
    payload: MonthCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:month_close")),
) -> list[MonthlyPaymentSummary]:
    month = _month_start(payload.accounting_month)
    received_by_key: dict[tuple[UUID, str], Decimal] = {}
    allocation_query = (
        db.query(
            ReceiptAllocation.customer_id,
            ReceiptAllocation.cylinder_no,
            func.sum(ReceiptAllocation.amount).label("received_amount"),
        )
        .join(ReceiptDailyEntry, ReceiptDailyEntry.id == ReceiptAllocation.daily_entry_id)
        .filter(
            ReceiptDailyEntry.status == "checked",
            ReceiptDailyEntry.deleted_at.is_(None),
            ReceiptAllocation.accounting_month == month,
        )
        .group_by(ReceiptAllocation.customer_id, ReceiptAllocation.cylinder_no)
    )
    if payload.customer_id:
        allocation_query = allocation_query.filter(ReceiptAllocation.customer_id == payload.customer_id)

    for row in allocation_query.all():
        received_by_key[(row.customer_id, row.cylinder_no)] = _decimal(row.received_amount)

    summary_keys = set(received_by_key)
    order_query = db.query(SalesOrder).filter(
        SalesOrder.deleted_at.is_(None),
        SalesOrder.order_date >= month,
        SalesOrder.order_date < _next_month(month),
    )
    if payload.customer_id:
        order_query = order_query.filter(SalesOrder.customer_id == payload.customer_id)
    for order in order_query.all():
        for cylinder_no in _order_cylinder_nos(order):
            summary_keys.add((order.customer_id, cylinder_no))

    previous_query = db.query(MonthlyPaymentSummary).filter(
        MonthlyPaymentSummary.accounting_month < month,
        MonthlyPaymentSummary.deleted_at.is_(None),
    )
    if payload.customer_id:
        previous_query = previous_query.filter(MonthlyPaymentSummary.customer_id == payload.customer_id)
    for previous in previous_query.all():
        if _previous_due(db, previous.customer_id, previous.cylinder_no, month) != Decimal("0"):
            summary_keys.add((previous.customer_id, previous.cylinder_no))

    existing_query = db.query(MonthlyPaymentSummary).filter(
        MonthlyPaymentSummary.accounting_month == month,
        MonthlyPaymentSummary.deleted_at.is_(None),
    )
    if payload.customer_id:
        existing_query = existing_query.filter(MonthlyPaymentSummary.customer_id == payload.customer_id)
    for existing in existing_query.all():
        summary_keys.add((existing.customer_id, existing.cylinder_no))

    summaries: list[MonthlyPaymentSummary] = []
    for customer_id, cylinder_no in sorted(summary_keys, key=lambda item: (str(item[0]), item[1])):
        receivable_amount = _sum_order_receivable(db, customer_id, cylinder_no, month)
        received_amount = received_by_key.get((customer_id, cylinder_no), Decimal("0"))
        due_amount = _previous_due(db, customer_id, cylinder_no, month) + receivable_amount - received_amount
        summary = (
            db.query(MonthlyPaymentSummary)
            .filter(
                MonthlyPaymentSummary.customer_id == customer_id,
                MonthlyPaymentSummary.cylinder_no == cylinder_no,
                MonthlyPaymentSummary.accounting_month == month,
                MonthlyPaymentSummary.deleted_at.is_(None),
            )
            .first()
        )
        if summary is None:
            summary = MonthlyPaymentSummary(
                customer_id=customer_id,
                cylinder_no=cylinder_no,
                accounting_month=month,
            )
            db.add(summary)
        summary.receivable_amount = receivable_amount
        summary.received_amount = received_amount
        summary.due_amount = due_amount
        summary.status = "closed" if due_amount <= 0 else "open"
        summary.calculated_at = datetime.now(timezone.utc)
        summaries.append(summary)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="close_monthly_receipts",
        target_type="monthly_payment_summary",
        after_data={"month": month.isoformat(), "count": len(summaries)},
    )
    db.commit()
    for summary in summaries:
        db.refresh(summary)
    return summaries


@router.get("/customer-statements", response_model=PageResponse[CustomerStatementRead])
def list_customer_statements(
    customer_id: UUID | None = None,
    statement_month: date | None = None,
    status_filter: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receivable:view")),
) -> PageResponse[CustomerStatementRead]:
    _assert_finance_module_role(current_user)
    query = db.query(CustomerStatementRun).filter(CustomerStatementRun.deleted_at.is_(None))
    if customer_id:
        query = query.filter(CustomerStatementRun.customer_id == customer_id)
    if statement_month:
        query = query.filter(CustomerStatementRun.statement_month == _month_start(statement_month))
    if status_filter:
        query = query.filter(CustomerStatementRun.status == status_filter)
    total = query.count()
    items = query.order_by(CustomerStatementRun.statement_month.desc(), CustomerStatementRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/customer-statements/export")
def export_customer_statements(
    customer_id: UUID | None = None,
    statement_month: date | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    _assert_finance_module_role(current_user)
    query = db.query(CustomerStatementRun).filter(CustomerStatementRun.deleted_at.is_(None))
    if customer_id:
        query = query.filter(CustomerStatementRun.customer_id == customer_id)
    if statement_month:
        query = query.filter(CustomerStatementRun.statement_month == _month_start(statement_month))
    if status_filter:
        query = query.filter(CustomerStatementRun.status == status_filter)

    statements = query.order_by(CustomerStatementRun.statement_month.desc(), CustomerStatementRun.created_at.desc()).all()
    customer_names = _customer_name_map(db, {statement.customer_id for statement in statements})
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="export_customer_statements",
        target_type="customer_statement",
        after_data={"count": len(statements)},
    )
    db.commit()
    return build_xlsx_response(
        "customer_statements.xlsx",
        [
            "Statement No.",
            "Customer",
            "Statement Month",
            "Cylinder Nos",
            "Previous Balance",
            "Current Receivable",
            "Received Amount",
            "Due Amount",
            "Price Approval",
            "Price Approved At",
            "Price Approved By",
            "Status",
            "Printed At",
            "Remark",
        ],
        [
            [
                statement.statement_no,
                customer_names.get(statement.customer_id, str(statement.customer_id)),
                statement.statement_month.strftime("%Y-%m"),
                ", ".join(statement.selected_cylinder_nos),
                float(statement.previous_balance),
                float(statement.current_receivable),
                float(statement.received_amount),
                float(statement.due_amount),
                statement.price_approval_status,
                statement.price_approved_at.isoformat() if statement.price_approved_at else "",
                str(statement.price_approved_by) if statement.price_approved_by else "",
                statement.status,
                statement.printed_at.isoformat() if statement.printed_at else "",
                statement.remark or "",
            ]
            for statement in statements
        ],
    )


@router.post("/customer-statements", response_model=CustomerStatementRead, status_code=status.HTTP_201_CREATED)
def create_customer_statement(
    payload: CustomerStatementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:month_close")),
) -> CustomerStatementRun:
    customer = db.get(Customer, payload.customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    month = _month_start(payload.statement_month)
    selected = [item.strip() for item in payload.selected_cylinder_nos if item.strip()]
    if not selected:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one cylinder no is required.")
    previous_balance = sum((_previous_due(db, payload.customer_id, cylinder_no, month) for cylinder_no in selected), Decimal("0")) if payload.include_previous_balance else Decimal("0")
    current_receivable = sum((_sum_order_receivable(db, payload.customer_id, cylinder_no, month) for cylinder_no in selected), Decimal("0"))
    received_amount = (
        db.query(func.coalesce(func.sum(ReceiptAllocation.amount), 0))
        .join(ReceiptDailyEntry, ReceiptDailyEntry.id == ReceiptAllocation.daily_entry_id)
        .filter(
            ReceiptDailyEntry.status == "checked",
            ReceiptAllocation.customer_id == payload.customer_id,
            ReceiptAllocation.accounting_month == month,
            ReceiptAllocation.cylinder_no.in_(selected),
        )
        .scalar()
    )
    due_amount = previous_balance + current_receivable - _decimal(received_amount)
    statement = CustomerStatementRun(
        statement_no=generate_number("BILL"),
        customer_id=payload.customer_id,
        statement_month=month,
        selected_cylinder_nos=selected,
        previous_balance=previous_balance,
        current_receivable=current_receivable,
        received_amount=_decimal(received_amount),
        due_amount=due_amount,
        status="draft",
        price_approval_status="pending",
        remark=payload.remark,
    )
    db.add(statement)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="create_customer_statement",
        target_type="customer_statement",
        target_id=statement.id,
        after_data={"statement_no": statement.statement_no, "due_amount": float(statement.due_amount)},
    )
    db.commit()
    db.refresh(statement)
    return statement


@router.post("/customer-statements/{statement_id}/approve-price", response_model=CustomerStatementRead)
def approve_customer_statement_price(
    statement_id: UUID,
    remark: str | None = Query(default=None, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:bill_price:approve")),
) -> CustomerStatementRun:
    _assert_bill_price_approver_role(current_user)
    statement = db.get(CustomerStatementRun, statement_id)
    if statement is None or statement.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")
    statement.price_approval_status = "approved"
    statement.price_approved_at = datetime.now(timezone.utc)
    statement.price_approved_by = current_user.id
    statement.price_approval_remark = remark
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="approve_customer_statement_price",
        target_type="customer_statement",
        target_id=statement.id,
        after_data={"statement_no": statement.statement_no, "current_receivable": float(statement.current_receivable)},
    )
    db.commit()
    db.refresh(statement)
    return statement


@router.get("/customer-statements/{statement_id}/print", response_class=HTMLResponse)
def print_customer_statement(
    statement_id: UUID,
    with_header: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("finance:receipt:print")),
) -> HTMLResponse:
    statement = db.get(CustomerStatementRun, statement_id)
    if statement is None or statement.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found.")
    if statement.price_approval_status != "approved":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Bill price must be approved by boss/admin before printing.")
    statement.printed_at = datetime.now(timezone.utc)
    statement.status = "printed"
    customer = db.get(Customer, statement.customer_id)
    html = _statement_html_v2(statement, customer, db, with_header=with_header)
    print_job = record_print_job(
        db,
        document_type="customer_statement",
        target_type="customer_statement",
        target_id=statement.id,
        printed_by=current_user.id,
        snapshot=_statement_snapshot(statement, customer, with_header=with_header),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="finance",
        action="print_customer_statement",
        target_type="customer_statement",
        target_id=statement.id,
        after_data={"statement_no": statement.statement_no, "print_no": print_job.print_no, "with_header": with_header},
    )
    db.commit()
    return HTMLResponse(html)
