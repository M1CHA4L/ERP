"""Add legacy sales identifiers

Revision ID: 20260528_0005
Revises: 20260528_0004
Create Date: 2026-05-28 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0005"
down_revision: str | None = "20260528_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    sales_columns = {column["name"] for column in inspector.get_columns("sales_orders")}
    if "legacy_bussiness_mst_id" not in sales_columns:
        op.add_column("sales_orders", sa.Column("legacy_bussiness_mst_id", sa.String(length=32), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("sales_orders")}
    if "ix_sales_orders_legacy_bussiness_mst_id" not in indexes:
        op.create_index("ix_sales_orders_legacy_bussiness_mst_id", "sales_orders", ["legacy_bussiness_mst_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_orders_legacy_bussiness_mst_id", table_name="sales_orders")
    op.drop_column("sales_orders", "legacy_bussiness_mst_id")
