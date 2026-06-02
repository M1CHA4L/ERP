from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.process import ProcessRoute, ProcessRouteStep, ProcessTemplate
from app.models.product import Product
from app.models.production import WorkOrder, WorkOrderStep
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.schemas.maintenance import (
    CleanupProductItem,
    CleanupRouteItem,
    CleanupSummary,
    CleanupTemplateItem,
    MasterDataCleanupRead,
)
from app.services.audit import log_operation
from app.services.backup import backup_result_to_dict, backup_scheduler, list_backup_files, run_database_backup

router = APIRouter()


@router.get("/backups")
def list_database_backups(
    _=Depends(require_permission("system:permission")),
) -> dict[str, object]:
    return {
        "scheduler": backup_scheduler.status(),
        "items": [item.__dict__ for item in list_backup_files()],
    }


@router.post("/backups/run")
def run_database_backup_now(
    current_user: User = Depends(require_permission("system:permission")),
) -> dict[str, object]:
    result = run_database_backup()
    return {
        "success": True,
        "created_by": str(current_user.id),
        **backup_result_to_dict(result),
    }


def _template_usage(db: Session, template_id: UUID) -> tuple[int, int]:
    route_step_count = db.query(ProcessRouteStep).filter(ProcessRouteStep.process_template_id == template_id).count()
    work_order_step_count = db.query(WorkOrderStep).filter(WorkOrderStep.process_template_id == template_id).count()
    return route_step_count, work_order_step_count


def _route_usage(db: Session, route_id: UUID) -> tuple[int, int, int]:
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
    return product_count, direct_order_count + item_order_count, work_order_count


def _product_usage(db: Session, product_id: UUID) -> tuple[int, int]:
    sales_order_item_count = db.query(SalesOrderItem).filter(SalesOrderItem.product_id == product_id).count()
    work_order_count = (
        db.query(WorkOrder)
        .filter(WorkOrder.product_id == product_id, WorkOrder.deleted_at.is_(None))
        .count()
    )
    return sales_order_item_count, work_order_count


@router.get("/master-data-cleanup", response_model=MasterDataCleanupRead)
def get_master_data_cleanup(
    db: Session = Depends(get_db),
    _=Depends(require_permission("master_data:cleanup")),
) -> MasterDataCleanupRead:
    templates: list[CleanupTemplateItem] = []
    inactive_templates = 0
    unused_templates = 0
    for template in db.query(ProcessTemplate).order_by(ProcessTemplate.code.asc()).all():
        route_step_count, work_order_step_count = _template_usage(db, template.id)
        can_delete = route_step_count == 0 and work_order_step_count == 0
        if not template.enabled:
            inactive_templates += 1
        if can_delete:
            unused_templates += 1
        if template.enabled and not can_delete:
            continue
        reason = "已停用" if not template.enabled else "未被路线或工单引用"
        templates.append(
            CleanupTemplateItem(
                id=template.id,
                code=template.code,
                name=template.name,
                category=template.category,
                enabled=template.enabled,
                route_step_count=route_step_count,
                work_order_step_count=work_order_step_count,
                can_delete=can_delete,
                reason=reason,
                created_at=template.created_at,
                updated_at=template.updated_at,
            )
        )

    routes: list[CleanupRouteItem] = []
    inactive_routes = 0
    unused_routes = 0
    for route in db.query(ProcessRoute).order_by(ProcessRoute.route_code.asc()).all():
        product_count, sales_order_count, work_order_count = _route_usage(db, route.id)
        is_unused = product_count + sales_order_count + work_order_count == 0
        if route.status != "active":
            inactive_routes += 1
        if is_unused:
            unused_routes += 1
        if route.status == "active" and not is_unused:
            continue
        reason = "未启用/已禁用" if route.status != "active" else "未被产品、订单或工单引用"
        routes.append(
            CleanupRouteItem(
                id=route.id,
                route_code=route.route_code,
                name=route.name,
                version=route.version,
                status=route.status,
                product_count=product_count,
                sales_order_count=sales_order_count,
                work_order_count=work_order_count,
                can_restore=route.status == "disabled",
                reason=reason,
                created_at=route.created_at,
                updated_at=route.updated_at,
            )
        )

    products: list[CleanupProductItem] = []
    inactive_products = 0
    unused_products = 0
    for product in db.query(Product).order_by(Product.product_code.asc()).all():
        sales_order_item_count, work_order_count = _product_usage(db, product.id)
        is_inactive = product.status != "active" or product.deleted_at is not None
        is_unused = sales_order_item_count + work_order_count == 0
        if is_inactive:
            inactive_products += 1
        if is_unused:
            unused_products += 1
        if not is_inactive and not is_unused:
            continue
        reason = "已停用/已删除" if is_inactive else "未被订单或工单引用"
        products.append(
            CleanupProductItem(
                id=product.id,
                product_code=product.product_code,
                name=product.name,
                specification=product.specification,
                unit=product.unit,
                status=product.status,
                deleted_at=product.deleted_at,
                sales_order_item_count=sales_order_item_count,
                work_order_count=work_order_count,
                can_restore=is_inactive,
                reason=reason,
                created_at=product.created_at,
                updated_at=product.updated_at,
            )
        )

    return MasterDataCleanupRead(
        summary=CleanupSummary(
            inactive_templates=inactive_templates,
            unused_templates=unused_templates,
            inactive_routes=inactive_routes,
            unused_routes=unused_routes,
            inactive_products=inactive_products,
            unused_products=unused_products,
        ),
        templates=templates,
        routes=routes,
        products=products,
    )


@router.post("/master-data-cleanup/templates/{template_id}/restore")
def restore_process_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master_data:cleanup")),
) -> dict[str, bool]:
    template = db.get(ProcessTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process template not found.")
    before = {"code": template.code, "name": template.name, "enabled": template.enabled}
    template.enabled = True
    log_operation(
        db,
        user_id=current_user.id,
        module="maintenance",
        action="restore_template",
        target_type="process_template",
        target_id=template.id,
        before_data=before,
        after_data={"enabled": template.enabled},
    )
    db.commit()
    return {"success": True}


@router.post("/master-data-cleanup/routes/{route_id}/restore")
def restore_process_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master_data:cleanup")),
) -> dict[str, bool]:
    route = db.get(ProcessRoute, route_id)
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process route not found.")
    before = {"route_code": route.route_code, "name": route.name, "status": route.status}
    route.status = "draft"
    route.deleted_at = None
    log_operation(
        db,
        user_id=current_user.id,
        module="maintenance",
        action="restore_route",
        target_type="process_route",
        target_id=route.id,
        before_data=before,
        after_data={"status": route.status},
    )
    db.commit()
    return {"success": True}


@router.post("/master-data-cleanup/products/{product_id}/restore")
def restore_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master_data:cleanup")),
) -> dict[str, bool]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    before = {"product_code": product.product_code, "name": product.name, "status": product.status}
    product.status = "active"
    product.deleted_at = None
    log_operation(
        db,
        user_id=current_user.id,
        module="maintenance",
        action="restore_product",
        target_type="product",
        target_id=product.id,
        before_data=before,
        after_data={"status": product.status},
    )
    db.commit()
    return {"success": True}
