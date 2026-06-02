from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InventoryReceiptItem(BaseModel):
    product_name: str = Field(min_length=1)
    specification: str | None = None
    unit: str = "pcs"
    quantity: float = Field(gt=0)
    unit_price: float = Field(default=0, ge=0)
    owner_type: str = "company"
    customer_id: UUID | None = None
    remark: str | None = None


class InventoryReceiptCreate(BaseModel):
    warehouse_name: str = "Main"
    supplier_name: str | None = None
    movement_date: date
    handler_name: str | None = None
    remark: str | None = None
    items: list[InventoryReceiptItem] = Field(min_length=1)


class InventoryIssueItem(BaseModel):
    lot_id: UUID
    quantity: float = Field(gt=0)
    remark: str | None = None


class InventoryIssueCreate(BaseModel):
    warehouse_name: str = "Main"
    movement_date: date
    department: str | None = None
    receiver_name: str | None = None
    sales_order_id: UUID | None = None
    work_order_id: UUID | None = None
    cylinder_no: str | None = None
    remark: str | None = None
    items: list[InventoryIssueItem] = Field(min_length=1)


class CustomerMaterialUseCreate(BaseModel):
    customer_id: UUID
    lot_id: UUID
    quantity: float = Field(gt=0)
    sales_order_id: UUID | None = None
    work_order_id: UUID | None = None
    cylinder_no: str | None = None
    remark: str | None = None


class InventoryLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lot_no: str
    owner_type: str
    customer_id: UUID | None = None
    warehouse_name: str
    supplier_name: str | None = None
    product_name: str
    specification: str | None = None
    unit: str
    unit_price: float
    quantity_on_hand: float
    status: str
    remark: str | None = None


class InventoryTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movement_no: str
    movement_type: str
    lot_id: UUID | None = None
    customer_id: UUID | None = None
    sales_order_id: UUID | None = None
    work_order_id: UUID | None = None
    cylinder_no: str | None = None
    warehouse_name: str
    supplier_name: str | None = None
    product_name: str
    specification: str | None = None
    unit: str
    quantity: float
    unit_price: float
    total_amount: float
    movement_date: date
    status: str
    handler_name: str | None = None
    department: str | None = None
    receiver_name: str | None = None
    remark: str | None = None


class CylinderStockCreate(BaseModel):
    cylinder_no: str = Field(min_length=1, max_length=64)
    customer_id: UUID | None = None
    sales_order_id: UUID | None = None
    warehouse_name: str = "Cylinder Warehouse"
    diameter: float | None = None
    cylinder_length: float | None = None
    hole: str | None = None
    area_cm2: float | None = None
    unit_price: float = Field(default=0, ge=0)
    quantity: float = Field(default=1, gt=0)
    stock_in_date: date
    remark: str | None = None


class CylinderStockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stock_no: str
    cylinder_no: str
    customer_id: UUID | None = None
    sales_order_id: UUID | None = None
    warehouse_name: str
    diameter: float | None = None
    cylinder_length: float | None = None
    hole: str | None = None
    area_cm2: float | None = None
    unit_price: float
    quantity: float
    total_amount: float
    stock_status: str
    stock_in_date: date
    remark: str | None = None
