from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerPriceRule(BaseModel):
    max_cm2: float | None = None
    min_cm2: float | None = None
    min_l: float | None = None
    max_l: float | None = None
    min_c: float | None = None
    max_c: float | None = None
    old_pcs: float | None = None
    repair_chromium_pcs: float | None = None
    special_cyl_price: float | None = None


class CustomerBase(BaseModel):
    legacy_company_id: str | None = None
    name: str = Field(min_length=1, max_length=128)
    customer_type: str | None = None
    is_key_customer: bool = False
    contact_name: str | None = None
    phone: str | None = None
    company_phone: str | None = None
    fax: str | None = None
    address: str | None = None
    salesperson_id: UUID | None = None
    payment_terms_days: int = 30
    payment_method: str | None = None
    minimum_price: float | None = None
    vat_enabled: bool = False
    ait_enabled: bool = False
    advance_percent: float | None = None
    lister: str | None = None
    price_rules: list[CustomerPriceRule] | None = Field(default_factory=list)
    credit_limit: float | None = None
    tax_no: str | None = None
    office: str | None = None
    opening_remark: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    delivery_method: str | None = None
    copper_thickness: float | None = None
    chrome_time: float | None = None
    stripping_cost: float | None = None
    reconciliation_cycle: str | None = None
    reconciliation_day: int | None = None
    remark: str | None = None
    status: str = "active"


class CustomerCreate(CustomerBase):
    customer_code: str | None = None


class CustomerUpdate(BaseModel):
    legacy_company_id: str | None = None
    name: str | None = None
    customer_type: str | None = None
    is_key_customer: bool | None = None
    contact_name: str | None = None
    phone: str | None = None
    company_phone: str | None = None
    fax: str | None = None
    address: str | None = None
    salesperson_id: UUID | None = None
    payment_terms_days: int | None = None
    payment_method: str | None = None
    minimum_price: float | None = None
    vat_enabled: bool | None = None
    ait_enabled: bool | None = None
    advance_percent: float | None = None
    lister: str | None = None
    price_rules: list[CustomerPriceRule] | None = None
    credit_limit: float | None = None
    tax_no: str | None = None
    office: str | None = None
    opening_remark: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    delivery_method: str | None = None
    copper_thickness: float | None = None
    chrome_time: float | None = None
    stripping_cost: float | None = None
    reconciliation_cycle: str | None = None
    reconciliation_day: int | None = None
    remark: str | None = None
    status: str | None = None


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_code: str
    salesperson_name: str | None = None
