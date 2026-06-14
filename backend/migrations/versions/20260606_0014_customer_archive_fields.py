"""Add customer archive fields

Revision ID: 20260606_0014
Revises: 20260605_0013
Create Date: 2026-06-06 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260606_0014"
down_revision: str | None = "20260605_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("customers", "payment_method", sa.Column("payment_method", sa.String(length=64), nullable=True))
    _add_column_if_missing("customers", "minimum_price", sa.Column("minimum_price", sa.Numeric(18, 2), nullable=True))
    _add_column_if_missing(
        "customers",
        "vat_enabled",
        sa.Column("vat_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        "customers",
        "ait_enabled",
        sa.Column("ait_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing("customers", "advance_percent", sa.Column("advance_percent", sa.Numeric(8, 2), nullable=True))
    _add_column_if_missing("customers", "lister", sa.Column("lister", sa.String(length=64), nullable=True))
    _add_column_if_missing("customers", "price_rules", sa.Column("price_rules", postgresql.JSONB(), nullable=True))
    op.alter_column("customers", "vat_enabled", server_default=None)
    op.alter_column("customers", "ait_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("customers", "price_rules")
    op.drop_column("customers", "lister")
    op.drop_column("customers", "advance_percent")
    op.drop_column("customers", "ait_enabled")
    op.drop_column("customers", "vat_enabled")
    op.drop_column("customers", "minimum_price")
    op.drop_column("customers", "payment_method")
