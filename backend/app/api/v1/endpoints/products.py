from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.process import ProcessRoute
from app.models.product import Product
from app.models.rbac import User
from app.schemas.common import PageResponse
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.audit import log_operation
from app.services.excel import build_xlsx_response
from app.services.numbering import generate_number

router = APIRouter()


def _ensure_active_route(db: Session, route_id) -> None:
    route = db.get(ProcessRoute, route_id)
    if route is None or route.status != "active":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="默认工艺路线不存在或未启用。")


@router.get("", response_model=PageResponse[ProductRead])
def list_products(
    keyword: str | None = None,
    status_filter: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_permission("product:view")),
) -> PageResponse[ProductRead]:
    query = db.query(Product).filter(Product.deleted_at.is_(None))
    if keyword:
        query = query.filter(or_(Product.name.ilike(f"%{keyword}%"), Product.product_code.ilike(f"%{keyword}%")))
    if status_filter:
        query = query.filter(Product.status == status_filter)
    total = query.count()
    items = query.order_by(Product.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("product:create")),
) -> Product:
    product_code = payload.product_code or generate_number("PRD")
    exists = db.query(Product).filter(Product.product_code == product_code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product code already exists.")
    if payload.default_route_id:
        _ensure_active_route(db, payload.default_route_id)
    product = Product(product_code=product_code, **payload.model_dump(exclude={"product_code"}))
    db.add(product)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="product",
        action="create",
        target_type="product",
        target_id=product.id,
        after_data={"product_code": product.product_code, "name": product.name},
    )
    db.commit()
    db.refresh(product)
    return product


@router.get("/export")
def export_products(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("report:export")),
):
    query = db.query(Product).filter(Product.deleted_at.is_(None))
    if keyword:
        query = query.filter(or_(Product.name.ilike(f"%{keyword}%"), Product.product_code.ilike(f"%{keyword}%")))
    products = query.order_by(Product.created_at.desc()).all()
    log_operation(
        db,
        user_id=current_user.id,
        module="product",
        action="export",
        target_type="product",
        after_data={"count": len(products)},
    )
    db.commit()
    return build_xlsx_response(
        "products.xlsx",
        ["产品编码", "产品名称", "规格", "单位", "参考价", "状态", "备注"],
        [
            [
                product.product_code,
                product.name,
                product.specification or "",
                product.unit,
                float(product.reference_price) if product.reference_price is not None else "",
                product.status,
                product.remark or "",
            ]
            for product in products
        ],
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("product:view")),
) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("product:update")),
) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    if payload.default_route_id:
        _ensure_active_route(db, payload.default_route_id)
    before = {"product_code": product.product_code, "name": product.name, "status": product.status}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    log_operation(
        db,
        user_id=current_user.id,
        module="product",
        action="update",
        target_type="product",
        target_id=product.id,
        before_data=before,
        after_data={"product_code": product.product_code, "name": product.name, "status": product.status},
    )
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("product:delete")),
) -> dict[str, bool]:
    product = db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    product.status = "disabled"
    product.deleted_at = datetime.now(timezone.utc)
    log_operation(
        db,
        user_id=current_user.id,
        module="product",
        action="delete",
        target_type="product",
        target_id=product.id,
        before_data={"product_code": product.product_code, "name": product.name},
    )
    db.commit()
    return {"success": True}
