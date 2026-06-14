from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PreOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pre_orders"

    pre_order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sample_no: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(128))
    product_name: Mapped[str] = mapped_column(String(128))
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    salesperson_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    num: Mapped[float] = mapped_column(Numeric(18, 3))
    receiver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    print_color: Mapped[str | None] = mapped_column(String(128), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    customer_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), nullable=True)


class WorkflowTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_templates"

    template_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    template_name: Mapped[str] = mapped_column(String(128))
    template_type: Mapped[str] = mapped_column(String(32), default="normal", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    nodes: Mapped[list["WorkflowNode"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="WorkflowNode.sort_order",
    )
    edges: Mapped[list["WorkflowEdge"]] = relationship(back_populates="template", cascade="all, delete-orphan")


class WorkflowNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_nodes"
    __table_args__ = (UniqueConstraint("template_id", "node_code", name="uq_workflow_node_template_code"),)

    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_templates.id", ondelete="CASCADE"), index=True)
    node_code: Mapped[str] = mapped_column(String(64))
    node_name: Mapped[str] = mapped_column(String(128))
    department: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    node_type: Mapped[str] = mapped_column(String(32), default="task", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    branch_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_parallel_node: Mapped[bool] = mapped_column(Boolean, default=False)
    is_join_node: Mapped[bool] = mapped_column(Boolean, default=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_skip: Mapped[bool] = mapped_column(Boolean, default=False)
    required_permission: Mapped[str | None] = mapped_column(String(128), nullable=True)

    template: Mapped[WorkflowTemplate] = relationship(back_populates="nodes")


class WorkflowEdge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_edges"

    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_templates.id", ondelete="CASCADE"), index=True)
    from_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_nodes.id", ondelete="CASCADE"), index=True)
    to_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_nodes.id", ondelete="CASCADE"), index=True)
    condition_type: Mapped[str] = mapped_column(String(32), default="always")
    condition_expression: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped[WorkflowTemplate] = relationship(back_populates="edges")
    from_node: Mapped[WorkflowNode] = relationship(foreign_keys=[from_node_id])
    to_node: Mapped[WorkflowNode] = relationship(foreign_keys=[to_node_id])


class OrderWorkflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_workflows"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), unique=True, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_templates.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template: Mapped[WorkflowTemplate] = relationship()
    nodes: Mapped[list["OrderWorkflowNode"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="OrderWorkflowNode.sort_order",
    )


class OrderWorkflowNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_workflow_nodes"
    __table_args__ = (UniqueConstraint("order_workflow_id", "node_code", name="uq_order_workflow_node_code"),)

    order_workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("order_workflows.id", ondelete="CASCADE"), index=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_nodes.id"), index=True)
    node_code: Mapped[str] = mapped_column(String(64), index=True)
    node_name: Mapped[str] = mapped_column(String(128))
    department: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    node_type: Mapped[str] = mapped_column(String(32), default="task")
    branch_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waiting_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped[OrderWorkflow] = relationship(back_populates="nodes")
    template_node: Mapped[WorkflowNode] = relationship()


class ProductionTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "production_tasks"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    workflow_node_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_workflow_nodes.id", ondelete="CASCADE"),
        index=True,
    )
    department: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    task_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    planned_num: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    completed_num: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    bad_num: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class MakingAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "making_assignments"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    making_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("production_tasks.id"), nullable=True, index=True)
    supervisor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    assigned_sets: Mapped[float] = mapped_column(Numeric(18, 3))
    completed_sets: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    status: Mapped[str] = mapped_column(String(32), default="assigned", index=True)
    submitted_to_epin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class EpinBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "epin_batches"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    making_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("making_assignments.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    sets_count: Mapped[float] = mapped_column(Numeric(18, 3))
    status: Mapped[str] = mapped_column(String(32), default="submitted", index=True)
    received_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class AbnormalProcessRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "abnormal_process_records"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    abnormal_type: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    selected_start_node: Mapped[str] = mapped_column(String(64))
    selected_process_nodes: Mapped[list] = mapped_column(JSONB)
    need_inspection: Mapped[bool] = mapped_column(Boolean, default=True)
    need_finance_bill: Mapped[bool] = mapped_column(Boolean, default=False)
    need_delivery: Mapped[bool] = mapped_column(Boolean, default=False)
    initiated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)


class FinanceBill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "finance_bills"

    bill_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String(128))
    amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    bill_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    printed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reprint_count: Mapped[int] = mapped_column(Integer, default=0)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)


class SignRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sign_records"

    delivery_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_orders.id"), nullable=True, index=True)
    sales_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_orders.id"), index=True)
    signed_by: Mapped[str] = mapped_column(String(128))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sign_image_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
