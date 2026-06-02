"""Add legacy delivery identifiers

Revision ID: 20260528_0007
Revises: 20260528_0006
Create Date: 2026-05-28 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0007"
down_revision: str | None = "20260528_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    delivery_columns = {column["name"] for column in inspector.get_columns("delivery_orders")}
    additions = {
        "legacy_order_mst_id": sa.Column("legacy_order_mst_id", sa.String(length=32), nullable=True),
        "legacy_order_mst_rid": sa.Column("legacy_order_mst_rid", sa.String(length=32), nullable=True),
        "legacy_bill_type": sa.Column("legacy_bill_type", sa.String(length=64), nullable=True),
    }
    for column_name, column in additions.items():
        if column_name not in delivery_columns:
            op.add_column("delivery_orders", column)

    indexes = {index["name"] for index in inspector.get_indexes("delivery_orders")}
    if "ix_delivery_orders_legacy_order_mst_id" not in indexes:
        op.create_index("ix_delivery_orders_legacy_order_mst_id", "delivery_orders", ["legacy_order_mst_id"])
    if "ix_delivery_orders_legacy_order_mst_rid" not in indexes:
        op.create_index("ix_delivery_orders_legacy_order_mst_rid", "delivery_orders", ["legacy_order_mst_rid"])


def downgrade() -> None:
    op.drop_index("ix_delivery_orders_legacy_order_mst_rid", table_name="delivery_orders")
    op.drop_index("ix_delivery_orders_legacy_order_mst_id", table_name="delivery_orders")
    op.drop_column("delivery_orders", "legacy_bill_type")
    op.drop_column("delivery_orders", "legacy_order_mst_rid")
    op.drop_column("delivery_orders", "legacy_order_mst_id")
