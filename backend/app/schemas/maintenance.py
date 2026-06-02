from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CleanupSummary(BaseModel):
    inactive_templates: int
    unused_templates: int
    inactive_routes: int
    unused_routes: int
    inactive_products: int
    unused_products: int


class CleanupTemplateItem(BaseModel):
    id: UUID
    code: str
    name: str
    category: str | None
    enabled: bool
    route_step_count: int
    work_order_step_count: int
    can_delete: bool
    reason: str
    created_at: datetime | None
    updated_at: datetime | None


class CleanupRouteItem(BaseModel):
    id: UUID
    route_code: str
    name: str
    version: int
    status: str
    product_count: int
    sales_order_count: int
    work_order_count: int
    can_restore: bool
    reason: str
    created_at: datetime | None
    updated_at: datetime | None


class CleanupProductItem(BaseModel):
    id: UUID
    product_code: str
    name: str
    specification: str | None
    unit: str
    status: str
    deleted_at: datetime | None
    sales_order_item_count: int
    work_order_count: int
    can_restore: bool
    reason: str
    created_at: datetime | None
    updated_at: datetime | None


class MasterDataCleanupRead(BaseModel):
    summary: CleanupSummary
    templates: list[CleanupTemplateItem]
    routes: list[CleanupRouteItem]
    products: list[CleanupProductItem]
