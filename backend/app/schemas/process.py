from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProcessTemplateCreate(BaseModel):
    code: str
    name: str
    category: str | None = None
    requires_inspection: bool = False
    enabled: bool = True


class ProcessTemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    requires_inspection: bool | None = None
    enabled: bool | None = None


class ProcessTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    category: str | None
    requires_inspection: bool
    enabled: bool


class RouteStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_no: int
    step_name: str
    process_template_id: UUID
    is_optional: bool
    requires_inspection: bool
    planned_hours: float | None = None
    remark: str | None = None


class RouteStepCreate(BaseModel):
    process_template_id: UUID
    step_name: str | None = None
    is_optional: bool = False
    requires_inspection: bool | None = None
    planned_hours: float | None = Field(default=None, ge=0)
    remark: str | None = None


class ProcessRouteCreate(BaseModel):
    route_code: str
    name: str
    description: str | None = None
    is_default: bool = False
    status: str = "active"
    steps: list[RouteStepCreate]


class ProcessRouteUpdate(BaseModel):
    route_code: str | None = None
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    status: str | None = None
    steps: list[RouteStepCreate] | None = None


class ProcessRouteCopy(BaseModel):
    route_code: str
    name: str
    description: str | None = None
    is_default: bool = False
    status: str = "active"
    steps: list[RouteStepCreate] | None = None


class ProcessRouteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    route_code: str
    name: str
    version: int
    source_route_id: UUID | None = None
    source_route_code: str | None = None
    source_route_name: str | None = None
    description: str | None
    is_default: bool
    status: str
    product_count: int = 0
    sales_order_count: int = 0
    work_order_count: int = 0
    is_used: bool = False
    can_edit_steps: bool = True
    steps: list[RouteStepRead] = []
