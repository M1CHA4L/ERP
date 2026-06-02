"""Add legacy customer fields and opening receivables

Revision ID: 20260527_0003
Revises: 20260526_0002
Create Date: 2026-05-27 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260527_0003"
down_revision: str | None = "20260526_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    customer_columns = {column["name"] for column in inspector.get_columns("customers")}
    customer_additions = {
        "customer_type": sa.Column("customer_type", sa.String(length=32), nullable=True),
        "is_key_customer": sa.Column("is_key_customer", sa.Boolean(), nullable=False, server_default=sa.false()),
        "company_phone": sa.Column("company_phone", sa.String(length=32), nullable=True),
        "fax": sa.Column("fax", sa.String(length=32), nullable=True),
        "salesperson_id": sa.Column("salesperson_id", postgresql.UUID(as_uuid=True), nullable=True),
        "office": sa.Column("office", sa.String(length=64), nullable=True),
        "opening_remark": sa.Column("opening_remark", sa.Text(), nullable=True),
        "bank_name": sa.Column("bank_name", sa.String(length=128), nullable=True),
        "bank_account": sa.Column("bank_account", sa.String(length=128), nullable=True),
        "delivery_method": sa.Column("delivery_method", sa.String(length=64), nullable=True),
        "copper_thickness": sa.Column("copper_thickness", sa.Numeric(10, 2), nullable=True),
        "chrome_time": sa.Column("chrome_time", sa.Numeric(10, 2), nullable=True),
        "stripping_cost": sa.Column("stripping_cost", sa.Numeric(18, 2), nullable=True),
        "reconciliation_cycle": sa.Column("reconciliation_cycle", sa.String(length=32), nullable=True),
        "reconciliation_day": sa.Column("reconciliation_day", sa.Integer(), nullable=True),
    }
    for column_name, column in customer_additions.items():
        if column_name not in customer_columns:
            op.add_column("customers", column)

    customer_foreign_keys = inspector.get_foreign_keys("customers")
    has_salesperson_fk = any(fk.get("constrained_columns") == ["salesperson_id"] for fk in customer_foreign_keys)
    if not has_salesperson_fk:
        op.create_foreign_key("fk_customers_salesperson_id_users", "customers", "users", ["salesperson_id"], ["id"])

    receivable_columns = {column["name"] for column in inspector.get_columns("receivables")}
    if "source_type" not in receivable_columns:
        op.add_column("receivables", sa.Column("source_type", sa.String(length=32), nullable=False, server_default="delivery"))
    if "remark" not in receivable_columns:
        op.add_column("receivables", sa.Column("remark", sa.Text(), nullable=True))
    op.alter_column(
        "receivables",
        "sales_order_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    if "source_type" not in receivable_columns:
        op.alter_column("receivables", "source_type", server_default=None)


def downgrade() -> None:
    op.alter_column(
        "receivables",
        "sales_order_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("receivables", "remark")
    op.drop_column("receivables", "source_type")

    op.drop_constraint("fk_customers_salesperson_id_users", "customers", type_="foreignkey")
    op.drop_column("customers", "reconciliation_day")
    op.drop_column("customers", "reconciliation_cycle")
    op.drop_column("customers", "stripping_cost")
    op.drop_column("customers", "chrome_time")
    op.drop_column("customers", "copper_thickness")
    op.drop_column("customers", "delivery_method")
    op.drop_column("customers", "bank_account")
    op.drop_column("customers", "bank_name")
    op.drop_column("customers", "opening_remark")
    op.drop_column("customers", "office")
    op.drop_column("customers", "salesperson_id")
    op.drop_column("customers", "fax")
    op.drop_column("customers", "company_phone")
    op.drop_column("customers", "is_key_customer")
    op.drop_column("customers", "customer_type")
