from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    product_code: str | None = None
    name: str
    specification: str | None = None
    unit: str = "件"
    default_route_id: UUID | None = None
    reference_price: float | None = None
    status: str = "active"
    remark: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    specification: str | None = None
    unit: str | None = None
    default_route_id: UUID | None = None
    reference_price: float | None = None
    status: str | None = None
    remark: str | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_code: str
    name: str
    specification: str | None
    unit: str
    default_route_id: UUID | None
    reference_price: float | None
    status: str
    remark: str | None
