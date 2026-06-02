from __future__ import annotations

from datetime import date as Date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


PlateValue = str | int | float | bool | None


class PlateDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    order_type: PlateValue = None
    customer_text: PlateValue = None
    product_name: PlateValue = None
    total_qty: PlateValue = None
    unit_l: PlateValue = None
    straight: PlateValue = None
    cylinder_id: PlateValue = None
    increase: PlateValue = None
    hole: PlateValue = None
    flange: PlateValue = None
    cylinder_model: PlateValue = None
    cylinder_making: PlateValue = None
    new_material: PlateValue = None
    unit_w: PlateValue = None
    crossway: PlateValue = None
    order_date: PlateValue = None
    dynamic_balance: PlateValue = None
    slope: PlateValue = None
    original_no: PlateValue = None
    printing_method: PlateValue = None
    self_bring: PlateValue = None
    production_time: PlateValue = None
    cylinder_cost: PlateValue = None
    copper_thickness: PlateValue = None
    key_way: PlateValue = None
    returns: PlateValue = None
    archives: PlateValue = None
    inspection_requirement: PlateValue = None
    no: PlateValue = None
    sample_no: PlateValue = None
    printings: PlateValue = None
    salesman: PlateValue = None
    sign_in_person: PlateValue = None
    c_value: PlateValue = None
    l_value: PlateValue = None
    material_model: PlateValue = None
    plate_thickness: PlateValue = None
    cylinder_structure: PlateValue = None
    address: PlateValue = None
    lister: PlateValue = None
    bag_type: PlateValue = None
    material_new: PlateValue = None
    set_type: PlateValue = None
    mark_line: PlateValue = None
    test_line: PlateValue = None
    test_spot: PlateValue = None
    computer_position: PlateValue = None
    production_position: PlateValue = None
    common_remarks: PlateValue = None
    engraving_requirement: PlateValue = None
    proofing_requirement: PlateValue = None
    computer_requirement: PlateValue = None
    color_separation: PlateValue = None
    engraving_note: PlateValue = None
    dechrome_plan: PlateValue = None
    delivery_time: PlateValue = None
    charge: PlateValue = None
    total_branch: PlateValue = None
    finance_note: PlateValue = None
    receiver_name: PlateValue = None
    form_filler: PlateValue = None
    chrome_requirement: PlateValue = None
    polishing_requirement: PlateValue = None
    rework_reason: PlateValue = None
    rework_source_cylinder_no: PlateValue = None
    rework_target_step: PlateValue = None
    rework_quantity: PlateValue = None
    rework_chargeable: PlateValue = None


class ColorRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    color_no: PlateValue = None
    print_color: PlateValue = None
    qty: PlateValue = None
    dia: PlateValue = None
    real_dia: PlateValue = None
    public_no: PlateValue = None
    printing_method: PlateValue = None
    remarks: PlateValue = None


class SalesOrderItemCreate(BaseModel):
    product_id: UUID | None = None
    product_name: str
    specification: str | None = None
    quantity: float = Field(gt=0)
    unit: str = "件"
    unit_price: float = Field(ge=0)
    route_id: UUID | None = None
    remark: str | None = None


class SalesOrderCreate(BaseModel):
    customer_id: UUID
    due_date: Date
    route_id: UUID | None = None
    priority: str = "normal"
    remark: str | None = None
    plate_details: PlateDetails | None = None
    color_rows: list[ColorRow] | None = Field(default_factory=list)
    items: list[SalesOrderItemCreate]


class SalesOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID | None
    product_name: str
    specification: str | None
    quantity: float
    unit: str
    unit_price: float
    amount: float
    route_id: UUID | None


class SalesOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_no: str
    legacy_bussiness_mst_id: str | None = None
    legacy_bussiness_mst_rid: str | None = None
    customer_id: UUID
    product_summary: str
    order_date: Date
    due_date: Date
    total_amount: float
    status: str
    priority: str
    route_id: UUID | None
    rework_source_order_id: UUID | None = None
    rework_source_work_order_id: UUID | None = None
    rework_source_inspection_id: UUID | None = None
    plate_details: PlateDetails | None = None
    color_rows: list[ColorRow] | None = Field(default_factory=list)
    remark: str | None
    items: list[SalesOrderItemRead] = []


class EntrustSheetRead(BaseModel):
    order: SalesOrderRead
    customer_name: str | None = None
    customer_address: str | None = None
    customer_contact: str | None = None
    customer_phone: str | None = None
    entrust_no: str


class EntrustLayoutUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    title_mode: str | None = None
    diagram_style: str | None = None
    color_columns: int | None = Field(default=None, ge=4, le=14)
    show_info_table: bool | None = None
    show_color_table: bool | None = None
    show_layout_diagram: bool | None = None
    show_requirements: bool | None = None
    left_label: str | None = None
    center_label: str | None = None
    right_label: str | None = None
    top_note: str | None = None
    bottom_note: str | None = None
    width_label: str | None = None
    custom_note: str | None = None


class ConfirmOrderRequest(BaseModel):
    route_id: UUID | None = None


class EngravingColorRow(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: Date | None = None
    color_order: int | None = None
    color_no: str | None = None
    color_cylinder_no: str | None = None
    curve: str | None = None
    grid_line: str | None = None
    screen_angle: str | None = None
    stitch: str | None = None
    file_saved: bool = False
    shade_front: str | None = None
    shade_middle: str | None = None
    shade_back: str | None = None
    thorough_front: str | None = None
    thorough_middle: str | None = None
    thorough_back: str | None = None
    highlight_front: str | None = None
    highlight_middle: str | None = None
    highlight_back: str | None = None
    makeup_man: str | None = None
    remarks: str | None = None


class EngravingRecordUpdate(BaseModel):
    cylinder_no: str | None = None
    product_name: str | None = None
    salesman: str | None = None
    phone: str | None = None
    printed_material: str | None = None
    printing_method: str | None = None
    cylinder_circumference: float | None = None
    cylinder_length: float | None = None
    carving_width: float | None = None
    edge: float | None = None
    h_size: float | None = None
    testing_block: str | None = None
    testing_position: str | None = None
    keyway_position: str | None = None
    note: str | None = None
    rows: list[EngravingColorRow] = Field(default_factory=list)


class EngravingRecordRead(EngravingRecordUpdate):
    updated_at: Date | None = None
