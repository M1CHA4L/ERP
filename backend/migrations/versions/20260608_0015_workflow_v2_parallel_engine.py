"""Add v2 parallel workflow engine

Revision ID: 20260608_0015
Revises: 20260606_0014
Create Date: 2026-06-08 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260608_0015"
down_revision: str | None = "20260606_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _table_exists("pre_orders"):
        op.create_table(
            "pre_orders",
            _uuid_pk(),
            sa.Column("pre_order_no", sa.String(length=64), nullable=False),
            sa.Column("sample_no", sa.String(length=64), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True),
            sa.Column("customer_name", sa.String(length=128), nullable=False),
            sa.Column("product_name", sa.String(length=128), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=True),
            sa.Column("order_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("salesperson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("num", sa.Numeric(18, 3), nullable=False),
            sa.Column("receiver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("print_color", sa.String(length=128), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("customer_confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("converted_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("pre_order_no", name="uq_pre_orders_pre_order_no"),
        )
        _create_index_if_missing("ix_pre_orders_sample_no", "pre_orders", ["sample_no"])
        _create_index_if_missing("ix_pre_orders_status", "pre_orders", ["status"])

    if not _table_exists("workflow_templates"):
        op.create_table(
            "workflow_templates",
            _uuid_pk(),
            sa.Column("template_code", sa.String(length=64), nullable=False),
            sa.Column("template_name", sa.String(length=128), nullable=False),
            sa.Column("template_type", sa.String(length=32), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            *_timestamps(),
            sa.UniqueConstraint("template_code", name="uq_workflow_templates_template_code"),
        )
        _create_index_if_missing("ix_workflow_templates_type_default_active", "workflow_templates", ["template_type", "is_default", "is_active"])

    if not _table_exists("workflow_nodes"):
        op.create_table(
            "workflow_nodes",
            _uuid_pk(),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("node_code", sa.String(length=64), nullable=False),
            sa.Column("node_name", sa.String(length=128), nullable=False),
            sa.Column("department", sa.String(length=64), nullable=True),
            sa.Column("node_type", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("branch_code", sa.String(length=64), nullable=True),
            sa.Column("is_parallel_node", sa.Boolean(), nullable=False),
            sa.Column("is_join_node", sa.Boolean(), nullable=False),
            sa.Column("is_required", sa.Boolean(), nullable=False),
            sa.Column("allow_skip", sa.Boolean(), nullable=False),
            sa.Column("required_permission", sa.String(length=128), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("template_id", "node_code", name="uq_workflow_node_template_code"),
        )
        _create_index_if_missing("ix_workflow_nodes_template_id", "workflow_nodes", ["template_id"])
        _create_index_if_missing("ix_workflow_nodes_department", "workflow_nodes", ["department"])

    if not _table_exists("workflow_edges"):
        op.create_table(
            "workflow_edges",
            _uuid_pk(),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("to_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("condition_type", sa.String(length=32), nullable=False),
            sa.Column("condition_expression", sa.Text(), nullable=True),
            *_timestamps(),
        )
        _create_index_if_missing("ix_workflow_edges_template_id", "workflow_edges", ["template_id"])
        _create_index_if_missing("ix_workflow_edges_from_node_id", "workflow_edges", ["from_node_id"])
        _create_index_if_missing("ix_workflow_edges_to_node_id", "workflow_edges", ["to_node_id"])

    if not _table_exists("order_workflows"):
        op.create_table(
            "order_workflows",
            _uuid_pk(),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_templates.id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("sales_order_id", name="uq_order_workflows_sales_order_id"),
        )
        _create_index_if_missing("ix_order_workflows_status", "order_workflows", ["status"])

    if not _table_exists("order_workflow_nodes"):
        op.create_table(
            "order_workflow_nodes",
            _uuid_pk(),
            sa.Column("order_workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_workflows.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_nodes.id"), nullable=False),
            sa.Column("node_code", sa.String(length=64), nullable=False),
            sa.Column("node_name", sa.String(length=128), nullable=False),
            sa.Column("department", sa.String(length=64), nullable=True),
            sa.Column("node_type", sa.String(length=32), nullable=False),
            sa.Column("branch_code", sa.String(length=64), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("waiting_reason", sa.Text(), nullable=True),
            sa.Column("is_current", sa.Boolean(), nullable=False),
            sa.Column("remarks", sa.Text(), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("order_workflow_id", "node_code", name="uq_order_workflow_node_code"),
        )
        _create_index_if_missing("ix_order_workflow_nodes_order_status", "order_workflow_nodes", ["sales_order_id", "status"])
        _create_index_if_missing("ix_order_workflow_nodes_current", "order_workflow_nodes", ["is_current"])

    if not _table_exists("production_tasks"):
        op.create_table(
            "production_tasks",
            _uuid_pk(),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("workflow_node_instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_workflow_nodes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("department", sa.String(length=64), nullable=True),
            sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("task_status", sa.String(length=32), nullable=False),
            sa.Column("planned_num", sa.Numeric(18, 3), nullable=False),
            sa.Column("completed_num", sa.Numeric(18, 3), nullable=False),
            sa.Column("bad_num", sa.Numeric(18, 3), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            *_timestamps(),
        )
        _create_index_if_missing("ix_production_tasks_dept_status", "production_tasks", ["department", "task_status"])

    if not _table_exists("making_assignments"):
        op.create_table(
            "making_assignments",
            _uuid_pk(),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("making_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("production_tasks.id"), nullable=True),
            sa.Column("supervisor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("assigned_sets", sa.Numeric(18, 3), nullable=False),
            sa.Column("completed_sets", sa.Numeric(18, 3), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("submitted_to_epin_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            *_timestamps(),
        )
        _create_index_if_missing("ix_making_assignments_order", "making_assignments", ["sales_order_id"])
        _create_index_if_missing("ix_making_assignments_employee_status", "making_assignments", ["employee_id", "status"])

    if not _table_exists("epin_batches"):
        op.create_table(
            "epin_batches",
            _uuid_pk(),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("making_assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("making_assignments.id"), nullable=False),
            sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("sets_count", sa.Numeric(18, 3), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("received_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            *_timestamps(),
        )
        _create_index_if_missing("ix_epin_batches_order_status", "epin_batches", ["sales_order_id", "status"])

    if not _table_exists("abnormal_process_records"):
        op.create_table(
            "abnormal_process_records",
            _uuid_pk(),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("abnormal_type", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("selected_start_node", sa.String(length=64), nullable=False),
            sa.Column("selected_process_nodes", postgresql.JSONB(), nullable=False),
            sa.Column("need_inspection", sa.Boolean(), nullable=False),
            sa.Column("need_finance_bill", sa.Boolean(), nullable=False),
            sa.Column("need_delivery", sa.Boolean(), nullable=False),
            sa.Column("initiated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            *_timestamps(),
        )
        _create_index_if_missing("ix_abnormal_process_records_order", "abnormal_process_records", ["sales_order_id"])

    if not _table_exists("finance_bills"):
        op.create_table(
            "finance_bills",
            _uuid_pk(),
            sa.Column("bill_no", sa.String(length=64), nullable=False),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("customer_name", sa.String(length=128), nullable=False),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("bill_status", sa.String(length=32), nullable=False),
            sa.Column("printed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("released_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reprint_count", sa.Integer(), nullable=False),
            sa.Column("remarks", sa.Text(), nullable=True),
            *_timestamps(),
            sa.UniqueConstraint("bill_no", name="uq_finance_bills_bill_no"),
        )
        _create_index_if_missing("ix_finance_bills_order_status", "finance_bills", ["sales_order_id", "bill_status"])

    if not _table_exists("sign_records"):
        op.create_table(
            "sign_records",
            _uuid_pk(),
            sa.Column("delivery_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("delivery_orders.id"), nullable=True),
            sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=False),
            sa.Column("signed_by", sa.String(length=128), nullable=False),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sign_image_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            *_timestamps(),
        )
        _create_index_if_missing("ix_sign_records_order", "sign_records", ["sales_order_id"])


def downgrade() -> None:
    for table_name in (
        "sign_records",
        "finance_bills",
        "abnormal_process_records",
        "epin_batches",
        "making_assignments",
        "production_tasks",
        "order_workflow_nodes",
        "order_workflows",
        "workflow_edges",
        "workflow_nodes",
        "workflow_templates",
        "pre_orders",
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)
