from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.process import ProcessRoute
from app.models.sales import EntrustLayoutTemplate, PlateNumberReservation, SalesOrder, SalesOrderItem
from app.models.production import WorkOrder
from app.models.rbac import User
from app.schemas.common import PageResponse
from app.schemas.production import GenerateWorkOrdersRequest, WorkOrderRead
from app.schemas.sales import (
    ConfirmOrderRequest,
    EngravingRecordRead,
    EngravingRecordUpdate,
    EntrustContentUpdate,
    EntrustLayoutTemplateCreate,
    EntrustLayoutTemplateRead,
    EntrustRequirementsUpdate,
    EntrustLayoutUpdate,
    EntrustSheetRead,
    SalesOrderCreate,
    SalesOrderMaterialUseRead,
    SalesOrderRead,
)
from app.schemas.timeline import TimelineItem
from app.services.numbering import generate_number
from app.services.plate_numbers import (
    get_usable_reservation,
    mark_reservation_used,
    next_derived_plate_number,
    normalize_derivation_type,
    normalize_plate_number,
    normalize_plate_number_kind,
    primary_plate_number_from_details,
)
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.printing import record_print_job
from app.services.state_machine import OrderStatus, can_confirm_order
from app.services.timeline import build_sales_order_timeline
from app.services.work_order_factory import create_work_orders_from_sales_order

router = APIRouter()

HISTORICAL_ORDER_STATUSES = {OrderStatus.PAID, OrderStatus.ARCHIVED, OrderStatus.CANCELLED}
ORDER_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _decimal(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


def _line_total(quantity: float, unit_price: float | Decimal | None) -> Decimal:
    return _decimal(quantity) * _decimal(unit_price)


def _ensure_active_route(db: Session, route_id: UUID) -> None:
    route = db.get(ProcessRoute, route_id)
    if route is None or route.status != "active":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="工艺路线不存在或未启用。")


def _use_customer_materials_for_order(
    db: Session,
    order: SalesOrder,
    uses: list,
    current_user: User,
) -> int:
    if not uses:
        return 0

    cylinder_no = primary_plate_number_from_details(order.plate_details or {})
    used_count = 0
    for item in uses:
        lot = db.get(InventoryLot, item.lot_id)
        if lot is None or lot.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer material lot not found.")
        if lot.owner_type != "customer" or lot.customer_id != order.customer_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer material cannot be used by another customer.")
        if _decimal(lot.quantity_on_hand) < _decimal(item.quantity):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{lot.product_name} customer material is insufficient.")

        lot.quantity_on_hand = _decimal(lot.quantity_on_hand) - _decimal(item.quantity)
        if _decimal(lot.quantity_on_hand) <= 0:
            lot.status = "depleted"

        db.add(
            InventoryTransaction(
                movement_no=generate_number("OUT"),
                movement_type="issue",
                lot_id=lot.id,
                customer_id=lot.customer_id,
                sales_order_id=order.id,
                cylinder_no=cylinder_no,
                warehouse_name=lot.warehouse_name,
                supplier_name=lot.supplier_name,
                product_name=lot.product_name,
                specification=lot.specification,
                unit=lot.unit,
                quantity=-_decimal(item.quantity),
                unit_price=lot.unit_price,
                total_amount=-_line_total(item.quantity, lot.unit_price),
                movement_date=date.today(),
                receiver_name=current_user.real_name or current_user.username,
                remark=item.remark or f"Used by order {order.order_no}",
            )
        )
        used_count += 1
    return used_count


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


def _normalize_datetime_text(value: object, fallback: datetime) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback.strftime("%Y-%m-%d %H:%M:%S")
    normalized = text.replace("T", " ").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized[: len(fmt)], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    if len(normalized) >= 10:
        return f"{normalized[:10]} {fallback.strftime('%H:%M:%S')}"
    return fallback.strftime("%Y-%m-%d %H:%M:%S")


def _filled_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_plate_order_timestamp(plate_details: dict) -> date:
    now = datetime.now(ORDER_TIMEZONE)
    order_datetime = _normalize_datetime_text(plate_details.get("order_datetime") or plate_details.get("order_date"), now)
    plate_details["order_datetime"] = order_datetime
    plate_details["order_date"] = order_datetime[:10]
    plate_details["order_time"] = order_datetime[11:19]
    return datetime.strptime(order_datetime[:10], "%Y-%m-%d").date()


def _set_primary_plate_number(plate_details: dict, plate_no: str) -> None:
    plate_details["cylinder_id"] = plate_no
    plate_details["no"] = plate_no
    plate_details["sample_no"] = plate_no


def _find_user_reserved_plate_number(db: Session, current_user: User, plate_no: str) -> PlateNumberReservation | None:
    if not plate_no:
        return None
    return (
        db.query(PlateNumberReservation)
        .filter(
            PlateNumberReservation.deleted_at.is_(None),
            PlateNumberReservation.assigned_user_id == current_user.id,
            PlateNumberReservation.status == "reserved",
            PlateNumberReservation.plate_no == plate_no,
        )
        .first()
    )


def _prepare_plate_number(
    db: Session,
    *,
    plate_details: dict,
    current_user: User,
) -> PlateNumberReservation | None:
    order_type = str(plate_details.get("order_type") or "new_cylinder").strip() or "new_cylinder"
    plate_details["order_type"] = order_type

    if order_type == "new_cylinder":
        try:
            kind = normalize_plate_number_kind(plate_details.get("plate_number_kind"))
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
        plate_details["plate_number_kind"] = kind

        reservation: PlateNumberReservation | None = None
        reservation_id = str(plate_details.get("reserved_plate_number_id") or "").strip()
        if reservation_id:
            try:
                reservation = get_usable_reservation(db, user=current_user, reservation_id=reservation_id)
            except ValueError as error:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
        else:
            typed_plate_no = primary_plate_number_from_details(plate_details)
            reservation = _find_user_reserved_plate_number(db, current_user, typed_plate_no)
            if typed_plate_no and reservation is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Please choose a plate number reserved by your account.",
                )

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Please request and choose a plate number before creating a new cylinder order.",
            )

        _set_primary_plate_number(plate_details, reservation.plate_no)
        plate_details["original_no"] = reservation.plate_no
        plate_details["reserved_plate_number_id"] = str(reservation.id)
        return reservation

    if order_type == "old_cylinder":
        source_plate_no = normalize_plate_number(
            plate_details.get("derived_source_cylinder_no") or plate_details.get("original_no") or plate_details.get("cylinder_id") or plate_details.get("no")
        )
        if not source_plate_no:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Source plate number is required for revision or remake.")
        try:
            derivation_type = normalize_derivation_type(plate_details.get("derivation_type"), default="revision")
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
        if derivation_type not in {"revision", "remake"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Revision orders can only use revision or remake plate numbers.")
        plate_no = next_derived_plate_number(db, source_plate_no=source_plate_no, derivation_type=derivation_type)
        plate_details["original_no"] = source_plate_no
        plate_details["derived_source_cylinder_no"] = source_plate_no
        plate_details["derivation_type"] = derivation_type
        _set_primary_plate_number(plate_details, plate_no)
        return None

    if order_type == "rework":
        source_plate_no = normalize_plate_number(
            plate_details.get("derived_source_cylinder_no") or plate_details.get("rework_source_cylinder_no") or plate_details.get("original_no")
        )
        if not source_plate_no:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Source plate number is required for rework.")
        try:
            derivation_type = normalize_derivation_type(plate_details.get("derivation_type"), default="internal_rework")
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
        if derivation_type not in {"internal_rework", "external_rework", "remake"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Rework orders can only use IR, OR, or remake plate numbers.")
        plate_no = next_derived_plate_number(db, source_plate_no=source_plate_no, derivation_type=derivation_type)
        plate_details["original_no"] = source_plate_no
        plate_details["derived_source_cylinder_no"] = source_plate_no
        plate_details["rework_source_cylinder_no"] = source_plate_no
        plate_details["derivation_type"] = derivation_type
        _set_primary_plate_number(plate_details, plate_no)
        return None

    return None


@router.get("", response_model=PageResponse[SalesOrderRead])
def list_sales_orders(
    status_filter: str | None = None,
    customer_id: UUID | None = None,
    keyword: str | None = None,
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
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.join(Customer, SalesOrder.customer_id == Customer.id).filter(
            or_(
                SalesOrder.order_no.ilike(term),
                SalesOrder.product_summary.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
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
    customer = (
        db.query(Customer)
        .options(selectinload(Customer.salesperson))
        .filter(Customer.id == payload.customer_id, Customer.deleted_at.is_(None))
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer not found.")

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
    if not _filled_text(plate_details.get("customer_text")):
        plate_details["customer_text"] = customer.name
    if not _filled_text(plate_details.get("address")) and customer.address:
        plate_details["address"] = customer.address
    if not _filled_text(plate_details.get("salesman")) and customer.salesperson_name:
        plate_details["salesman"] = customer.salesperson_name
    if not _filled_text(plate_details.get("lister")) and customer.lister:
        plate_details["lister"] = customer.lister
    order_date = _normalize_plate_order_timestamp(plate_details)
    reserved_plate_number = _prepare_plate_number(db, plate_details=plate_details, current_user=current_user)

    order = SalesOrder(
        order_no=generate_number("SO"),
        customer_id=payload.customer_id,
        product_summary=" / ".join(product_names[:3]),
        order_date=order_date,
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
    if reserved_plate_number is not None:
        mark_reservation_used(reserved_plate_number, order_id=order.id, user_id=current_user.id)
    customer_material_use_count = _use_customer_materials_for_order(
        db,
        order,
        payload.customer_material_uses or [],
        current_user,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="create",
        target_type="sales_order",
        target_id=order.id,
        after_data={
            "order_no": order.order_no,
            "total_amount": float(order.total_amount),
            "customer_material_use_count": customer_material_use_count,
        },
    )
    db.commit()
    db.refresh(order)
    return order


@router.get("/export")
def export_sales_orders(
    status_filter: str | None = None,
    keyword: str | None = None,
    order_type: str | None = None,
    include_history: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    query = db.query(SalesOrder).filter(SalesOrder.deleted_at.is_(None))
    query = _hide_restricted_orders(query, current_user, status_filter, include_history)
    if status_filter:
        query = query.filter(SalesOrder.status == status_filter)
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.join(Customer, SalesOrder.customer_id == Customer.id).filter(
            or_(
                SalesOrder.order_no.ilike(term),
                SalesOrder.product_summary.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
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


@router.get("/entrust-layout-templates", response_model=list[EntrustLayoutTemplateRead])
def list_entrust_layout_templates(
    template_type: str = Query(default="template", pattern="^(template|archive)$"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("order:view")),
) -> list[EntrustLayoutTemplate]:
    return (
        db.query(EntrustLayoutTemplate)
        .filter(
            EntrustLayoutTemplate.deleted_at.is_(None),
            EntrustLayoutTemplate.template_type == template_type,
        )
        .order_by(EntrustLayoutTemplate.created_at.desc())
        .all()
    )


@router.post("/entrust-layout-templates", response_model=EntrustLayoutTemplateRead, status_code=status.HTTP_201_CREATED)
def save_entrust_layout_template(
    payload: EntrustLayoutTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:update")),
) -> EntrustLayoutTemplate:
    name = payload.name.strip()
    template = (
        db.query(EntrustLayoutTemplate)
        .filter(
            EntrustLayoutTemplate.deleted_at.is_(None),
            EntrustLayoutTemplate.template_type == payload.template_type,
            EntrustLayoutTemplate.name == name,
        )
        .first()
    )
    action = "update_entrust_layout_template" if template else "create_entrust_layout_template"
    if template is None:
        template = EntrustLayoutTemplate(
            name=name,
            template_type=payload.template_type,
            created_by=current_user.id,
        )
        db.add(template)
    template.order_no = payload.order_no
    template.settings = payload.settings
    template.updated_by = current_user.id
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action=action,
        target_type="entrust_layout_template",
        target_id=template.id,
        after_data={"name": name, "template_type": payload.template_type},
    )
    db.commit()
    db.refresh(template)
    return template


@router.delete("/entrust-layout-templates/{template_id}")
def delete_entrust_layout_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:update")),
) -> dict[str, bool]:
    template = db.get(EntrustLayoutTemplate, template_id)
    if template is None or template.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    template.deleted_at = datetime.now(timezone.utc)
    template.updated_by = current_user.id
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="delete_entrust_layout_template",
        target_type="entrust_layout_template",
        target_id=template.id,
        after_data={"name": template.name, "template_type": template.template_type},
    )
    db.commit()
    return {"success": True}


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


@router.get("/{order_id}/material-uses", response_model=list[SalesOrderMaterialUseRead])
def list_sales_order_material_uses(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> list[SalesOrderMaterialUseRead]:
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)

    rows = (
        db.query(InventoryTransaction, InventoryLot.lot_no)
        .join(InventoryLot, InventoryTransaction.lot_id == InventoryLot.id)
        .filter(
            InventoryTransaction.deleted_at.is_(None),
            InventoryTransaction.sales_order_id == order_id,
            InventoryTransaction.movement_type == "issue",
            InventoryTransaction.quantity < 0,
            InventoryLot.owner_type == "customer",
            InventoryLot.deleted_at.is_(None),
        )
        .order_by(InventoryTransaction.created_at.desc())
        .all()
    )
    return [
        SalesOrderMaterialUseRead(
            movement_no=transaction.movement_no,
            lot_id=transaction.lot_id,
            lot_no=lot_no,
            product_name=transaction.product_name,
            specification=transaction.specification,
            quantity_used=abs(float(transaction.quantity)),
            unit=transaction.unit,
            warehouse_name=transaction.warehouse_name,
            movement_date=transaction.movement_date,
            cylinder_no=transaction.cylinder_no,
            remark=transaction.remark,
            status=transaction.status,
        )
        for transaction, lot_no in rows
    ]


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
    current_user: User = Depends(require_permission("order:update")),
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


@router.post("/{order_id}/entrust/print")
def record_sales_order_entrust_print(
    order_id: UUID,
    payload: EntrustLayoutUpdate | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:view")),
) -> dict[str, str]:
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    customer = db.get(Customer, order.customer_id)
    plate_details = order.plate_details or {}
    layout = payload.model_dump(mode="json") if payload else plate_details.get("entrust_layout")
    entrust_no = str(plate_details.get("sample_no") or order.order_no)
    print_job = record_print_job(
        db,
        document_type="entrust_sheet",
        target_type="sales_order",
        target_id=order.id,
        printed_by=current_user.id,
        snapshot={
            "order_no": order.order_no,
            "entrust_no": entrust_no,
            "customer_name": customer.name if customer else None,
            "layout": layout,
        },
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="print_entrust_sheet",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "print_no": print_job.print_no},
    )
    db.commit()
    return {"print_no": print_job.print_no}


@router.put("/{order_id}/entrust-content", response_model=SalesOrderRead)
def update_sales_order_entrust_content(
    order_id: UUID,
    payload: EntrustContentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:update")),
) -> SalesOrderRead:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)

    details = dict(order.plate_details or {})
    updates = payload.plate_details.model_dump(exclude_unset=True) if payload.plate_details else {}
    updates.pop("entrust_layout", None)
    for key, raw_value in updates.items():
        text_value = str(raw_value).strip() if raw_value is not None else ""
        if text_value:
            details[key] = text_value
        else:
            details.pop(key, None)

    if "order_datetime" in details or "order_date" in details:
        order.order_date = _normalize_plate_order_timestamp(details)

    if payload.color_rows is not None:
        order.color_rows = [row.model_dump(exclude_none=True) for row in payload.color_rows]

    product_name = str(details.get("product_name") or "").strip()
    if product_name:
        order.product_summary = product_name
        if order.items:
            order.items[0].product_name = product_name

    order.plate_details = details
    order.remark = str(details.get("common_remarks") or "").strip() or None
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="update_entrust_content",
        target_type="sales_order",
        target_id=order.id,
        after_data={
            "order_no": order.order_no,
            "fields": sorted(updates.keys()),
            "color_rows": len(payload.color_rows or order.color_rows or []),
        },
    )
    db.commit()
    db.refresh(order)
    return _serialize_sales_order(order, current_user)


@router.put("/{order_id}/entrust-requirements", response_model=SalesOrderRead)
def update_sales_order_entrust_requirements(
    order_id: UUID,
    payload: EntrustRequirementsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("order:update")),
) -> SalesOrderRead:
    order = db.query(SalesOrder).options(selectinload(SalesOrder.items)).filter(SalesOrder.id == order_id, SalesOrder.deleted_at.is_(None)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    _ensure_order_visible(order, current_user)
    details = dict(order.plate_details or {})
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        text_value = str(value).strip() if value is not None else ""
        if text_value:
            details[key] = text_value
        else:
            details.pop(key, None)
    order.plate_details = details
    order.remark = str(details.get("common_remarks") or "").strip() or None
    log_operation(
        db,
        user_id=current_user.id,
        module="order",
        action="update_entrust_requirements",
        target_type="sales_order",
        target_id=order.id,
        after_data={"order_no": order.order_no, "fields": sorted(updates.keys())},
    )
    db.commit()
    db.refresh(order)
    return _serialize_sales_order(order, current_user)


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

    used_plate_numbers = (
        db.query(PlateNumberReservation)
        .filter(
            PlateNumberReservation.deleted_at.is_(None),
            PlateNumberReservation.used_order_id == order.id,
            PlateNumberReservation.status == "used",
        )
        .all()
    )
    for reservation in used_plate_numbers:
        reservation.status = "available"
        reservation.assigned_user_id = None
        reservation.used_order_id = None
        reservation.used_at = None
        reservation.returned_at = datetime.now(timezone.utc)
        reservation.updated_by = current_user.id

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
