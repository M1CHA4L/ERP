from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.process import ProcessRoute, ProcessRouteStep, ProcessTemplate
from app.models.product import Product
from app.models.production import WorkOrderStep
from app.models.production import WorkOrder
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.schemas.process import (
    ProcessRouteCopy,
    ProcessRouteCreate,
    ProcessRouteRead,
    ProcessRouteUpdate,
    ProcessTemplateCreate,
    ProcessTemplateRead,
    ProcessTemplateUpdate,
    RouteStepCreate,
)
from app.services.audit import log_operation

router = APIRouter()
ROUTE_STATUSES = {"draft", "active", "disabled"}


def _route_query(db: Session):
    return db.query(ProcessRoute).options(selectinload(ProcessRoute.steps))


def _get_route_or_404(db: Session, route_id: UUID) -> ProcessRoute:
    route = _route_query(db).filter(ProcessRoute.id == route_id).first()
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process route not found.")
    return _attach_route_metadata(db, route)


def _route_usage_counts(db: Session, route_id: UUID) -> dict[str, int]:
    product_count = (
        db.query(Product)
        .filter(Product.default_route_id == route_id, Product.deleted_at.is_(None))
        .count()
    )
    direct_order_count = (
        db.query(SalesOrder)
        .filter(SalesOrder.route_id == route_id, SalesOrder.deleted_at.is_(None))
        .count()
    )
    item_order_count = (
        db.query(SalesOrderItem)
        .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
        .filter(SalesOrderItem.route_id == route_id, SalesOrder.deleted_at.is_(None))
        .count()
    )
    work_order_count = (
        db.query(WorkOrder)
        .filter(WorkOrder.route_id == route_id, WorkOrder.deleted_at.is_(None))
        .count()
    )
    return {
        "product_count": product_count,
        "sales_order_count": direct_order_count + item_order_count,
        "work_order_count": work_order_count,
    }


def _attach_route_metadata(db: Session, route: ProcessRoute) -> ProcessRoute:
    counts = _route_usage_counts(db, route.id)
    route.product_count = counts["product_count"]
    route.sales_order_count = counts["sales_order_count"]
    route.work_order_count = counts["work_order_count"]
    route.is_used = any(counts.values())
    route.can_edit_steps = not route.is_used
    route.source_route_code = None
    route.source_route_name = None
    if route.source_route_id:
        source = db.get(ProcessRoute, route.source_route_id)
        if source:
            route.source_route_code = source.route_code
            route.source_route_name = source.name
    return route


def _validate_route_status(route_status: str) -> None:
    if route_status not in ROUTE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Route status must be draft, active, or disabled.",
        )


def _replace_route_steps(db: Session, route: ProcessRoute, steps: list[RouteStepCreate]) -> None:
    if not steps:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one route step is required.")

    for existing_step in list(route.steps):
        db.delete(existing_step)
    db.flush()
    route.steps = []

    for index, step_payload in enumerate(steps, start=1):
        template = db.get(ProcessTemplate, step_payload.process_template_id)
        if template is None or not template.enabled:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Route step must use an enabled process template.",
            )
        route.steps.append(
            ProcessRouteStep(
                route_id=route.id,
                process_template_id=template.id,
                step_no=index,
                step_name=step_payload.step_name or template.name,
                is_optional=step_payload.is_optional,
                requires_inspection=(
                    template.requires_inspection
                    if step_payload.requires_inspection is None
                    else step_payload.requires_inspection
                ),
                planned_hours=step_payload.planned_hours,
                remark=step_payload.remark,
            )
        )


@router.get("/templates", response_model=list[ProcessTemplateRead])
def list_process_templates(
    db: Session = Depends(get_db),
    _=Depends(require_permission("route:view")),
) -> list[ProcessTemplate]:
    return db.query(ProcessTemplate).order_by(ProcessTemplate.code).all()


@router.post("/templates", response_model=ProcessTemplateRead, status_code=status.HTTP_201_CREATED)
def create_process_template(
    payload: ProcessTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("process:template:create")),
) -> ProcessTemplate:
    exists = db.query(ProcessTemplate).filter(ProcessTemplate.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="工序编码已存在，不能新增。")
    name_exists = db.query(ProcessTemplate).filter(ProcessTemplate.name == payload.name).first()
    if name_exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="工序名称已存在，不能新增。")
    template = ProcessTemplate(**payload.model_dump())
    db.add(template)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="create_template",
        target_type="process_template",
        target_id=template.id,
        after_data={"code": template.code, "name": template.name},
    )
    db.commit()
    db.refresh(template)
    return template


@router.put("/templates/{template_id}", response_model=ProcessTemplateRead)
def update_process_template(
    template_id: UUID,
    payload: ProcessTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("process:template:update")),
) -> ProcessTemplate:
    template = db.get(ProcessTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process template not found.")
    before = {"code": template.code, "name": template.name, "enabled": template.enabled}
    if payload.name and payload.name != template.name:
        name_exists = db.query(ProcessTemplate).filter(ProcessTemplate.name == payload.name).first()
        if name_exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="工序名称已存在，不能修改。")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="update_template",
        target_type="process_template",
        target_id=template.id,
        before_data=before,
        after_data={"code": template.code, "name": template.name, "enabled": template.enabled},
    )
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}")
def delete_process_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("process:template:delete")),
) -> dict[str, bool]:
    template = db.get(ProcessTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process template not found.")
    route_step_count = (
        db.query(ProcessRouteStep).filter(ProcessRouteStep.process_template_id == template.id).count()
    )
    work_order_step_count = (
        db.query(WorkOrderStep).filter(WorkOrderStep.process_template_id == template.id).count()
    )
    if route_step_count or work_order_step_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "该工序模板已被工艺路线或工单引用，不能删除；"
                "如后续不再使用，请编辑模板并关闭“启用”。"
            ),
        )
    before = {"code": template.code, "name": template.name, "enabled": template.enabled}
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="delete_template",
        target_type="process_template",
        target_id=template.id,
        before_data=before,
    )
    db.delete(template)
    db.commit()
    return {"success": True}


@router.get("", response_model=list[ProcessRouteRead])
def list_process_routes(
    db: Session = Depends(get_db),
    _=Depends(require_permission("route:view")),
) -> list[ProcessRoute]:
    routes = (
        db.query(ProcessRoute)
        .options(selectinload(ProcessRoute.steps))
        .filter(ProcessRoute.status != "disabled")
        .order_by(ProcessRoute.route_code)
        .all()
    )
    return [_attach_route_metadata(db, route) for route in routes]


@router.post("", response_model=ProcessRouteRead, status_code=status.HTTP_201_CREATED)
def create_process_route(
    payload: ProcessRouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("route:create")),
) -> ProcessRoute:
    _validate_route_status(payload.status)
    exists = db.query(ProcessRoute).filter(ProcessRoute.route_code == payload.route_code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="路线编码已存在，不能新增。")

    route = ProcessRoute(
        route_code=payload.route_code,
        name=payload.name,
        description=payload.description,
        version=1,
        is_default=payload.is_default,
        status=payload.status,
    )
    db.add(route)
    db.flush()
    _replace_route_steps(db, route, payload.steps)
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="create_route",
        target_type="process_route",
        target_id=route.id,
        after_data={"route_code": route.route_code, "name": route.name, "step_count": len(payload.steps)},
    )
    db.commit()
    return _get_route_or_404(db, route.id)


@router.post("/{route_id}/copy", response_model=ProcessRouteRead, status_code=status.HTTP_201_CREATED)
def copy_process_route(
    route_id: UUID,
    payload: ProcessRouteCopy,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("route:create")),
) -> ProcessRoute:
    source = _get_route_or_404(db, route_id)
    if source.status == "disabled":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="已删除路线不能复制。")
    _validate_route_status(payload.status)
    exists = db.query(ProcessRoute).filter(ProcessRoute.route_code == payload.route_code).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="路线编码已存在，不能复制。")

    route = ProcessRoute(
        route_code=payload.route_code,
        name=payload.name,
        description=payload.description if payload.description is not None else source.description,
        version=source.version + 1,
        source_route_id=source.id,
        is_default=payload.is_default,
        status=payload.status,
    )
    db.add(route)
    db.flush()
    if payload.steps is not None:
        _replace_route_steps(db, route, payload.steps)
        step_count = len(payload.steps)
    else:
        for step in source.steps:
            route.steps.append(
                ProcessRouteStep(
                    route_id=route.id,
                    process_template_id=step.process_template_id,
                    step_no=step.step_no,
                    step_name=step.step_name,
                    is_optional=step.is_optional,
                    requires_inspection=step.requires_inspection,
                    planned_hours=step.planned_hours,
                    remark=step.remark,
                )
            )
        step_count = len(source.steps)
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="copy_route",
        target_type="process_route",
        target_id=route.id,
        before_data={"source_route_id": str(source.id), "source_route_code": source.route_code},
        after_data={"route_code": route.route_code, "name": route.name, "step_count": step_count},
    )
    db.commit()
    return _get_route_or_404(db, route.id)


@router.get("/{route_id}", response_model=ProcessRouteRead)
def get_process_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("route:view")),
) -> ProcessRoute:
    return _get_route_or_404(db, route_id)


@router.put("/{route_id}", response_model=ProcessRouteRead)
def update_process_route(
    route_id: UUID,
    payload: ProcessRouteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("route:update")),
) -> ProcessRoute:
    route = _get_route_or_404(db, route_id)
    before = {
        "route_code": route.route_code,
        "name": route.name,
        "status": route.status,
        "step_count": len(route.steps),
    }
    data = payload.model_dump(exclude_unset=True)
    if "route_code" in data and data["route_code"] != route.route_code:
        exists = db.query(ProcessRoute).filter(ProcessRoute.route_code == data["route_code"]).first()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="路线编码已存在，不能修改。")
        route.route_code = data["route_code"]
    if "name" in data:
        route.name = data["name"]
    if "description" in data:
        route.description = data["description"]
    if "is_default" in data:
        route.is_default = data["is_default"]
    if "status" in data:
        _validate_route_status(data["status"])
        route.status = data["status"]
    if "steps" in data:
        if not route.can_edit_steps:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="该路线已被产品、订单或工单使用，不能直接修改工序步骤；请复制路线后调整新版本。",
            )
        _replace_route_steps(db, route, payload.steps or [])
    route.version += 1
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="update_route",
        target_type="process_route",
        target_id=route.id,
        before_data=before,
        after_data={
            "route_code": route.route_code,
            "name": route.name,
            "status": route.status,
            "step_count": len(payload.steps) if payload.steps is not None else len(route.steps),
        },
    )
    db.commit()
    return _get_route_or_404(db, route.id)


@router.delete("/{route_id}")
def disable_process_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("route:delete")),
) -> dict[str, bool]:
    route = _get_route_or_404(db, route_id)
    before = {"route_code": route.route_code, "name": route.name, "status": route.status}
    route.status = "disabled"
    route.is_default = False
    log_operation(
        db,
        user_id=current_user.id,
        module="process",
        action="disable_route",
        target_type="process_route",
        target_id=route.id,
        before_data=before,
    )
    db.commit()
    return {"success": True}
