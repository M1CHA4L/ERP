from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DeliverableOrder(BaseModel):
    sales_order_id: UUID
    order_no: str
    customer_id: UUID
    customer_name: str
    address: str | None
    product_summary: str
    total_amount: float
    status: str


class DeliveryOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sales_order_item_id: UUID | None
    product_name: str
    specification: str | None
    quantity: float
    unit: str


class DeliveryOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_no: str
    legacy_order_mst_id: str | None = None
    legacy_order_mst_rid: str | None = None
    legacy_bill_type: str | None = None
    sales_order_id: UUID
    customer_id: UUID
    address: str
    delivery_time: datetime
    driver_name: str | None
    logistics_no: str | None
    status: str
    signed_by: str | None
    signed_at: datetime | None
    remark: str | None
    items: list[DeliveryOrderItemRead] = []


class DeliveryOrderCreate(BaseModel):
    sales_order_id: UUID
    address: str | None = None
    delivery_time: datetime | None = None
    driver_name: str | None = None
    logistics_no: str | None = None
    remark: str | None = None


class ShipDeliveryRequest(BaseModel):
    logistics_no: str | None = None
    driver_name: str | None = None


class SignDeliveryRequest(BaseModel):
    signed_by: str
    signed_at: datetime | None = None
