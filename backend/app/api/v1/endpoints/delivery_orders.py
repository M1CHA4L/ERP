from datetime import datetime, timezone
from html import escape
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.logistics import DeliveryOrder, DeliveryOrderItem
from app.models.production import WorkOrder
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.common import PageResponse
from app.schemas.delivery import (
    DeliverableOrder,
    DeliveryOrderCreate,
    DeliveryOrderRead,
    ShipDeliveryRequest,
    SignDeliveryRequest,
)
from app.services.audit import log_operation
from app.services.numbering import generate_number
from app.services.printing import record_print_job
from app.services.state_machine import OrderStatus, WorkOrderStatus

router = APIRouter()

DeliveryPrintVariant = Literal["priced", "no_unit_price", "no_amount"]


def _load_delivery(db: Session, delivery_id: UUID) -> DeliveryOrder:
    delivery = db.query(DeliveryOrder).options(selectinload(DeliveryOrder.items)).filter(DeliveryOrder.id == delivery_id).first()
    if delivery is None or delivery.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery order not found.")
    return delivery


def _assert_order_deliverable(db: Session, order: SalesOrder) -> None:
    work_orders = db.query(WorkOrder).filter(WorkOrder.sales_order_id == order.id, WorkOrder.deleted_at.is_(None)).all()
    if not work_orders:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Order has no work orders.")
    if not all(work_order.status == WorkOrderStatus.COMPLETED for work_order in work_orders):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="All work orders must be completed before delivery.")


def _role_codes(user: User) -> set[str]:
    return {role.code for role in user.roles}


def _can_view_delivery_amount(user: User) -> bool:
    if _role_codes(user) & {"admin", "boss", "finance"}:
        return True
    return bool({"finance:receivable:view", "cost:view"} & set(user.permission_codes))


def _h(value: object) -> str:
    return escape("" if value is None else str(value))


def _money(value: object) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def _quantity(value: object) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "-"


def _variant_label(variant: DeliveryPrintVariant) -> str:
    labels = {
        "priced": "Delivery Note (Priced)",
        "no_unit_price": "Delivery Note (No Unit Price)",
        "no_amount": "Delivery Note (No Amount)",
    }
    return labels[variant]


def _delivery_print_html(
    *,
    delivery: DeliveryOrder,
    order: SalesOrder | None,
    customer: Customer | None,
    variant: DeliveryPrintVariant,
) -> str:
    source_items = {item.id: item for item in order.items} if order else {}
    show_unit_price = variant == "priced"
    show_amount = variant in {"priced", "no_unit_price"}
    amount_colspan = (1 if show_unit_price else 0) + (1 if show_amount else 0)
    column_count = 5 + amount_colspan
    total_amount = 0.0
    rows: list[str] = []

    for index, item in enumerate(delivery.items, start=1):
        source = source_items.get(item.sales_order_item_id)
        unit_price = float(source.unit_price) if source and source.unit_price is not None else 0.0
        amount = float(source.amount) if source and source.amount is not None else unit_price * float(item.quantity)
        if show_amount:
            total_amount += amount
        money_cells = ""
        if show_unit_price:
            money_cells += f"<td>{_money(unit_price)}</td>"
        if show_amount:
            money_cells += f"<td>{_money(amount)}</td>"
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td class='left'>{_h(item.product_name)}</td>"
            f"<td class='left'>{_h(item.specification or '')}</td>"
            f"<td>{_quantity(item.quantity)}</td>"
            f"<td>{_h(item.unit)}</td>"
            f"{money_cells}"
            "</tr>"
        )

    total_row = ""
    if show_amount:
        total_row = (
            "<tr>"
            f"<th colspan='{column_count - 1}' class='right'>Total Amount</th>"
            f"<th>{_money(total_amount)}</th>"
            "</tr>"
        )

    price_headers = ""
    if show_unit_price:
        price_headers += "<th>Unit Price</th>"
    if show_amount:
        price_headers += "<th>Amount</th>"

    title = _variant_label(variant)
    delivery_date = delivery.delivery_time.strftime("%Y-%m-%d %H:%M") if delivery.delivery_time else ""
    signed_at = delivery.signed_at.strftime("%Y-%m-%d %H:%M") if delivery.signed_at else ""
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{_h(title)} - {_h(delivery.delivery_no)}</title>
  <style>
    @page {{ size: A4 portrait; margin: 12mm; }}
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; color: #111827; margin: 0; }}
    .sheet {{ width: 760px; margin: 16px auto; }}
    h1 {{ text-align: center; font-size: 24px; letter-spacing: 0; margin: 0 0 12px; }}
    .meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; font-size: 13px; margin-bottom: 12px; }}
    .meta div {{ border-bottom: 1px solid #9ca3af; padding: 3px 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #111827; padding: 7px 6px; font-size: 12px; text-align: center; }}
    th {{ background: #f3f4f6; }}
    .left {{ text-align: left; }}
    .right {{ text-align: right; }}
    .remark {{ min-height: 46px; margin-top: 10px; border: 1px solid #111827; padding: 8px; font-size: 13px; }}
    .signatures {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 18px; margin-top: 28px; font-size: 13px; }}
    .line {{ border-bottom: 1px solid #111827; height: 24px; }}
    .actions {{ text-align: right; margin: 12px auto; width: 760px; }}
    button {{ border: 1px solid #111827; background: #fff; padding: 6px 12px; cursor: pointer; }}
    @media print {{ .actions {{ display: none; }} .sheet {{ margin: 0 auto; }} }}
  </style>
</head>
<body>
  <div class="actions"><button type="button" onclick="window.print()">Print / PDF</button></div>
  <section class="sheet">
    <h1>{_h(title)}</h1>
    <div class="meta">
      <div>Delivery No.: {_h(delivery.delivery_no)}</div>
      <div>Order No.: {_h(order.order_no if order else '')}</div>
      <div>Customer: {_h(customer.name if customer else '')}</div>
      <div>Delivery Time: {_h(delivery_date)}</div>
      <div>Driver / Logistics: {_h(delivery.driver_name or '')}</div>
      <div>Logistics No.: {_h(delivery.logistics_no or '')}</div>
      <div style="grid-column: 1 / -1;">Delivery Address: {_h(delivery.address)}</div>
    </div>
    <table>
      <thead>
        <tr><th style="width: 42px;">No.</th><th>Item / Artwork</th><th>Specification</th><th style="width: 70px;">Qty</th><th style="width: 64px;">Unit</th>{price_headers}</tr>
      </thead>
      <tbody>{''.join(rows) or f"<tr><td colspan='{column_count}'>No delivery items</td></tr>"}</tbody>
      <tfoot>{total_row}</tfoot>
    </table>
    <div class="remark">Remarks: {_h(delivery.remark or '')}</div>
    <div class="signatures">
      <div>Prepared By<div class="line"></div></div>
      <div>Delivered By<div class="line">{_h(delivery.driver_name or '')}</div></div>
      <div>Customer Signature<div class="line">{_h(delivery.signed_by or '')}</div></div>
    </div>
    <div class="meta" style="margin-top: 16px;">
      <div>Signed At: {_h(signed_at)}</div>
      <div>Printed At: {_h(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'))}</div>
    </div>
  </section>
</body>
</html>
"""
    return html


def _delivery_print_snapshot(
    *,
    delivery: DeliveryOrder,
    order: SalesOrder | None,
    customer: Customer | None,
    variant: DeliveryPrintVariant,
    can_view_amount: bool,
) -> dict:
    return {
        "delivery_no": delivery.delivery_no,
        "order_no": order.order_no if order else None,
        "customer_name": customer.name if customer else None,
        "variant": variant,
        "item_count": len(delivery.items),
        "total_amount": float(order.total_amount) if order and can_view_amount else None,
    }


@router.get("/deliverable", response_model=list[DeliverableOrder])
def list_deliverable_orders(
    db: Session = Depends(get_db),
    _=Depends(require_permission("delivery:view")),
) -> list[DeliverableOrder]:
    orders = (
        db.query(SalesOrder, Customer)
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .filter(SalesOrder.deleted_at.is_(None), SalesOrder.status.in_(["pending_delivery", "inspection_passed"]))
        .order_by(SalesOrder.created_at.desc())
        .all()
    )
    result: list[DeliverableOrder] = []
    for order, customer in orders:
        work_orders = db.query(WorkOrder).filter(WorkOrder.sales_order_id == order.id, WorkOrder.deleted_at.is_(None)).all()
        if work_orders and all(work_order.status == WorkOrderStatus.COMPLETED for work_order in work_orders):
            result.append(
                DeliverableOrder(
                    sales_order_id=order.id,
                    order_no=order.order_no,
                    customer_id=customer.id,
                    customer_name=customer.name,
                    address=customer.address,
                    product_summary=order.product_summary,
                    total_amount=order.total_amount,
                    status=order.status,
                )
            )
    return result


@router.get("", response_model=PageResponse[DeliveryOrderRead])
def list_delivery_orders(
    status_filter: str | None = None,
    sales_order_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("delivery:view")),
) -> PageResponse[DeliveryOrderRead]:
    query = db.query(DeliveryOrder).options(selectinload(DeliveryOrder.items)).filter(DeliveryOrder.deleted_at.is_(None))
    if status_filter:
        query = query.filter(DeliveryOrder.status == status_filter)
    if sales_order_id:
        query = query.filter(DeliveryOrder.sales_order_id == sales_order_id)
    total = query.count()
    items = query.order_by(DeliveryOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=DeliveryOrderRead, status_code=status.HTTP_201_CREATED)
def create_delivery_order(
    payload: DeliveryOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delivery:create")),
) -> DeliveryOrder:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == payload.sales_order_id).first()
    if order is None or order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _assert_order_deliverable(db, order)

    existing = (
        db.query(DeliveryOrder)
        .filter(DeliveryOrder.sales_order_id == order.id, DeliveryOrder.deleted_at.is_(None), DeliveryOrder.status != "cancelled")
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery order already exists for this order.")

    customer = db.get(Customer, order.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    delivery = DeliveryOrder(
        delivery_no=generate_number("DO"),
        sales_order_id=order.id,
        customer_id=order.customer_id,
        address=payload.address or customer.address or "",
        delivery_time=payload.delivery_time or datetime.now(timezone.utc),
        driver_name=payload.driver_name,
        logistics_no=payload.logistics_no,
        status="draft",
        remark=payload.remark,
        items=[
            DeliveryOrderItem(
                sales_order_item_id=item.id,
                product_name=item.product_name,
                specification=item.specification,
                quantity=item.quantity,
                unit=item.unit,
            )
            for item in order.items
        ],
    )
    db.add(delivery)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="delivery",
        action="create",
        target_type="delivery_order",
        target_id=delivery.id,
        after_data={"delivery_no": delivery.delivery_no, "sales_order_id": str(delivery.sales_order_id)},
    )
    db.commit()
    db.refresh(delivery)
    return delivery


@router.get("/{delivery_id}", response_model=DeliveryOrderRead)
def get_delivery_order(
    delivery_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("delivery:view")),
) -> DeliveryOrder:
    return _load_delivery(db, delivery_id)


@router.get("/{delivery_id}/print", response_class=HTMLResponse)
def print_delivery_order(
    delivery_id: UUID,
    variant: DeliveryPrintVariant = Query(default="no_unit_price"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delivery:view")),
) -> HTMLResponse:
    delivery = _load_delivery(db, delivery_id)
    can_view_amount = _can_view_delivery_amount(current_user)
    if variant != "no_amount" and not can_view_amount:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied for amount delivery note.")

    order = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.id == delivery.sales_order_id, SalesOrder.deleted_at.is_(None))
        .first()
    )
    customer = db.get(Customer, delivery.customer_id)
    html = _delivery_print_html(delivery=delivery, order=order, customer=customer, variant=variant)
    print_job = record_print_job(
        db,
        document_type=f"delivery_note_{variant}",
        target_type="delivery_order",
        target_id=delivery.id,
        printed_by=current_user.id,
        snapshot=_delivery_print_snapshot(
            delivery=delivery,
            order=order,
            customer=customer,
            variant=variant,
            can_view_amount=can_view_amount,
        ),
        html_snapshot=html,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="delivery",
        action="print_delivery_order",
        target_type="delivery_order",
        target_id=delivery.id,
        after_data={"delivery_no": delivery.delivery_no, "variant": variant, "print_no": print_job.print_no},
    )
    db.commit()
    return HTMLResponse(html)


@router.post("/{delivery_id}/ship", response_model=DeliveryOrderRead)
def ship_delivery_order(
    delivery_id: UUID,
    payload: ShipDeliveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delivery:create")),
) -> DeliveryOrder:
    delivery = _load_delivery(db, delivery_id)
    if delivery.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft delivery orders can be shipped.")
    if payload.logistics_no:
        delivery.logistics_no = payload.logistics_no
    if payload.driver_name:
        delivery.driver_name = payload.driver_name
    delivery.status = "shipped"
    log_operation(
        db,
        user_id=current_user.id,
        module="delivery",
        action="ship",
        target_type="delivery_order",
        target_id=delivery.id,
        after_data={"delivery_no": delivery.delivery_no, "status": delivery.status},
    )
    db.commit()
    db.refresh(delivery)
    return delivery


@router.post("/{delivery_id}/sign", response_model=DeliveryOrderRead)
def sign_delivery_order(
    delivery_id: UUID,
    payload: SignDeliveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("delivery:create")),
) -> DeliveryOrder:
    delivery = _load_delivery(db, delivery_id)
    if delivery.status not in {"draft", "shipped"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery order cannot be signed in current status.")
    delivery.status = "signed"
    delivery.signed_by = payload.signed_by
    delivery.signed_at = payload.signed_at or datetime.now(timezone.utc)
    order = db.get(SalesOrder, delivery.sales_order_id)
    if order:
        order.status = OrderStatus.DELIVERED
    log_operation(
        db,
        user_id=current_user.id,
        module="delivery",
        action="sign",
        target_type="delivery_order",
        target_id=delivery.id,
        after_data={"delivery_no": delivery.delivery_no, "signed_by": delivery.signed_by, "status": delivery.status},
    )
    db.commit()
    db.refresh(delivery)
    return delivery
