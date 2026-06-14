from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.product import Product
from app.schemas.product import ProductOptionRead

router = APIRouter()


@router.get("/options", response_model=list[ProductOptionRead])
def list_product_options(
    keyword: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("product:view")),
) -> list[Product]:
    query = db.query(Product).filter(Product.deleted_at.is_(None), Product.status == "active")
    if keyword:
        query = query.filter(or_(Product.name.ilike(f"%{keyword}%"), Product.product_code.ilike(f"%{keyword}%")))
    return query.order_by(Product.product_code.asc(), Product.name.asc()).all()
