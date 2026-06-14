from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.models.process import ProcessRoute
from app.models.production import WorkOrder, WorkOrderStep
from app.models.sales import SalesOrder
from app.services.numbering import generate_number
from app.services.state_machine import OrderStatus, StepStatus, WorkOrderStatus, can_generate_work_order


def create_work_orders_from_sales_order(
    db: Session,
    sales_order: SalesOrder,
    route_id: UUID | None = None,
) -> list[WorkOrder]:
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"sales_order_work_orders:{sales_order.id}"},
    )
    existing = (
        db.query(WorkOrder.id)
        .filter(WorkOrder.sales_order_id == sales_order.id, WorkOrder.deleted_at.is_(None))
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Work orders already exist for this order.")

    transition = can_generate_work_order(sales_order.status)
    if not transition.allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=transition.reason)

    created: list[WorkOrder] = []
    fallback_route = (
        db.query(ProcessRoute)
        .options(selectinload(ProcessRoute.steps))
        .filter(ProcessRoute.status == "active")
        .order_by(ProcessRoute.is_default.desc(), ProcessRoute.route_code.asc())
        .first()
    )
    if fallback_route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active route not found.")

    for item in sales_order.items:
        effective_route_id = route_id or item.route_id or sales_order.route_id
        if effective_route_id is None:
            route = fallback_route
        else:
            route = (
                db.query(ProcessRoute)
                .options(selectinload(ProcessRoute.steps))
                .filter(ProcessRoute.id == effective_route_id, ProcessRoute.status == "active")
                .first()
            )
            if route is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active route not found.")

        work_order = WorkOrder(
            work_order_no=generate_number("WO"),
            sales_order_id=sales_order.id,
            sales_order_item_id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity,
            route_id=route.id,
            status=WorkOrderStatus.PENDING_SCHEDULE,
            priority=sales_order.priority,
        )

        for index, route_step in enumerate(route.steps):
            work_order.steps.append(
                WorkOrderStep(
                    process_template_id=route_step.process_template_id,
                    step_no=route_step.step_no,
                    step_name=route_step.step_name,
                    requires_inspection=route_step.requires_inspection,
                    status=StepStatus.PENDING_PROCESS if index == 0 else StepStatus.NOT_STARTED,
                )
            )

        db.add(work_order)
        created.append(work_order)

    sales_order.status = OrderStatus.IN_PRODUCTION
    db.flush()
    return created
