from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.inventory import CylinderStock, InventoryLot, InventoryTransaction
from app.models.rbac import User
from app.schemas.common import PageResponse
from app.schemas.inventory import (
    CustomerMaterialUseCreate,
    CylinderStockCreate,
    CylinderStockRead,
    InventoryIssueCreate,
    InventoryLotRead,
    InventoryReceiptCreate,
    InventoryTransactionRead,
)
from app.services.audit import log_operation
from app.services.numbering import generate_number

router = APIRouter()


def _decimal(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0))


def _line_total(quantity: float, unit_price: float) -> Decimal:
    return _decimal(quantity) * _decimal(unit_price)


def _ensure_customer(db: Session, customer_id: UUID | None) -> None:
    if not customer_id:
        return
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.get("/lots", response_model=PageResponse[InventoryLotRead])
def list_inventory_lots(
    customer_id: UUID | None = None,
    owner_type: str | None = None,
    product_name: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory:view")),
) -> PageResponse[InventoryLotRead]:
    query = db.query(InventoryLot).filter(InventoryLot.deleted_at.is_(None))
    if customer_id:
        query = query.filter(InventoryLot.customer_id == customer_id)
    if owner_type:
        query = query.filter(InventoryLot.owner_type == owner_type)
    if product_name:
        query = query.filter(InventoryLot.product_name.ilike(f"%{product_name}%"))
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.outerjoin(Customer, InventoryLot.customer_id == Customer.id).filter(
            or_(
                InventoryLot.lot_no.ilike(term),
                InventoryLot.product_name.ilike(term),
                InventoryLot.specification.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
    total = query.count()
    items = query.order_by(InventoryLot.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/customer-materials", response_model=PageResponse[InventoryLotRead])
def list_customer_materials(
    customer_id: UUID,
    product_name: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory:view")),
) -> PageResponse[InventoryLotRead]:
    return list_inventory_lots(
        customer_id=customer_id,
        owner_type="customer",
        product_name=product_name,
        page=page,
        page_size=page_size,
        db=db,
        _=None,
    )


@router.post("/receipts", response_model=list[InventoryTransactionRead], status_code=status.HTTP_201_CREATED)
def create_inventory_receipt(
    payload: InventoryReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:receive")),
) -> list[InventoryTransaction]:
    transactions: list[InventoryTransaction] = []
    for item in payload.items:
        if item.owner_type == "customer" and not item.customer_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer material must have customer_id.")
        _ensure_customer(db, item.customer_id)
        lot = InventoryLot(
            lot_no=generate_number("LOT"),
            owner_type=item.owner_type,
            customer_id=item.customer_id,
            warehouse_name=payload.warehouse_name,
            supplier_name=payload.supplier_name,
            product_name=item.product_name,
            specification=item.specification,
            unit=item.unit,
            unit_price=item.unit_price,
            quantity_on_hand=item.quantity,
            remark=item.remark,
        )
        transaction = InventoryTransaction(
            movement_no=generate_number("IN"),
            movement_type="receipt",
            customer_id=item.customer_id,
            warehouse_name=payload.warehouse_name,
            supplier_name=payload.supplier_name,
            product_name=item.product_name,
            specification=item.specification,
            unit=item.unit,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_amount=_line_total(item.quantity, item.unit_price),
            movement_date=payload.movement_date,
            handler_name=payload.handler_name,
            remark=item.remark or payload.remark,
        )
        db.add(lot)
        db.flush()
        transaction.lot_id = lot.id
        db.add(transaction)
        transactions.append(transaction)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="inventory",
        action="receipt",
        target_type="inventory_transaction",
        after_data={"count": len(transactions)},
    )
    db.commit()
    for transaction in transactions:
        db.refresh(transaction)
    return transactions


@router.post("/issues", response_model=list[InventoryTransactionRead], status_code=status.HTTP_201_CREATED)
def create_inventory_issue(
    payload: InventoryIssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:issue")),
) -> list[InventoryTransaction]:
    transactions: list[InventoryTransaction] = []
    for item in payload.items:
        lot = db.get(InventoryLot, item.lot_id)
        if lot is None or lot.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory lot not found.")
        if _decimal(lot.quantity_on_hand) < _decimal(item.quantity):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{lot.product_name} stock is insufficient.")
        lot.quantity_on_hand = _decimal(lot.quantity_on_hand) - _decimal(item.quantity)
        if _decimal(lot.quantity_on_hand) <= 0:
            lot.status = "depleted"
        transaction = InventoryTransaction(
            movement_no=generate_number("OUT"),
            movement_type="issue",
            lot_id=lot.id,
            customer_id=lot.customer_id,
            sales_order_id=payload.sales_order_id,
            work_order_id=payload.work_order_id,
            cylinder_no=payload.cylinder_no,
            warehouse_name=payload.warehouse_name or lot.warehouse_name,
            supplier_name=lot.supplier_name,
            product_name=lot.product_name,
            specification=lot.specification,
            unit=lot.unit,
            quantity=-_decimal(item.quantity),
            unit_price=lot.unit_price,
            total_amount=-_line_total(item.quantity, lot.unit_price),
            movement_date=payload.movement_date,
            department=payload.department,
            receiver_name=payload.receiver_name,
            remark=item.remark or payload.remark,
        )
        db.add(transaction)
        transactions.append(transaction)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="inventory",
        action="issue",
        target_type="inventory_transaction",
        after_data={"count": len(transactions)},
    )
    db.commit()
    for transaction in transactions:
        db.refresh(transaction)
    return transactions


@router.post("/customer-materials/use", response_model=InventoryTransactionRead, status_code=status.HTTP_201_CREATED)
def use_customer_material(
    payload: CustomerMaterialUseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:issue")),
) -> InventoryTransaction:
    lot = db.get(InventoryLot, payload.lot_id)
    if lot is None or lot.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer material lot not found.")
    if lot.owner_type != "customer" or lot.customer_id != payload.customer_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer material cannot be used by another customer.")
    issue = create_inventory_issue(
        InventoryIssueCreate(
            warehouse_name=lot.warehouse_name,
            movement_date=date.today(),
            sales_order_id=payload.sales_order_id,
            work_order_id=payload.work_order_id,
            cylinder_no=payload.cylinder_no,
            remark=payload.remark,
            items=[{"lot_id": payload.lot_id, "quantity": payload.quantity, "remark": payload.remark}],
        ),
        db=db,
        current_user=current_user,
    )
    return issue[0]


@router.get("/transactions", response_model=PageResponse[InventoryTransactionRead])
def list_inventory_transactions(
    movement_type: str | None = None,
    customer_id: UUID | None = None,
    product_name: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory:view")),
) -> PageResponse[InventoryTransactionRead]:
    query = db.query(InventoryTransaction).filter(InventoryTransaction.deleted_at.is_(None))
    if movement_type:
        query = query.filter(InventoryTransaction.movement_type == movement_type)
    if customer_id:
        query = query.filter(InventoryTransaction.customer_id == customer_id)
    if product_name:
        query = query.filter(InventoryTransaction.product_name.ilike(f"%{product_name}%"))
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.outerjoin(Customer, InventoryTransaction.customer_id == Customer.id).filter(
            or_(
                InventoryTransaction.movement_no.ilike(term),
                InventoryTransaction.product_name.ilike(term),
                InventoryTransaction.specification.ilike(term),
                InventoryTransaction.cylinder_no.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
    total = query.count()
    items = query.order_by(InventoryTransaction.movement_date.desc(), InventoryTransaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/cylinder-stock-ins", response_model=CylinderStockRead, status_code=status.HTTP_201_CREATED)
def create_cylinder_stock_in(
    payload: CylinderStockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cylinder:stock_in")),
) -> CylinderStock:
    _ensure_customer(db, payload.customer_id)
    total_amount = _line_total(payload.quantity, payload.unit_price)
    stock = CylinderStock(
        stock_no=generate_number("CYL"),
        cylinder_no=payload.cylinder_no.strip(),
        customer_id=payload.customer_id,
        sales_order_id=payload.sales_order_id,
        warehouse_name=payload.warehouse_name,
        diameter=payload.diameter,
        cylinder_length=payload.cylinder_length,
        hole=payload.hole,
        area_cm2=payload.area_cm2,
        unit_price=payload.unit_price,
        quantity=payload.quantity,
        total_amount=total_amount,
        stock_in_date=payload.stock_in_date,
        remark=payload.remark,
    )
    db.add(stock)
    db.add(
        InventoryTransaction(
            movement_no=generate_number("CIN"),
            movement_type="cylinder_in",
            customer_id=payload.customer_id,
            sales_order_id=payload.sales_order_id,
            cylinder_no=payload.cylinder_no.strip(),
            warehouse_name=payload.warehouse_name,
            product_name=f"Cylinder {payload.cylinder_no}",
            specification=f"D {payload.diameter or '-'} / L {payload.cylinder_length or '-'}",
            unit="pcs",
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            total_amount=total_amount,
            movement_date=payload.stock_in_date,
            remark=payload.remark,
        )
    )
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="inventory",
        action="cylinder_stock_in",
        target_type="cylinder_stock",
        target_id=stock.id,
        after_data={"cylinder_no": stock.cylinder_no, "quantity": float(stock.quantity)},
    )
    db.commit()
    db.refresh(stock)
    return stock


@router.get("/cylinder-stocks", response_model=PageResponse[CylinderStockRead])
def list_cylinder_stocks(
    cylinder_no: str | None = None,
    customer_id: UUID | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("cylinder:view")),
) -> PageResponse[CylinderStockRead]:
    query = db.query(CylinderStock).filter(CylinderStock.deleted_at.is_(None))
    if cylinder_no:
        query = query.filter(CylinderStock.cylinder_no.ilike(f"%{cylinder_no}%"))
    if customer_id:
        query = query.filter(CylinderStock.customer_id == customer_id)
    if keyword:
        term = f"%{keyword.strip()}%"
        query = query.outerjoin(Customer, CylinderStock.customer_id == Customer.id).filter(
            or_(
                CylinderStock.stock_no.ilike(term),
                CylinderStock.cylinder_no.ilike(term),
                Customer.name.ilike(term),
                Customer.customer_code.ilike(term),
            )
        )
    total = query.count()
    items = query.order_by(CylinderStock.stock_in_date.desc(), CylinderStock.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)
