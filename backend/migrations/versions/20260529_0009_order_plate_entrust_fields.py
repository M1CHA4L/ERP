"""Add plate entrust fields to sales orders

Revision ID: 20260529_0009
Revises: 20260529_0008
Create Date: 2026-05-29 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260529_0009"
down_revision: str | None = "20260529_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("sales_orders", "plate_details", sa.Column("plate_details", postgresql.JSONB(), nullable=True))
    _add_column_if_missing("sales_orders", "color_rows", sa.Column("color_rows", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_orders", "color_rows")
    op.drop_column("sales_orders", "plate_details")
