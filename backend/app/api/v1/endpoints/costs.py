import re
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.finance import CostRecord
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.common import PageResponse
from app.schemas.cost import (
    CostRecordCreate,
    CostRecordRead,
    CustomerMonthlySalesReport,
    CustomerMonthlySalesRow,
    ProfitReportResponse,
    ProfitReportRow,
    ProfitReportSummary,
    SalesMonthlySummary,
    SalespersonMonthlyReport,
    SalespersonMonthlyRow,
)
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response

router = APIRouter()


@router.get("/cost-records", response_model=PageResponse[CostRecordRead])
def list_cost_records(
    sales_order_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("cost:view")),
) -> PageResponse[CostRecordRead]:
    query = db.query(CostRecord).filter(CostRecord.deleted_at.is_(None))
    if sales_order_id:
        query = query.filter(CostRecord.sales_order_id == sales_order_id)
    total = query.count()
    items = query.order_by(CostRecord.cost_date.desc(), CostRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/cost-records", response_model=CostRecordRead, status_code=status.HTTP_201_CREATED)
def create_cost_record(
    payload: CostRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cost:create")),
) -> CostRecord:
    order = db.get(SalesOrder, payload.sales_order_id)
    if order is None or order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")

    cost_record = CostRecord(
        sales_order_id=payload.sales_order_id,
        work_order_id=payload.work_order_id,
        work_order_step_id=payload.work_order_step_id,
        cost_type=payload.cost_type,
        amount=Decimal(str(payload.amount)),
        cost_date=payload.cost_date,
        remark=payload.remark,
    )
    db.add(cost_record)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="cost",
        action="create",
        target_type="cost_record",
        target_id=cost_record.id,
        after_data={"cost_type": cost_record.cost_type, "amount": float(cost_record.amount)},
    )
    db.commit()
    db.refresh(cost_record)
    return cost_record


def _profit_rows(db: Session) -> list[ProfitReportRow]:
    rows: list[ProfitReportRow] = []
    orders = (
        db.query(SalesOrder, Customer)
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .filter(SalesOrder.deleted_at.is_(None))
        .order_by(SalesOrder.order_date.desc(), SalesOrder.created_at.desc())
        .all()
    )
    for order, customer in orders:
        total_cost = (
            db.query(CostRecord)
            .filter(CostRecord.sales_order_id == order.id, CostRecord.deleted_at.is_(None))
            .with_entities(CostRecord.amount)
            .all()
        )
        cost_sum = sum(Decimal(str(item.amount)) for item in total_cost)
        revenue = Decimal(str(order.total_amount))
        gross_profit = revenue - cost_sum
        gross_margin = float(gross_profit / revenue * Decimal("100")) if revenue else 0.0
        rows.append(
            ProfitReportRow(
                sales_order_id=order.id,
                order_no=order.order_no,
                customer_name=customer.name,
                product_summary=order.product_summary,
                order_date=order.order_date,
                due_date=order.due_date,
                revenue=float(revenue),
                total_cost=float(cost_sum),
                gross_profit=float(gross_profit),
                gross_margin=round(gross_margin, 2),
            )
        )
    return rows


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _number(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return Decimal(match.group(0)) if match else Decimal("0")


def _order_type(order: SalesOrder) -> str:
    return str((order.plate_details or {}).get("order_type") or "new_cylinder")


def _salesperson(order: SalesOrder, customer: Customer) -> str:
    details = order.plate_details or {}
    return str(details.get("salesman") or customer.salesperson_name or "未指定")


def _order_pcs(order: SalesOrder) -> tuple[Decimal, Decimal]:
    details = order.plate_details or {}
    explicit_new = _number(details.get("new_qty"))
    explicit_old = _number(details.get("old_qty"))
    if explicit_new or explicit_old:
        return explicit_new, explicit_old

    detail_qty = _number(details.get("total_qty"))
    item_qty = sum(_number(item.quantity) for item in order.items)
    qty = detail_qty or item_qty
    if _order_type(order) in {"old_cylinder", "dechrome", "rework"}:
        return Decimal("0"), qty
    return qty, Decimal("0")


def _settlement_type(customer: Customer) -> str:
    if customer.reconciliation_cycle:
        return customer.reconciliation_cycle
    days = customer.payment_terms_days or 0
    return "Cash" if days <= 0 else f"{days}days"


def _sales_orders_for_period(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    rework_mode: str,
    customer_id: UUID | None = None,
    salesperson: str | None = None,
) -> list[tuple[SalesOrder, Customer]]:
    query = (
        db.query(SalesOrder, Customer)
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.deleted_at.is_(None))
    )
    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)
    if date_from:
        query = query.filter(SalesOrder.order_date >= date_from)
    if date_to:
        query = query.filter(SalesOrder.order_date <= date_to)

    rows = query.order_by(SalesOrder.order_date, SalesOrder.created_at).all()
    if salesperson:
        rows = [(order, customer) for order, customer in rows if _salesperson(order, customer) == salesperson]
    if rework_mode == "only_rework":
        return [(order, customer) for order, customer in rows if _order_type(order) == "rework" or order.rework_source_order_id]
    if rework_mode == "exclude_rework":
        return [(order, customer) for order, customer in rows if _order_type(order) != "rework" and not order.rework_source_order_id]
    return rows


def _salesperson_monthly_rows(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    rework_mode: str,
    customer_id: UUID | None = None,
    salesperson: str | None = None,
) -> list[SalespersonMonthlyRow]:
    buckets: dict[str, dict[str, Decimal]] = {}
    for order, customer in _sales_orders_for_period(db, date_from, date_to, rework_mode, customer_id, salesperson):
        name = _salesperson(order, customer)
        new_pcs, old_pcs = _order_pcs(order)
        bucket = buckets.setdefault(name, {"new_pcs": Decimal("0"), "old_pcs": Decimal("0"), "total_amount": Decimal("0")})
        bucket["new_pcs"] += new_pcs
        bucket["old_pcs"] += old_pcs
        bucket["total_amount"] += _decimal(order.total_amount)

    return [
        SalespersonMonthlyRow(
            salesperson=name,
            new_pcs=float(values["new_pcs"]),
            old_pcs=float(values["old_pcs"]),
            total_amount=float(values["total_amount"]),
        )
        for name, values in sorted(buckets.items(), key=lambda item: item[1]["total_amount"], reverse=True)
    ]


def _customer_monthly_sales_rows(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    rework_mode: str,
    customer_id: UUID | None = None,
    salesperson: str | None = None,
) -> list[CustomerMonthlySalesRow]:
    buckets: dict[UUID, dict[str, object]] = {}
    for order, customer in _sales_orders_for_period(db, date_from, date_to, rework_mode, customer_id, salesperson):
        new_pcs, old_pcs = _order_pcs(order)
        amount = _decimal(order.total_amount)
        bucket = buckets.setdefault(
            customer.id,
            {
                "salesperson": _salesperson(order, customer),
                "customer_name": customer.name,
                "new_pcs": Decimal("0"),
                "old_pcs": Decimal("0"),
                "total_amount": Decimal("0"),
                "settlement_type": _settlement_type(customer),
            },
        )
        bucket["new_pcs"] = bucket["new_pcs"] + new_pcs
        bucket["old_pcs"] = bucket["old_pcs"] + old_pcs
        bucket["total_amount"] = bucket["total_amount"] + amount

    rows: list[CustomerMonthlySalesRow] = []
    for customer_id, values in buckets.items():
        pcs = values["new_pcs"] + values["old_pcs"]
        price = values["total_amount"] / pcs if pcs else Decimal("0")
        rows.append(
            CustomerMonthlySalesRow(
                salesperson=str(values["salesperson"]),
                customer_id=customer_id,
                customer_name=str(values["customer_name"]),
                new_pcs=float(values["new_pcs"]),
                old_pcs=float(values["old_pcs"]),
                total_amount=float(values["total_amount"]),
                price=round(float(price), 2),
                settlement_type=str(values["settlement_type"]),
            )
        )
    return sorted(rows, key=lambda row: (row.salesperson, row.customer_name))


def _sales_summary(rows: list[SalespersonMonthlyRow] | list[CustomerMonthlySalesRow]) -> SalesMonthlySummary:
    return SalesMonthlySummary(
        new_pcs=float(sum(Decimal(str(row.new_pcs)) for row in rows)),
        old_pcs=float(sum(Decimal(str(row.old_pcs)) for row in rows)),
        total_amount=float(sum(Decimal(str(row.total_amount)) for row in rows)),
    )


@router.get("/reports/salesperson-monthly", response_model=SalespersonMonthlyReport)
def salesperson_monthly_report(
    date_from: date | None = None,
    date_to: date | None = None,
    rework_mode: str = Query(default="all", pattern="^(all|exclude_rework|only_rework)$"),
    customer_id: UUID | None = None,
    salesperson: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("report:view")),
) -> SalespersonMonthlyReport:
    rows = _salesperson_monthly_rows(db, date_from, date_to, rework_mode, customer_id, salesperson)
    return SalespersonMonthlyReport(rows=rows, summary=_sales_summary(rows))


@router.get("/reports/salesperson-monthly/export")
def export_salesperson_monthly_report(
    date_from: date | None = None,
    date_to: date | None = None,
    rework_mode: str = Query(default="all", pattern="^(all|exclude_rework|only_rework)$"),
    customer_id: UUID | None = None,
    salesperson: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    rows = _salesperson_monthly_rows(db, date_from, date_to, rework_mode, customer_id, salesperson)
    log_operation(
        db,
        user_id=current_user.id,
        module="report",
        action="export_salesperson_monthly",
        target_type="salesperson_monthly_report",
        after_data={
            "count": len(rows),
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "customer_id": str(customer_id) if customer_id else None,
            "salesperson": salesperson,
        },
    )
    db.commit()
    return build_xlsx_response(
        "salesperson-monthly.xlsx",
        ["业务员", "新支数", "旧支数", "销售额"],
        [[row.salesperson, row.new_pcs, row.old_pcs, row.total_amount] for row in rows],
    )


@router.get("/reports/customer-monthly-sales", response_model=CustomerMonthlySalesReport)
def customer_monthly_sales_report(
    date_from: date | None = None,
    date_to: date | None = None,
    rework_mode: str = Query(default="all", pattern="^(all|exclude_rework|only_rework)$"),
    customer_id: UUID | None = None,
    salesperson: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("report:view")),
) -> CustomerMonthlySalesReport:
    rows = _customer_monthly_sales_rows(db, date_from, date_to, rework_mode, customer_id, salesperson)
    return CustomerMonthlySalesReport(rows=rows, summary=_sales_summary(rows))


@router.get("/reports/customer-monthly-sales/export")
def export_customer_monthly_sales_report(
    date_from: date | None = None,
    date_to: date | None = None,
    rework_mode: str = Query(default="all", pattern="^(all|exclude_rework|only_rework)$"),
    customer_id: UUID | None = None,
    salesperson: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    rows = _customer_monthly_sales_rows(db, date_from, date_to, rework_mode, customer_id, salesperson)
    log_operation(
        db,
        user_id=current_user.id,
        module="report",
        action="export_customer_monthly_sales",
        target_type="customer_monthly_sales_report",
        after_data={
            "count": len(rows),
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "customer_id": str(customer_id) if customer_id else None,
            "salesperson": salesperson,
        },
    )
    db.commit()
    return build_xlsx_response(
        "customer-monthly-sales.xlsx",
        ["业务员", "客户名称", "新支数", "旧支数", "销售额", "平均单价", "结算方式"],
        [
            [
                row.salesperson,
                row.customer_name,
                row.new_pcs,
                row.old_pcs,
                row.total_amount,
                row.price,
                row.settlement_type,
            ]
            for row in rows
        ],
    )


@router.get("/reports/profit", response_model=ProfitReportResponse)
def profit_report(
    db: Session = Depends(get_db),
    _=Depends(require_permission("report:view")),
) -> ProfitReportResponse:
    rows = _profit_rows(db)
    revenue = sum(Decimal(str(row.revenue)) for row in rows)
    total_cost = sum(Decimal(str(row.total_cost)) for row in rows)
    gross_profit = revenue - total_cost
    gross_margin = float(gross_profit / revenue * Decimal("100")) if revenue else 0.0
    return ProfitReportResponse(
        rows=rows,
        summary=ProfitReportSummary(
            revenue=float(revenue),
            total_cost=float(total_cost),
            gross_profit=float(gross_profit),
            gross_margin=round(gross_margin, 2),
        ),
    )


@router.get("/reports/profit/export")
def export_profit_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    rows = _profit_rows(db)
    log_operation(
        db,
        user_id=current_user.id,
        module="report",
        action="export_profit",
        target_type="profit_report",
        after_data={"count": len(rows)},
    )
    db.commit()
    return build_xlsx_response(
        "profit-report.xlsx",
        ["订单编号", "客户", "产品", "下单日期", "交期", "订单金额", "总成本", "毛利", "毛利率%"],
        [
            [
                row.order_no,
                row.customer_name,
                row.product_summary,
                row.order_date.isoformat(),
                row.due_date.isoformat(),
                row.revenue,
                row.total_cost,
                row.gross_profit,
                row.gross_margin,
            ]
            for row in rows
        ],
    )
