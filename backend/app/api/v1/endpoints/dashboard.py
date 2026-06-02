from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.production import WorkOrderStep
from app.models.sales import SalesOrder
from app.services.state_machine import OrderStatus, StepStatus

router = APIRouter()


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _=Depends(require_permission("dashboard:view")),
) -> dict[str, int]:
    open_order_statuses = [
        OrderStatus.DRAFT,
        OrderStatus.CONFIRMED,
        OrderStatus.IN_PRODUCTION,
        OrderStatus.PENDING_INSPECTION,
        OrderStatus.INSPECTION_PASSED,
        OrderStatus.PENDING_DELIVERY,
        OrderStatus.DELIVERED,
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.REWORKING,
    ]
    return {
        "draft_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.DRAFT).count(),
        "confirmed_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.CONFIRMED).count(),
        "in_production_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.IN_PRODUCTION).count(),
        "pending_inspection_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.PENDING_INSPECTION).count(),
        "inspection_passed_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.INSPECTION_PASSED).count(),
        "pending_delivery_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.PENDING_DELIVERY).count(),
        "delivered_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.DELIVERED).count(),
        "pending_payment_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.PENDING_PAYMENT).count(),
        "paid_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.PAID).count(),
        "reworking_orders": db.query(SalesOrder).filter(SalesOrder.status == OrderStatus.REWORKING).count(),
        "overdue_orders": (
            db.query(SalesOrder)
            .filter(SalesOrder.due_date < date.today(), SalesOrder.status.in_(open_order_statuses))
            .count()
        ),
        "pending_steps": db.query(WorkOrderStep).filter(WorkOrderStep.status == StepStatus.PENDING_PROCESS).count(),
        "processing_steps": db.query(WorkOrderStep).filter(WorkOrderStep.status == StepStatus.PROCESSING).count(),
        "pending_inspection_steps": db.query(WorkOrderStep).filter(WorkOrderStep.status == StepStatus.PENDING_INSPECTION).count(),
        "reworking_steps": db.query(WorkOrderStep).filter(WorkOrderStep.status == StepStatus.REWORKING).count(),
    }
