from datetime import datetime, time, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.finance import Payment, Receivable
from app.models.inventory import InventoryLot, InventoryTransaction
from app.models.logistics import DeliveryOrder
from app.models.production import InspectionRecord, ProcessRecord, ReworkRecord, WorkOrder, WorkOrderStep
from app.models.sales import SalesOrder
from app.schemas.timeline import TimelineItem


def _date_to_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _append(items: list[TimelineItem], **kwargs) -> None:
    items.append(TimelineItem(**kwargs))


def _sort_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def build_sales_order_timeline(db: Session, order: SalesOrder) -> list[TimelineItem]:
    items: list[TimelineItem] = []
    _append(
        items,
        occurred_at=order.created_at,
        category="order",
        title="订单创建",
        description=f"订单 {order.order_no} 已建立，金额 {float(order.total_amount):.2f}",
        status=order.status,
        entity_type="sales_order",
        entity_id=order.id,
        meta={"order_no": order.order_no},
    )
    if order.confirmed_at:
        _append(
            items,
            occurred_at=order.confirmed_at,
            category="order",
            title="订单确认",
            description="订单已确认，可以进入工单生成与排产。",
            status="confirmed",
            entity_type="sales_order",
            entity_id=order.id,
        )
    _append(
        items,
        occurred_at=_date_to_datetime(order.due_date),
        category="order",
        title="订单交期",
        description=f"计划交期 {order.due_date.isoformat()}",
        status=order.status,
        entity_type="sales_order",
        entity_id=order.id,
    )

    work_orders = (
        db.query(WorkOrder)
        .filter(WorkOrder.sales_order_id == order.id, WorkOrder.deleted_at.is_(None))
        .order_by(WorkOrder.created_at.asc())
        .all()
    )
    work_order_ids = [work_order.id for work_order in work_orders]
    for work_order in work_orders:
        _append(
            items,
            occurred_at=work_order.created_at,
            category="work_order",
            title=f"生成工单 {work_order.work_order_no}",
            description=f"{work_order.product_name}，数量 {float(work_order.quantity):g}",
            status=work_order.status,
            entity_type="work_order",
            entity_id=work_order.id,
            meta={"work_order_no": work_order.work_order_no},
        )
        if work_order.actual_start_at:
            _append(
                items,
                occurred_at=work_order.actual_start_at,
                category="work_order",
                title=f"工单开始 {work_order.work_order_no}",
                description="首道工序已开始加工。",
                status=work_order.status,
                entity_type="work_order",
                entity_id=work_order.id,
            )
        if work_order.actual_end_at:
            _append(
                items,
                occurred_at=work_order.actual_end_at,
                category="work_order",
                title=f"工单完成 {work_order.work_order_no}",
                description="工单所有工序已完成。",
                status=work_order.status,
                entity_type="work_order",
                entity_id=work_order.id,
            )

    if work_order_ids:
        steps = (
            db.query(WorkOrderStep, WorkOrder)
            .join(WorkOrder, WorkOrderStep.work_order_id == WorkOrder.id)
            .filter(WorkOrderStep.work_order_id.in_(work_order_ids))
            .order_by(WorkOrder.work_order_no.asc(), WorkOrderStep.step_no.asc())
            .all()
        )
        for step, work_order in steps:
            if step.actual_start_at:
                _append(
                    items,
                    occurred_at=step.actual_start_at,
                    category="step",
                    title=f"{step.step_no}. {step.step_name} 开始",
                    description=f"工单 {work_order.work_order_no}",
                    status=step.status,
                    entity_type="work_order_step",
                    entity_id=step.id,
                    meta={"work_order_no": work_order.work_order_no, "step_no": step.step_no},
                )
            if step.actual_end_at:
                description = f"加工 {float(step.input_qty or 0):g}，合格 {float(step.qualified_qty or 0):g}，不良 {float(step.defective_qty or 0):g}"
                _append(
                    items,
                    occurred_at=step.actual_end_at,
                    category="step",
                    title=f"{step.step_no}. {step.step_name} 完成",
                    description=description,
                    status=step.status,
                    entity_type="work_order_step",
                    entity_id=step.id,
                    meta={"work_order_no": work_order.work_order_no, "step_no": step.step_no},
                )

        records = (
            db.query(ProcessRecord, WorkOrderStep, WorkOrder)
            .join(WorkOrderStep, ProcessRecord.work_order_step_id == WorkOrderStep.id)
            .join(WorkOrder, ProcessRecord.work_order_id == WorkOrder.id)
            .filter(ProcessRecord.work_order_id.in_(work_order_ids))
            .order_by(ProcessRecord.reported_at.asc())
            .all()
        )
        for record, step, work_order in records:
            if record.action not in {"start", "complete"}:
                _append(
                    items,
                    occurred_at=record.reported_at,
                    category="record",
                    title=f"{step.step_name} 报工记录",
                    description=record.remark,
                    status=record.action,
                    entity_type="process_record",
                    entity_id=record.id,
                    meta={"work_order_no": work_order.work_order_no},
                )

        inspections = (
            db.query(InspectionRecord, WorkOrderStep, WorkOrder)
            .join(WorkOrderStep, InspectionRecord.work_order_step_id == WorkOrderStep.id)
            .join(WorkOrder, InspectionRecord.work_order_id == WorkOrder.id)
            .filter(InspectionRecord.work_order_id.in_(work_order_ids))
            .order_by(InspectionRecord.inspected_at.asc())
            .all()
        )
        for inspection, step, work_order in inspections:
            _append(
                items,
                occurred_at=inspection.inspected_at,
                category="inspection",
                title=f"质检 {inspection.inspection_no}",
                description=f"{work_order.work_order_no} / {step.step_name}：{inspection.result}",
                status=inspection.result,
                entity_type="inspection_record",
                entity_id=inspection.id,
                meta={"work_order_no": work_order.work_order_no, "step_name": step.step_name},
            )

        reworks = (
            db.query(ReworkRecord, WorkOrder)
            .join(WorkOrder, ReworkRecord.work_order_id == WorkOrder.id)
            .filter(ReworkRecord.work_order_id.in_(work_order_ids))
            .order_by(ReworkRecord.created_at.asc())
            .all()
        )
        for rework, work_order in reworks:
            _append(
                items,
                occurred_at=rework.created_at,
                category="rework",
                title=f"发起返工 {rework.rework_no}",
                description=f"工单 {work_order.work_order_no}，数量 {float(rework.quantity):g}",
                status=rework.status,
                entity_type="rework_record",
                entity_id=rework.id,
            )
            if rework.completed_at:
                _append(
                    items,
                    occurred_at=rework.completed_at,
                    category="rework",
                    title=f"返工完成 {rework.rework_no}",
                    description=f"工单 {work_order.work_order_no}",
                    status="completed",
                    entity_type="rework_record",
                    entity_id=rework.id,
                )

    deliveries = (
        db.query(DeliveryOrder)
        .filter(DeliveryOrder.sales_order_id == order.id, DeliveryOrder.deleted_at.is_(None))
        .order_by(DeliveryOrder.created_at.asc())
        .all()
    )
    delivery_ids = [delivery.id for delivery in deliveries]
    for delivery in deliveries:
        _append(
            items,
            occurred_at=delivery.created_at,
            category="delivery",
            title=f"生成送货单 {delivery.delivery_no}",
            description=delivery.address,
            status=delivery.status,
            entity_type="delivery_order",
            entity_id=delivery.id,
        )
        if delivery.signed_at:
            _append(
                items,
                occurred_at=delivery.signed_at,
                category="delivery",
                title=f"客户签收 {delivery.delivery_no}",
                description=delivery.signed_by,
                status="signed",
                entity_type="delivery_order",
                entity_id=delivery.id,
            )

    material_uses = (
        db.query(InventoryTransaction, InventoryLot.lot_no)
        .join(InventoryLot, InventoryTransaction.lot_id == InventoryLot.id)
        .filter(
            InventoryTransaction.sales_order_id == order.id,
            InventoryTransaction.movement_type == "issue",
            InventoryTransaction.quantity < 0,
            InventoryTransaction.deleted_at.is_(None),
            InventoryLot.owner_type == "customer",
            InventoryLot.deleted_at.is_(None),
        )
        .order_by(InventoryTransaction.created_at.asc())
        .all()
    )
    for transaction, lot_no in material_uses:
        quantity = abs(float(transaction.quantity))
        cylinder_no = f"，版号 {transaction.cylinder_no}" if transaction.cylinder_no else ""
        _append(
            items,
            occurred_at=transaction.created_at,
            category="material",
            title=f"使用客户来料 {lot_no}",
            description=(
                f"{transaction.product_name} {transaction.specification or ''}，"
                f"使用 {quantity:g}{transaction.unit}，仓库 {transaction.warehouse_name}{cylinder_no}"
            ),
            status=transaction.status,
            entity_type="inventory_transaction",
            entity_id=transaction.id,
            meta={"lot_no": lot_no, "movement_no": transaction.movement_no},
        )

    receivables = (
        db.query(Receivable)
        .filter(Receivable.sales_order_id == order.id, Receivable.deleted_at.is_(None))
        .order_by(Receivable.created_at.asc())
        .all()
    )
    receivable_ids = [receivable.id for receivable in receivables]
    for receivable in receivables:
        _append(
            items,
            occurred_at=receivable.created_at,
            category="finance",
            title=f"生成应收 {receivable.receivable_no}",
            description=f"应收 {float(receivable.amount):.2f}，余额 {float(receivable.balance_amount):.2f}",
            status=receivable.finance_status,
            entity_type="receivable",
            entity_id=receivable.id,
        )
        _append(
            items,
            occurred_at=_date_to_datetime(receivable.due_date),
            category="finance",
            title=f"应收到期 {receivable.receivable_no}",
            description=f"到期日 {receivable.due_date.isoformat()}",
            status=receivable.finance_status,
            entity_type="receivable",
            entity_id=receivable.id,
        )

    if receivable_ids:
        payments = (
            db.query(Payment)
            .filter(Payment.receivable_id.in_(receivable_ids), Payment.deleted_at.is_(None))
            .order_by(Payment.payment_date.asc(), Payment.created_at.asc())
            .all()
        )
        for payment in payments:
            _append(
                items,
                occurred_at=_date_to_datetime(payment.payment_date),
                category="finance",
                title=f"收款 {payment.payment_no}",
                description=f"收款金额 {float(payment.amount):.2f}",
                status="payment",
                entity_type="payment",
                entity_id=payment.id,
            )

    if not delivery_ids and order.status in {"inspection_passed", "pending_delivery"}:
        _append(
            items,
            occurred_at=None,
            category="delivery",
            title="待生成送货单",
            description="质检通过后可进入送货流程。",
            status="pending",
            entity_type="sales_order",
            entity_id=order.id,
        )

    return sorted(
        items,
        key=lambda item: (
            item.occurred_at is None,
            _sort_datetime(item.occurred_at),
            item.category,
            item.title,
        ),
    )
