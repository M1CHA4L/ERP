from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.customer import Customer
from app.models.logistics import DeliveryOrder, DeliveryOrderItem
from app.models.rbac import User
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.workflow_v2 import AbnormalProcessRecord, EpinBatch, FinanceBill, MakingAssignment, OrderWorkflowNode, PreOrder, SignRecord
from app.schemas.common import PageResponse
from app.schemas.workflow_v2 import (
    AbnormalFlowCreate,
    AbnormalFlowRead,
    ConvertPreOrderRequest,
    EpinBatchRead,
    JoinCheckRead,
    MakingAssignmentCreate,
    MakingAssignmentRead,
    MakingCompleteRequest,
    PreOrderCreate,
    PreOrderRead,
    WorkflowEdgeGraphRead,
    WorkflowDeliverySummary,
    WorkflowFinanceBillSummary,
    WorkflowFulfillmentSummary,
    WorkflowGraphRead,
    WorkflowNodeActionRequest,
    WorkflowNodeRead,
    WorkflowSignSummary,
    WorkflowStartRequest,
    WorkflowTemplateRead,
)
from app.services.audit import log_operation
from app.services.numbering import generate_number
from app.services.state_machine import OrderStatus
from app.services.workflow_v2 import (
    FORBIDDEN_ABNORMAL_PROCESS_NODES,
    EPIN_NODE_CODE,
    JOIN_NODE_CODE,
    MAKING_DISPATCH_NODE_CODE,
    approve_abnormal_process_record,
    check_join,
    complete_abnormal_process_record,
    complete_epin_batch,
    complete_making_assignment,
    complete_node,
    create_making_assignments,
    get_default_template,
    get_workflow_for_order,
    receive_epin_batch,
    reject_abnormal_process_record,
    seed_default_parallel_workflow_template,
    start_node,
    start_workflow_for_order,
    submit_making_assignment_to_epin,
)

router = APIRouter()

MANAGER_ROLE_CODES = {"admin", "boss", "production_manager"}
MAKING_ASSIGNABLE_ROLE_CODES = {"operator", "designer"}
NODE_PERMISSION_REQUIREMENTS = {
    MAKING_DISPATCH_NODE_CODE: "workflow_v2:making:assign",
    EPIN_NODE_CODE: "workflow_v2:epin:operate",
    JOIN_NODE_CODE: "workflow_v2:join:release",
}
NODE_DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "制作": ("制作", "production", "看样制作"),
    "电拼": ("电拼", "carving make-up", "make-up", "makeup"),
    "卷板": ("卷板", "sheet bending"),
    "法版": ("法版", "法兰", "flange"),
    "车床": ("车床", "lathe", "机加工"),
    "磨床": ("磨床", "基磨", "basic grinding", "机加工"),
    "镀铜": ("镀铜", "镀铬", "退铬", "plating", "chrome"),
    "研磨": ("研磨", "铜磨", "copper grinding"),
    "雕刻": ("雕刻", "电雕", "engraving"),
    "镀铬": ("镀铬", "退铬", "chrome"),
    "打样": ("打样", "proofing"),
    "检验": ("检验", "inspection"),
    "财务": ("财务", "会计", "出纳", "开票", "统计", "finance", "account"),
    "送货": ("送货", "仓库", "仓储", "物流", "delivery", "warehouse"),
}


def _role_codes(user: User) -> set[str]:
    return {role.code for role in user.roles}


def _is_workflow_manager(user: User) -> bool:
    roles = _role_codes(user)
    return bool(roles & MANAGER_ROLE_CODES) or "workflow_v2:template:manage" in user.permission_codes


def _can_browse_workflows(user: User) -> bool:
    if _is_workflow_manager(user):
        return True
    return bool({"workflow_v2:start", "workflow_v2:order:create"} & set(user.permission_codes))


def _can_browse_pre_orders(user: User) -> bool:
    if _is_workflow_manager(user):
        return True
    return bool(
        {
            "workflow_v2:pre_order:create",
            "workflow_v2:pre_order:confirm",
            "workflow_v2:order:create",
        }
        & set(user.permission_codes)
    )


def _normalized_text(value: str | None) -> str:
    return (value or "").strip().casefold()


def _department_matches_user(node_department: str | None, user: User) -> bool:
    if not node_department:
        return False
    user_department = _normalized_text(user.department)
    node_department_text = _normalized_text(node_department)
    if not user_department:
        return False
    if node_department_text in user_department or user_department in node_department_text:
        return True
    keywords = NODE_DEPARTMENT_KEYWORDS.get(node_department, ())
    return any(_normalized_text(keyword) in user_department for keyword in keywords)


def _can_operate_node(user: User, node: OrderWorkflowNode) -> bool:
    if "workflow_v2:operate" not in user.permission_codes:
        return False
    if _is_workflow_manager(user):
        return True
    if node.assigned_user_id == user.id:
        return True
    required_permission = NODE_PERMISSION_REQUIREMENTS.get(node.node_code)
    if required_permission:
        if required_permission not in user.permission_codes:
            return False
        if node.node_code == EPIN_NODE_CODE:
            return _department_matches_user("电拼", user)
        return True
    return _department_matches_user(node.department, user)


def _ensure_can_operate_node(user: User, node: OrderWorkflowNode) -> None:
    if not _can_operate_node(user, node):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only operate workflow nodes assigned to your department or account.")


def _ensure_can_operate_epin(user: User) -> None:
    if _is_workflow_manager(user):
        return
    if "workflow_v2:epin:operate" in user.permission_codes and _department_matches_user("电拼", user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only epin department users can operate epin batches.")


def _is_assignable_making_employee(user: User) -> bool:
    if user.status != "active" or user.deleted_at is not None:
        return False
    return bool(_role_codes(user) & MAKING_ASSIGNABLE_ROLE_CODES)


def _ensure_assignable_making_employees(db: Session, employee_ids: list[UUID]) -> None:
    unique_ids = list(dict.fromkeys(employee_ids))
    if not unique_ids:
        return

    employees = (
        db.query(User)
        .options(selectinload(User.roles))
        .filter(User.id.in_(unique_ids))
        .all()
    )
    employees_by_id = {employee.id: employee for employee in employees}
    invalid_names: list[str] = []
    for employee_id in unique_ids:
        employee = employees_by_id.get(employee_id)
        if employee is None or not _is_assignable_making_employee(employee):
            invalid_names.append(employee.real_name or employee.username if employee else str(employee_id))

    if invalid_names:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Making assignments can only target active operator or designer accounts: {', '.join(invalid_names)}",
        )


def _can_view_sales_order_workflow(db: Session, user: User, sales_order_id: UUID) -> bool:
    if _can_browse_workflows(user):
        return True
    nodes = (
        db.query(OrderWorkflowNode)
        .filter(
            OrderWorkflowNode.sales_order_id == sales_order_id,
            OrderWorkflowNode.deleted_at.is_(None),
            OrderWorkflowNode.status.in_(("active", "in_progress", "waiting")),
        )
        .all()
    )
    if any(_can_operate_node(user, node) for node in nodes):
        return True
    if (
        db.query(MakingAssignment.id)
        .filter(
            MakingAssignment.sales_order_id == sales_order_id,
            MakingAssignment.employee_id == user.id,
            MakingAssignment.deleted_at.is_(None),
        )
        .first()
        is not None
    ):
        return True
    epin_query = db.query(EpinBatch.id).filter(EpinBatch.sales_order_id == sales_order_id, EpinBatch.deleted_at.is_(None))
    if _department_matches_user("电拼", user) and "workflow_v2:epin:operate" in user.permission_codes:
        return epin_query.first() is not None
    return epin_query.filter(EpinBatch.employee_id == user.id).first() is not None


def _ensure_can_view_sales_order_workflow(db: Session, user: User, sales_order_id: UUID) -> None:
    if not _can_view_sales_order_workflow(db, user, sales_order_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view workflow orders related to your account or department.")


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _require_text(value: str | None, label: str) -> str:
    text = _clean_text(value)
    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{label} is required.")
    return text


def _workflow_sales_order(db: Session, sales_order_id: UUID) -> SalesOrder:
    order = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.id == sales_order_id, SalesOrder.deleted_at.is_(None))
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    return order


def _order_customer(db: Session, order: SalesOrder) -> Customer:
    customer = db.get(Customer, order.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return customer


def _active_delivery_for_order(db: Session, sales_order_id: UUID) -> DeliveryOrder | None:
    return (
        db.query(DeliveryOrder)
        .options(selectinload(DeliveryOrder.items))
        .filter(
            DeliveryOrder.sales_order_id == sales_order_id,
            DeliveryOrder.deleted_at.is_(None),
            DeliveryOrder.status != "cancelled",
        )
        .order_by(DeliveryOrder.created_at.desc())
        .first()
    )


def _ensure_workflow_delivery_order(
    db: Session,
    *,
    order: SalesOrder,
    delivery_no: str | None = None,
    address: str | None = None,
    delivery_time: datetime | None = None,
    driver_name: str | None = None,
    logistics_no: str | None = None,
    remark: str | None = None,
) -> DeliveryOrder:
    customer = _order_customer(db, order)
    delivery_no = _clean_text(delivery_no) or None
    if delivery_no:
        existing_by_no = (
            db.query(DeliveryOrder)
            .options(selectinload(DeliveryOrder.items))
            .filter(DeliveryOrder.delivery_no == delivery_no, DeliveryOrder.deleted_at.is_(None))
            .first()
        )
        if existing_by_no is not None and existing_by_no.sales_order_id != order.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery note number already belongs to another order.")
    else:
        existing_by_no = None

    delivery = _active_delivery_for_order(db, order.id) or existing_by_no
    if delivery is None:
        delivery = DeliveryOrder(
            delivery_no=delivery_no or generate_number("DO"),
            sales_order_id=order.id,
            customer_id=order.customer_id,
            address=address or customer.address or "",
            delivery_time=delivery_time or datetime.now(timezone.utc),
            driver_name=driver_name,
            logistics_no=logistics_no,
            status="draft",
            remark=remark,
            items=[
                DeliveryOrderItem(
                    sales_order_item_id=item.id,
                    product_name=item.product_name,
                    specification=item.specification,
                    quantity=item.quantity,
                    unit=item.unit,
                )
                for item in order.items
            ],
        )
        db.add(delivery)
        db.flush()
        return delivery

    if delivery_no and delivery.delivery_no != delivery_no:
        delivery.delivery_no = delivery_no
    if address:
        delivery.address = address
    if delivery_time:
        delivery.delivery_time = delivery_time
    if driver_name:
        delivery.driver_name = driver_name
    if logistics_no:
        delivery.logistics_no = logistics_no
    if remark:
        delivery.remark = remark
    return delivery


def _record_finance_bill_action(db: Session, node: OrderWorkflowNode, payload: WorkflowNodeActionRequest, current_user: User) -> dict:
    bill_no = _require_text(payload.bill_no, "Bill number")
    delivery_note_no = _require_text(payload.delivery_note_no, "Delivery note number")
    order = _workflow_sales_order(db, node.sales_order_id)
    customer = _order_customer(db, order)
    now = datetime.now(timezone.utc)
    bill_amount = Decimal(str(payload.bill_amount if payload.bill_amount is not None else order.total_amount or 0))
    order_amount = Decimal(str(order.total_amount or 0))
    can_approve_price = "finance:bill_price:approve" in current_user.permission_codes and any(
        role.code in {"admin", "boss"} for role in current_user.roles
    )
    if bill_amount != order_amount and not can_approve_price:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bill amount changes require boss/admin approval.")
    bill = (
        db.query(FinanceBill)
        .filter(FinanceBill.bill_no == bill_no, FinanceBill.deleted_at.is_(None))
        .first()
    )
    if bill is not None and bill.sales_order_id != order.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bill number already belongs to another order.")
    if bill is None:
        bill = FinanceBill(
            bill_no=bill_no,
            sales_order_id=order.id,
            customer_name=customer.name,
            amount=bill_amount,
            bill_status="released",
            printed_by=current_user.id,
            printed_at=now,
            released_by=current_user.id,
            released_at=now,
            remarks=payload.remarks,
        )
        db.add(bill)
    else:
        bill.customer_name = customer.name
        bill.amount = bill_amount if payload.bill_amount is not None else bill.amount
        bill.bill_status = "released"
        bill.printed_by = current_user.id
        bill.printed_at = bill.printed_at or now
        bill.released_by = current_user.id
        bill.released_at = now
        bill.remarks = payload.remarks or bill.remarks

    delivery = _ensure_workflow_delivery_order(
        db,
        order=order,
        delivery_no=delivery_note_no,
        remark=payload.remarks,
    )
    order.status = OrderStatus.PENDING_DELIVERY
    db.flush()
    return {
        "bill_id": str(bill.id),
        "bill_no": bill.bill_no,
        "delivery_order_id": str(delivery.id),
        "delivery_no": delivery.delivery_no,
    }


def _record_delivery_action(db: Session, node: OrderWorkflowNode, payload: WorkflowNodeActionRequest) -> dict:
    delivery_time = payload.delivery_time
    if delivery_time is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery time is required.")
    delivery_person = _require_text(payload.delivery_person, "Delivery person")
    order = _workflow_sales_order(db, node.sales_order_id)
    delivery = _ensure_workflow_delivery_order(
        db,
        order=order,
        address=_clean_text(payload.delivery_address) or None,
        delivery_time=delivery_time,
        driver_name=delivery_person,
        logistics_no=_clean_text(payload.logistics) or None,
        remark=payload.remarks,
    )
    if delivery.status not in {"draft", "shipped"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery order cannot be shipped in current status.")
    delivery.status = "shipped"
    order.status = OrderStatus.PENDING_DELIVERY
    db.flush()
    return {"delivery_order_id": str(delivery.id), "delivery_no": delivery.delivery_no, "status": delivery.status}


def _record_sign_action(db: Session, node: OrderWorkflowNode, payload: WorkflowNodeActionRequest, current_user: User) -> dict:
    signer = _require_text(payload.signer, "Signer")
    signed_at = payload.signed_at
    if signed_at is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Signed time is required.")
    order = _workflow_sales_order(db, node.sales_order_id)
    delivery = _active_delivery_for_order(db, order.id)
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery order must be created before sign-off.")
    if delivery.status not in {"draft", "shipped", "signed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Delivery order cannot be signed in current status.")

    delivery.status = "signed"
    delivery.signed_by = signer
    delivery.signed_at = signed_at
    if payload.remarks:
        delivery.remark = payload.remarks
    sign_remarks = payload.remarks
    sign_proof_no = _clean_text(payload.sign_proof_no)
    if sign_proof_no:
        sign_remarks = f"签收单号/凭证：{sign_proof_no}" + (f"；{sign_remarks}" if sign_remarks else "")

    record = (
        db.query(SignRecord)
        .filter(SignRecord.sales_order_id == order.id, SignRecord.deleted_at.is_(None))
        .order_by(SignRecord.created_at.desc())
        .first()
    )
    if record is None:
        record = SignRecord(
            delivery_order_id=delivery.id,
            sales_order_id=order.id,
            signed_by=signer,
            signed_at=signed_at,
            remarks=sign_remarks,
            created_by=current_user.id,
        )
        db.add(record)
    else:
        record.delivery_order_id = delivery.id
        record.signed_by = signer
        record.signed_at = signed_at
        record.remarks = sign_remarks or record.remarks
        record.updated_by = current_user.id
    order.status = OrderStatus.DELIVERED
    db.flush()
    return {"delivery_order_id": str(delivery.id), "sign_record_id": str(record.id), "signed_by": signer}


def _record_business_node_action(
    db: Session,
    node: OrderWorkflowNode,
    payload: WorkflowNodeActionRequest,
    current_user: User,
) -> dict | None:
    if node.node_code == "finance_bill":
        return _record_finance_bill_action(db, node, payload, current_user)
    if node.node_code == "delivery":
        return _record_delivery_action(db, node, payload)
    if node.node_code == "sign":
        return _record_sign_action(db, node, payload, current_user)
    return None


def _can_view_financial_amount(user: User) -> bool:
    roles = _role_codes(user)
    if roles & {"admin", "boss", "finance"}:
        return True
    return bool({"finance:receivable:view", "cost:view"} & set(user.permission_codes))


def _fulfillment_stage(
    bill: FinanceBill | None,
    delivery: DeliveryOrder | None,
    sign_record: SignRecord | None,
    finance_node: OrderWorkflowNode | None = None,
) -> str:
    if sign_record is not None or delivery is not None and delivery.status == "signed":
        return "signed"
    if delivery is not None and delivery.status == "shipped":
        return "shipped"
    if bill is not None and bill.bill_status == "released":
        return "released"
    if bill is not None:
        return "billing"
    if finance_node is not None and finance_node.status in {"active", "in_progress", "waiting"}:
        return "waiting_finance"
    return "production"


@router.post("/seed-default-template", response_model=WorkflowTemplateRead)
def seed_default_template(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:template:manage")),
) -> WorkflowTemplateRead:
    template = seed_default_parallel_workflow_template(db)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="seed_default_template",
        target_type="workflow_template",
        target_id=template.id,
    )
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates/default", response_model=WorkflowTemplateRead)
def read_default_template(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("workflow_v2:view")),
) -> WorkflowTemplateRead:
    return get_default_template(db)


@router.get("/tasks/my", response_model=list[WorkflowNodeRead])
def list_my_workflow_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> list[WorkflowNodeRead]:
    query = (
        db.query(OrderWorkflowNode)
        .filter(
            OrderWorkflowNode.deleted_at.is_(None),
            OrderWorkflowNode.status.in_(("active", "in_progress", "waiting")),
        )
        .order_by(OrderWorkflowNode.sort_order.asc(), OrderWorkflowNode.created_at.asc())
    )
    nodes = query.all()
    if _is_workflow_manager(current_user):
        return nodes
    return [node for node in nodes if _can_operate_node(current_user, node)]


@router.get("/pre-orders", response_model=PageResponse[PreOrderRead])
def list_pre_orders(
    status_filter: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> PageResponse[PreOrderRead]:
    if not _can_browse_pre_orders(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to pre-orders.")

    query = db.query(PreOrder).filter(PreOrder.deleted_at.is_(None))
    if not (
        _is_workflow_manager(current_user)
        or "workflow_v2:pre_order:confirm" in current_user.permission_codes
        or "workflow_v2:order:create" in current_user.permission_codes
    ):
        query = query.filter(PreOrder.salesperson_id == current_user.id)
    if status_filter:
        query = query.filter(PreOrder.status == status_filter)
    if keyword:
        keyword_text = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                PreOrder.pre_order_no.ilike(keyword_text),
                PreOrder.sample_no.ilike(keyword_text),
                PreOrder.customer_name.ilike(keyword_text),
                PreOrder.product_name.ilike(keyword_text),
            )
        )

    total = query.count()
    items = query.order_by(PreOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PageResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/pre-orders", response_model=PreOrderRead)
def create_pre_order(
    payload: PreOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:pre_order:create")),
) -> PreOrderRead:
    pre_order = PreOrder(
        pre_order_no=generate_number("PRE"),
        sample_no=payload.sample_no,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        product_name=payload.product_name,
        type=payload.type,
        order_time=payload.order_time or datetime.now(timezone.utc),
        salesperson_id=payload.salesperson_id or current_user.id,
        num=payload.num,
        receiver_id=payload.receiver_id,
        print_color=payload.print_color,
        remarks=payload.remarks,
        status="submitted",
        created_by=current_user.id,
    )
    db.add(pre_order)
    db.flush()
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="create_pre_order",
        target_type="pre_order",
        target_id=pre_order.id,
        after_data={"pre_order_no": pre_order.pre_order_no, "sample_no": pre_order.sample_no},
    )
    db.commit()
    db.refresh(pre_order)
    return pre_order


@router.post("/pre-orders/{pre_order_id}/approve-customer", response_model=PreOrderRead)
def approve_pre_order_customer(
    pre_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:pre_order:confirm")),
) -> PreOrderRead:
    pre_order = db.get(PreOrder, pre_order_id)
    if pre_order is None or pre_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pre-order not found.")
    if pre_order.status in {"converted", "cancelled"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pre-order cannot be approved from current status.")
    before = {"status": pre_order.status}
    pre_order.status = "customer_approved"
    pre_order.customer_confirmed_at = datetime.now(timezone.utc)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="approve_pre_order_customer",
        target_type="pre_order",
        target_id=pre_order.id,
        before_data=before,
        after_data={"status": pre_order.status},
    )
    db.commit()
    db.refresh(pre_order)
    return pre_order


@router.post("/pre-orders/{pre_order_id}/reject-customer", response_model=PreOrderRead)
def reject_pre_order_customer(
    pre_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:pre_order:confirm")),
) -> PreOrderRead:
    pre_order = db.get(PreOrder, pre_order_id)
    if pre_order is None or pre_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pre-order not found.")
    before = {"status": pre_order.status}
    pre_order.status = "customer_rejected"
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="reject_pre_order_customer",
        target_type="pre_order",
        target_id=pre_order.id,
        before_data=before,
        after_data={"status": pre_order.status},
    )
    db.commit()
    db.refresh(pre_order)
    return pre_order


@router.post("/pre-orders/{pre_order_id}/convert", response_model=dict)
def convert_pre_order(
    pre_order_id: UUID,
    payload: ConvertPreOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:order:create")),
) -> dict:
    pre_order = db.get(PreOrder, pre_order_id)
    if pre_order is None or pre_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pre-order not found.")
    if pre_order.status != "customer_approved":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Customer must approve before conversion.")
    if pre_order.converted_order_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Pre-order already converted.")

    customer_id = payload.customer_id or pre_order.customer_id
    if customer_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="customer_id is required to convert pre-order.")
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    amount = payload.unit_price * float(pre_order.num)
    order = SalesOrder(
        order_no=generate_number("SO"),
        customer_id=customer.id,
        product_summary=pre_order.product_name,
        order_date=pre_order.order_time.date(),
        due_date=payload.due_date,
        total_amount=amount,
        status="confirmed",
        priority=payload.priority,
        route_id=payload.route_id,
        plate_details={
            "source_pre_order_id": str(pre_order.id),
            "sample_no": pre_order.sample_no,
            "customer_text": pre_order.customer_name,
            "product_name": pre_order.product_name,
            "type": pre_order.type,
            "print_color": pre_order.print_color,
            "receiver_id": str(pre_order.receiver_id) if pre_order.receiver_id else None,
        },
        color_rows=[],
        remark=pre_order.remarks,
        created_by=current_user.id,
    )
    order.items.append(
        SalesOrderItem(
            product_name=pre_order.product_name,
            specification=pre_order.type,
            quantity=pre_order.num,
            unit="set",
            unit_price=payload.unit_price,
            amount=amount,
            route_id=payload.route_id,
        )
    )
    db.add(order)
    db.flush()
    pre_order.status = "converted"
    pre_order.converted_order_id = order.id
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="convert_pre_order",
        target_type="pre_order",
        target_id=pre_order.id,
        after_data={"sales_order_id": str(order.id), "order_no": order.order_no},
    )
    db.commit()
    return {"sales_order_id": order.id, "order_no": order.order_no}


@router.post("/sales-orders/{sales_order_id}/start", response_model=WorkflowGraphRead)
def start_order_workflow(
    sales_order_id: UUID,
    payload: WorkflowStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:start")),
) -> WorkflowGraphRead:
    sales_order = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.id == sales_order_id, SalesOrder.deleted_at.is_(None))
        .first()
    )
    if sales_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    workflow = start_workflow_for_order(db, sales_order, payload.template_id)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="start_workflow",
        target_type="sales_order",
        target_id=sales_order.id,
        after_data={"workflow_id": str(workflow.id)},
    )
    db.commit()
    return _workflow_graph(db, sales_order_id)


@router.get("/sales-orders/{sales_order_id}/graph", response_model=WorkflowGraphRead)
def read_order_workflow_graph(
    sales_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> WorkflowGraphRead:
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    return _workflow_graph(db, sales_order_id)


@router.get("/sales-orders/{sales_order_id}/fulfillment-summary", response_model=WorkflowFulfillmentSummary)
def read_fulfillment_summary(
    sales_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> WorkflowFulfillmentSummary:
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    bill = (
        db.query(FinanceBill)
        .filter(FinanceBill.sales_order_id == sales_order_id, FinanceBill.deleted_at.is_(None))
        .order_by(FinanceBill.created_at.desc())
        .first()
    )
    delivery = _active_delivery_for_order(db, sales_order_id)
    sign_record = (
        db.query(SignRecord)
        .filter(SignRecord.sales_order_id == sales_order_id, SignRecord.deleted_at.is_(None))
        .order_by(SignRecord.created_at.desc())
        .first()
    )
    finance_node = (
        db.query(OrderWorkflowNode)
        .filter(
            OrderWorkflowNode.sales_order_id == sales_order_id,
            OrderWorkflowNode.node_code == "finance_bill",
            OrderWorkflowNode.deleted_at.is_(None),
        )
        .first()
    )
    can_view_amount = _can_view_financial_amount(current_user)
    return WorkflowFulfillmentSummary(
        sales_order_id=sales_order_id,
        bill=(
            WorkflowFinanceBillSummary(
                id=bill.id,
                bill_no=bill.bill_no,
                amount=float(bill.amount) if can_view_amount else None,
                bill_status=bill.bill_status,
                printed_at=bill.printed_at,
                released_at=bill.released_at,
                remarks=bill.remarks,
            )
            if bill
            else None
        ),
        delivery=(
            WorkflowDeliverySummary(
                id=delivery.id,
                delivery_no=delivery.delivery_no,
                status=delivery.status,
                address=delivery.address,
                delivery_time=delivery.delivery_time,
                driver_name=delivery.driver_name,
                logistics_no=delivery.logistics_no,
                signed_by=delivery.signed_by,
                signed_at=delivery.signed_at,
                remark=delivery.remark,
            )
            if delivery
            else None
        ),
        sign=(
            WorkflowSignSummary(
                id=sign_record.id,
                signed_by=sign_record.signed_by,
                signed_at=sign_record.signed_at,
                remarks=sign_record.remarks,
            )
            if sign_record
            else None
        ),
        current_stage=_fulfillment_stage(bill, delivery, sign_record, finance_node),
        can_view_amount=can_view_amount,
    )


@router.post("/nodes/{node_id}/start", response_model=WorkflowNodeRead)
def start_workflow_node(
    node_id: UUID,
    payload: WorkflowNodeActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:operate")),
) -> WorkflowNodeRead:
    node = db.get(OrderWorkflowNode, node_id)
    if node is None or node.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow node not found.")
    _ensure_can_operate_node(current_user, node)
    node = start_node(db, node, assigned_user_id=payload.assigned_user_id or current_user.id, remarks=payload.remarks)
    log_operation(db, user_id=current_user.id, module="workflow_v2", action="start_node", target_type="workflow_node", target_id=node.id)
    db.commit()
    db.refresh(node)
    return node


@router.post("/nodes/{node_id}/complete", response_model=WorkflowNodeRead)
def complete_workflow_node(
    node_id: UUID,
    payload: WorkflowNodeActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:operate")),
) -> WorkflowNodeRead:
    node = db.get(OrderWorkflowNode, node_id)
    if node is None or node.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow node not found.")
    _ensure_can_operate_node(current_user, node)
    business_action = _record_business_node_action(db, node, payload, current_user)
    node = complete_node(db, node, remarks=payload.remarks)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="complete_node",
        target_type="workflow_node",
        target_id=node.id,
        after_data={"node_code": node.node_code, "business_action": business_action} if business_action else {"node_code": node.node_code},
    )
    db.commit()
    db.refresh(node)
    return node


@router.get("/sales-orders/{sales_order_id}/check-join", response_model=JoinCheckRead)
def read_join_check(
    sales_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> JoinCheckRead:
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    result = check_join(db, sales_order_id)
    return JoinCheckRead(
        ready=result.ready,
        join_node_code=JOIN_NODE_CODE,
        waiting_for=result.waiting_for,
        epin_completed=result.epin_completed,
        copper_grind_completed=result.copper_grind_completed,
    )


@router.get("/sales-orders/{sales_order_id}/making-assignments", response_model=list[MakingAssignmentRead])
def list_making_assignments(
    sales_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> list[MakingAssignmentRead]:
    sales_order = db.get(SalesOrder, sales_order_id)
    if sales_order is None or sales_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    query = (
        db.query(MakingAssignment)
        .filter(MakingAssignment.sales_order_id == sales_order_id, MakingAssignment.deleted_at.is_(None))
        .order_by(MakingAssignment.created_at.desc())
    )
    if not _is_workflow_manager(current_user) and "workflow_v2:making:assign" not in current_user.permission_codes:
        query = query.filter(MakingAssignment.employee_id == current_user.id)
    return query.all()


@router.post("/sales-orders/{sales_order_id}/making-assignments", response_model=list[MakingAssignmentRead])
def assign_making_work(
    sales_order_id: UUID,
    payload: MakingAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:making:assign")),
) -> list[MakingAssignmentRead]:
    sales_order = (
        db.query(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .filter(SalesOrder.id == sales_order_id, SalesOrder.deleted_at.is_(None))
        .first()
    )
    if sales_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    _ensure_assignable_making_employees(db, [item.employee_id for item in payload.assignments])
    created = create_making_assignments(
        db,
        sales_order=sales_order,
        supervisor_id=current_user.id,
        assignments=[(item.employee_id, item.assigned_sets, item.remarks) for item in payload.assignments],
        allow_over_assign=payload.allow_over_assign and "workflow_v2:making:override" in current_user.permission_codes,
    )
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="assign_making_work",
        target_type="sales_order",
        target_id=sales_order.id,
        after_data={"assignment_count": len(created)},
    )
    db.commit()
    return created


@router.post("/making-assignments/{assignment_id}/complete", response_model=MakingAssignmentRead)
def complete_making_work(
    assignment_id: UUID,
    payload: MakingCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MakingAssignmentRead:
    assignment = db.get(MakingAssignment, assignment_id)
    if assignment is None or assignment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Making assignment not found.")
    if assignment.employee_id != current_user.id and "workflow_v2:making:assign" not in current_user.permission_codes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    assignment = complete_making_assignment(db, assignment, payload.completed_sets, payload.remarks)
    log_operation(db, user_id=current_user.id, module="workflow_v2", action="complete_making_assignment", target_type="making_assignment", target_id=assignment.id)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/making-assignments/{assignment_id}/submit-epin", response_model=EpinBatchRead)
def submit_making_to_epin(
    assignment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EpinBatchRead:
    assignment = db.get(MakingAssignment, assignment_id)
    if assignment is None or assignment.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Making assignment not found.")
    if assignment.employee_id != current_user.id and "workflow_v2:making:assign" not in current_user.permission_codes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    batch = submit_making_assignment_to_epin(db, assignment)
    log_operation(db, user_id=current_user.id, module="workflow_v2", action="submit_making_to_epin", target_type="epin_batch", target_id=batch.id)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/sales-orders/{sales_order_id}/epin-batches", response_model=list[EpinBatchRead])
def list_epin_batches(
    sales_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> list[EpinBatchRead]:
    sales_order = db.get(SalesOrder, sales_order_id)
    if sales_order is None or sales_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    query = (
        db.query(EpinBatch)
        .filter(EpinBatch.sales_order_id == sales_order_id, EpinBatch.deleted_at.is_(None))
        .order_by(EpinBatch.created_at.desc())
    )
    if not _is_workflow_manager(current_user) and not _department_matches_user("电拼", current_user):
        query = query.filter(EpinBatch.employee_id == current_user.id)
    return query.all()


@router.post("/epin-batches/{batch_id}/receive", response_model=EpinBatchRead)
def receive_epin(
    batch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:epin:operate")),
) -> EpinBatchRead:
    batch = db.get(EpinBatch, batch_id)
    if batch is None or batch.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epin batch not found.")
    _ensure_can_operate_epin(current_user)
    batch = receive_epin_batch(db, batch, current_user.id)
    log_operation(db, user_id=current_user.id, module="workflow_v2", action="receive_epin_batch", target_type="epin_batch", target_id=batch.id)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/epin-batches/{batch_id}/complete", response_model=EpinBatchRead)
def complete_epin(
    batch_id: UUID,
    payload: WorkflowNodeActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:epin:operate")),
) -> EpinBatchRead:
    batch = db.get(EpinBatch, batch_id)
    if batch is None or batch.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Epin batch not found.")
    _ensure_can_operate_epin(current_user)
    batch = complete_epin_batch(db, batch, remarks=payload.remarks)
    log_operation(db, user_id=current_user.id, module="workflow_v2", action="complete_epin_batch", target_type="epin_batch", target_id=batch.id)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/sales-orders/{sales_order_id}/abnormal-flows", response_model=list[AbnormalFlowRead])
def list_abnormal_flows(
    sales_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:view")),
) -> list[AbnormalFlowRead]:
    sales_order = db.get(SalesOrder, sales_order_id)
    if sales_order is None or sales_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    return (
        db.query(AbnormalProcessRecord)
        .filter(
            AbnormalProcessRecord.sales_order_id == sales_order_id,
            AbnormalProcessRecord.deleted_at.is_(None),
        )
        .order_by(AbnormalProcessRecord.created_at.desc())
        .all()
    )


@router.post("/sales-orders/{sales_order_id}/abnormal-flow", response_model=AbnormalFlowRead)
def create_abnormal_flow(
    sales_order_id: UUID,
    payload: AbnormalFlowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:abnormal:create")),
) -> AbnormalFlowRead:
    sales_order = db.get(SalesOrder, sales_order_id)
    if sales_order is None or sales_order.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, sales_order_id)
    workflow = get_workflow_for_order(db, sales_order_id)
    nodes_by_code = {node.node_code: node for node in workflow.nodes}
    selected_codes = [payload.selected_start_node, *payload.selected_process_nodes]
    missing_nodes = sorted({node_code for node_code in selected_codes if node_code not in nodes_by_code})
    if missing_nodes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Workflow nodes not found: {', '.join(missing_nodes)}",
        )
    illegal_nodes = sorted(
        {
            node_code
            for node_code in selected_codes
            if node_code in FORBIDDEN_ABNORMAL_PROCESS_NODES or nodes_by_code[node_code].node_type in {"start", "end"}
        }
    )
    if illegal_nodes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nodes cannot be selected for abnormal processing: {', '.join(illegal_nodes)}",
        )
    record = AbnormalProcessRecord(
        sales_order_id=sales_order_id,
        abnormal_type=payload.abnormal_type,
        reason=payload.reason,
        selected_start_node=payload.selected_start_node,
        selected_process_nodes=payload.selected_process_nodes,
        need_inspection=payload.need_inspection,
        need_finance_bill=payload.need_finance_bill,
        need_delivery=payload.need_delivery,
        initiated_by=current_user.id,
        status="pending_approval",
        created_by=current_user.id,
    )
    db.add(record)
    db.flush()
    log_operation(db, user_id=current_user.id, module="workflow_v2", action="create_abnormal_flow", target_type="abnormal_process", target_id=record.id)
    db.commit()
    db.refresh(record)
    return record


@router.post("/abnormal-flows/{record_id}/approve", response_model=AbnormalFlowRead)
def approve_abnormal_flow(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:abnormal:approve")),
) -> AbnormalFlowRead:
    record = db.get(AbnormalProcessRecord, record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abnormal record not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, record.sales_order_id)
    record = approve_abnormal_process_record(db, record, current_user.id)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="approve_abnormal_flow",
        target_type="abnormal_process",
        target_id=record.id,
        after_data={"status": record.status, "selected_process_nodes": record.selected_process_nodes},
    )
    db.commit()
    db.refresh(record)
    return record


@router.post("/abnormal-flows/{record_id}/reject", response_model=AbnormalFlowRead)
def reject_abnormal_flow(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:abnormal:approve")),
) -> AbnormalFlowRead:
    record = db.get(AbnormalProcessRecord, record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abnormal record not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, record.sales_order_id)
    record = reject_abnormal_process_record(db, record, current_user.id)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="reject_abnormal_flow",
        target_type="abnormal_process",
        target_id=record.id,
        after_data={"status": record.status},
    )
    db.commit()
    db.refresh(record)
    return record


@router.post("/abnormal-flows/{record_id}/complete", response_model=AbnormalFlowRead)
def complete_abnormal_flow(
    record_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("workflow_v2:abnormal:approve")),
) -> AbnormalFlowRead:
    record = db.get(AbnormalProcessRecord, record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abnormal record not found.")
    _ensure_can_view_sales_order_workflow(db, current_user, record.sales_order_id)
    record = complete_abnormal_process_record(db, record)
    log_operation(
        db,
        user_id=current_user.id,
        module="workflow_v2",
        action="complete_abnormal_flow",
        target_type="abnormal_process",
        target_id=record.id,
        after_data={"status": record.status},
    )
    db.commit()
    db.refresh(record)
    return record


def _workflow_graph(db: Session, sales_order_id: UUID) -> WorkflowGraphRead:
    workflow = get_workflow_for_order(db, sales_order_id)
    template_nodes = {node.id: node.node_code for node in workflow.template.nodes}
    edges = [
        WorkflowEdgeGraphRead(
            from_node_code=template_nodes.get(edge.from_node_id, ""),
            to_node_code=template_nodes.get(edge.to_node_id, ""),
            condition_type=edge.condition_type,
            condition_expression=edge.condition_expression,
        )
        for edge in workflow.template.edges
    ]
    return WorkflowGraphRead(
        workflow_id=workflow.id,
        sales_order_id=workflow.sales_order_id,
        template_id=workflow.template_id,
        status=workflow.status,
        started_at=workflow.started_at,
        completed_at=workflow.completed_at,
        nodes=[WorkflowNodeRead.model_validate(node) for node in workflow.nodes],
        edges=edges,
    )
