from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services.state_machine import OrderStatus, WorkOrderStatus

router = APIRouter()


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
