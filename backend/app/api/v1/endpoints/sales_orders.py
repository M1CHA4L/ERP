from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.process import ProcessRoute
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.production import WorkOrder
from app.models.rbac import User
from app.schemas.common import PageResponse
from app.schemas.production import GenerateWorkOrdersRequest, WorkOrderRead
from app.schemas.sales import (
    ConfirmOrderRequest,
    EngravingRecordRead,
    EngravingRecordUpdate,
    EntrustLayoutUpdate,
    EntrustSheetRead,
    SalesOrderCreate,
    SalesOrderRead,
)
from app.schemas.timeline import TimelineItem
from app.services.numbering import generate_number
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.state_machine import OrderStatus, can_confirm_order
from app.services.timeline import build_sales_order_timeline
from app.services.work_order_factory import create_work_orders_from_sales_order

router = APIRouter()

HISTORICAL_ORDER_STATUSES = {OrderStatus.PAID, OrderStatus.ARCHIVED, OrderStatus.CANCELLED}


def _ensure_active_route(db: Session, route_id: UUID) -> None:
    route = db.get(ProcessRoute, route_id)
    if route is None or route.status != "active":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="工艺路线不存在或未启用。")


def _can_view_history(user: User) -> bool:
    return "order:history:view" in user.permission_codes


def _can_view_plate_details(user: User) -> bool:
    return "order:plate_detail:view" in user.permission_codes


def _hide_restricted_orders(query, user: User, status_filter: str | None = None, include_history: bool = False):
    history_requested = include_history or status_filter in HISTORICAL_ORDER_STATUSES
    if _can_view_history(user) and history_requested:
        return query
    return query.filter(~SalesOrder.status.in_(HISTORICAL_ORDER_STATUSES))


def _ensure_order_visible(order: SalesOrder, user: User) -> None:
    if order.status in HISTORICAL_ORDER_STATUSES and not _can_view_history(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")


def _serialize_sales_order(order: SalesOrder, user: User) -> SalesOrderRead:
    data = SalesOrderRead.model_validate(order)
    if not _can_view_plate_details(user):
        data.remark = None
        data.plate_details = None
        data.color_rows = []
        for item in data.items:
            item.specification = None
    return data


def _order_type(order: SalesOrder) -> str:
    return str((order.plate_details or {}).get("order_type") or "new_cylinder")


def _filter_order_type(orders: list[SalesOrder], order_type: str | None) -> list[SalesOrder]:
    if not order_type:
        return orders
    return [order for order in orders if _order_type(order) == order_type]


@router.get("", response_model=PageResponse[SalesOrderRead])
def list_sales_orders(
    status_filter: str | None = None,
    customer_id: UUID | None = None,
    order_type: str | None = None,
    include_history: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> PageResponse[SalesOrderRead]:
    query = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.deleted_at.is_(None))
    query = _hide_restricted_orders(query, current_user, status_filter, include_history)
    if status_filter:
        query = query.filter(SalesOrder.status == status_filter)
    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)
    ordered = query.order_by(SalesOrder.created_at.desc()).all()
    filtered = _filter_order_type(ordered, order_type)
    total = len(filtered)
    items = filtered[(page - 1) * page_size : page * page_size]
    return PageResponse(
        items=[_serialize_sales_order(order, current_user) for order in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SalesOrderRead, status_code=status.HTTP_201_CREATED)
def create_sales_order(
    payload: SalesOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:create")),
) -> SalesOrder:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one item is required.")
    if payload.route_id:
        _ensure_active_route(db, payload.route_id)

    items: list[SalesOrderItem] = []
    total_amount = 0.0
    product_names: list[str] = []
    for item in payload.items:
        if item.route_id:
            _ensure_active_route(db, item.route_id)
        amount = item.quantity * item.unit_price
        total_amount += amount
        product_names.append(item.product_name)
        items.append(
            SalesOrderItem(
                product_id=item.product_id,
                product_name=item.product_name,
                specification=item.specification,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                amount=amount,
                route_id=item.route_id,
                remark=item.remark,
            )
        )

    plate_details = payload.plate_details.model_dump(exclude_none=True) if payload.plate_details else {}
    plate_details.setdefault("order_type", "new_cylinder")

    order = SalesOrder(
        order_no=generate_number("SO"),
        customer_id=payload.customer_id,
        product_summary=" / ".join(product_names[:3]),
        order_date=date.today(),
        due_date=payload.due_date,
        total_amount=total_amount,
        status=OrderStatus.DRAFT,
        priority=payload.priority,
        route_id=payload.route_id,
        plate_details=plate_details,
        color_rows=[row.model_dump(exclude_none=True) for row in (payload.color_rows or [])],
        remark=payload.remark,
        items=items,
    )
    db.add(order)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="create",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "total_amount": float(order.total_amount)},
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/export")
def export_sales_orders(
    status_filter: str | None = None,
    order_type: str | None = None,
    include_history: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    query = db.query(SalesOrder).filter(SalesOrder.deleted_at.is_(None))
    query = _hide_restricted_orders(query, current_user, status_filter, include_history)
    if status_filter:
        query = query.filter(SalesOrder.status == status_filter)
    orders = _filter_order_type(query.order_by(SalesOrder.created_at.desc()).all(), order_type)
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="export",
        target_type="sales_order",
        after_data={"count": len(orders)},
    )
    db.commit()
    return build_xlsx_response(
        "sales-orders.xlsx",
        ["订单编号", "订单类型", "产品", "下单日期", "交期", "金额", "优先级", "状态"],
        [
            [
                order.order_no,
                _order_type(order),
                order.product_summary,
                order.order_date.isoformat(),
                order.due_date.isoformat(),
                float(order.total_amount),
                order.priority,
                order.status,
            ]
            for order in orders
        ],
    )


@router.get("/{order_id}", response_model=SalesOrderRead)
def get_sales_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> SalesOrderRead:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    return _serialize_sales_order(order, current_user)


@router.get("/{order_id}/engraving", response_model=EngravingRecordRead)
def get_engraving_record(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> EngravingRecordRead:
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    record = (order.plate_details or {}).get("engraving_record") or {}
    return EngravingRecordRead(**record)


@router.put("/{order_id}/engraving", response_model=EngravingRecordRead)
def update_engraving_record(
    order_id: UUID,
    payload: EngravingRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("step:report")),
) -> EngravingRecordRead:
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    details = dict(order.plate_details or {})
    record = payload.model_dump(exclude_none=True)
    record["updated_at"] = date.today()
    details["engraving_record"] = record
    if payload.cylinder_no:
        details["cylinder_id"] = payload.cylinder_no
    if payload.product_name:
        details["product_name"] = payload.product_name
        order.product_summary = payload.product_name
    if payload.printing_method:
        details["printing_method"] = payload.printing_method
    order.plate_details = details
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="update_engraving_record",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "row_count": len(payload.rows)},
    )
    db.commit()
    return EngravingRecordRead(**record)


@router.get("/{order_id}/entrust", response_model=EntrustSheetRead)
def get_sales_order_entrust_sheet(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> EntrustSheetRead:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    customer = db.get(Customer, order.customer_id)
    order_read = _serialize_sales_order(order, current_user)
    plate_details = order_read.plate_details.model_dump() if order_read.plate_details else {}
    entrust_no = str(plate_details.get("sample_no") or order.order_no)
    return EntrustSheetRead(
        order=order_read,
        customer_name=customer.name if customer else None,
        customer_address=customer.address if customer else None,
        customer_contact=customer.contact_name if customer else None,
        customer_phone=customer.phone if customer else None,
        entrust_no=entrust_no,
    )


@router.put("/{order_id}/entrust-layout", response_model=SalesOrderRead)
def update_sales_order_entrust_layout(
    order_id: UUID,
    payload: EntrustLayoutUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:update")),
) -> SalesOrderRead:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    details = dict(order.plate_details or {})
    layout = payload.model_dump(exclude_none=True)
    details["entrust_layout"] = layout
    order.plate_details = details
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="update_entrust_layout",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "layout": layout},
    )
    db.commit()
    db.refresh(order)
    return _serialize_sales_order(order, current_user)


@router.get("/{order_id}/timeline", response_model=list[TimelineItem])
def get_sales_order_timeline(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> list[TimelineItem]:
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    return build_sales_order_timeline(db, order)


@router.post("/{order_id}/confirm", response_model=SalesOrderRead)
def confirm_sales_order(
    order_id: UUID,
    payload: ConfirmOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission("order:confirm")),
) -> SalesOrder:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    transition = can_confirm_order(order.status)
    if not transition.allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=transition.reason)
    if payload.route_id:
        _ensure_active_route(db, payload.route_id)
        order.route_id = payload.route_id
    if order.route_id:
        _ensure_active_route(db, order.route_id)
    for item in order.items:
        if item.route_id:
            _ensure_active_route(db, item.route_id)
    if order.route_id is None and not all(item.route_id for item in order.items):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Route is required before confirmation.")
    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = datetime.now(timezone.utc)
    order.confirmed_by = current_user.id
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="confirm",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "status": order.status},
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/{order_id}/work-orders", response_model=list[WorkOrderRead], status_code=status.HTTP_201_CREATED)
def generate_work_orders(
    order_id: UUID,
    payload: GenerateWorkOrdersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("work_order:create")),
):
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    work_orders = create_work_orders_from_sales_order(db, order, payload.route_id)
    log_operation(
        db,
        user_id=current_user.id,
        module="work_order",
        action="generate",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "work_order_count": len(work_orders)},
    )
    db.commit()
    for work_order in work_orders:
        db.refresh(work_order)
    return work_orders


@router.delete("/{order_id}")
def delete_sales_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:cancel")),
) -> dict[str, bool]:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id).first()
    if order is None or order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    work_order_count = db.query(WorkOrder).filter(WorkOrder.sales_order_id == order.id, WorkOrder.deleted_at.is_(None)).count()
    if work_order_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Order already has work orders. Cancel work orders before deleting the order.",
        )

    if order.status not in {OrderStatus.DRAFT, OrderStatus.CONFIRMED, OrderStatus.CANCELLED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft, confirmed, or cancelled orders without work orders can be deleted.",
        )

    order.status = OrderStatus.CANCELLED
    order.deleted_at = datetime.now(timezone.utc)
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="delete",
        target_type="sales_order",
        target_id=order.id,
        before_data={"order_no": order.order_no, "status": order.status},
    )
    db.commit()
    return {"success": True}
