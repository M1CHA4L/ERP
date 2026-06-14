from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.rbac import User
from app.models.sales import SalesOrder
from app.schemas.common import PageResponse
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.numbering import generate_number

router = APIRouter()


@router.get("", response_model=PageResponse[CustomerRead])
def list_customers(
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("customer:view")),
) -> PageResponse[CustomerRead]:
    query = db.query(Customer).options(selectinload(Customer.salesperson)).filter(Customer.deleted_at.is_(None))
    if keyword:
        query = query.filter(or_(Customer.name.ilike(f"%{keyword}%"), Customer.customer_code.ilike(f"%{keyword}%")))
    total = query.count()
    items = query.order_by(Customer.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customer:create")),
) -> Customer:
    customer_code = payload.customer_code or generate_number("C")
    exists = db.query(Customer).filter(Customer.customer_code == customer_code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer code already exists.")
    if payload.salesperson_id and db.get(User, payload.salesperson_id) is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Salesperson not found.")

    customer = Customer(customer_code=customer_code, **payload.model_dump(exclude={"customer_code"}))
    db.add(customer)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="customer",
        action="create",
        target_type="customer",
        target_id=customer.id,
        after_data={"customer_code": customer.customer_code, "name": customer.name},
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/export")
def export_customers(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    query = db.query(Customer).options(selectinload(Customer.salesperson)).filter(Customer.deleted_at.is_(None))
    if keyword:
        query = query.filter(or_(Customer.name.ilike(f"%{keyword}%"), Customer.customer_code.ilike(f"%{keyword}%")))
    customers = query.order_by(Customer.created_at.desc()).all()
    log_operation(
        db,
        user_id=current_user.id,
        module="customer",
        action="export",
        target_type="customer",
        after_data={"count": len(customers)},
    )
    db.commit()
    return build_xlsx_response(
        "customers.xlsx",
        [
            "Legacy Company ID",
            "Payment Method",
            "Minimum Price",
            "VAT 15%",
            "AIT 5%",
            "Advance %",
            "Lister",
            "客户编号",
            "客户名称",
            "客户类型",
            "重点客户",
            "业务员",
            "联系人",
            "客户联系电话",
            "公司电话",
            "传真",
            "地址",
            "账期天数",
            "税号",
            "开户银行",
            "开户账号",
            "交货方式",
            "镀铜厚度",
            "镀铬时间",
            "退镀成本",
            "对账周期",
            "对账日",
            "状态",
            "备注",
        ],
        [
            [
                customer.legacy_company_id or "",
                customer.payment_method or "",
                customer.minimum_price or "",
                "Y" if customer.vat_enabled else "N",
                "Y" if customer.ait_enabled else "N",
                customer.advance_percent or "",
                customer.lister or "",
                customer.customer_code,
                customer.name,
                customer.customer_type or "",
                "是" if customer.is_key_customer else "否",
                customer.salesperson_name or "",
                customer.contact_name or "",
                customer.phone or "",
                customer.company_phone or "",
                customer.fax or "",
                customer.address or "",
                customer.payment_terms_days,
                customer.tax_no or "",
                customer.bank_name or "",
                customer.bank_account or "",
                customer.delivery_method or "",
                customer.copper_thickness or "",
                customer.chrome_time or "",
                customer.stripping_cost or "",
                customer.reconciliation_cycle or "",
                customer.reconciliation_day or "",
                customer.status,
                customer.remark or "",
            ]
            for customer in customers
        ],
    )


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("customer:view")),
) -> Customer:
    customer = db.query(Customer).options(selectinload(Customer.salesperson)).filter(Customer.id == customer_id).first()
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return customer


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("customer:update")),
) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "salesperson_id" and value and db.get(User, value) is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Salesperson not found.")
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("customer:delete")),
) -> dict[str, bool]:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    active_order_count = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.customer_id == customer.id,
            SalesOrder.deleted_at.is_(None),
            SalesOrder.status != "cancelled",
        )
        .count()
    )
    if active_order_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Customer has active orders. Cancel or delete related orders first.",
        )

    customer.status = "disabled"
    customer.deleted_at = datetime.now(timezone.utc)
    log_operation(
        db,
        user_id=current_user.id,
        module="customer",
        action="delete",
        target_type="customer",
        target_id=customer.id,
        before_data={"customer_code": customer.customer_code, "name": customer.name},
    )
    db.commit()
    return {"success": True}
