"""Add legacy customer identifiers

Revision ID: 20260528_0004
Revises: 20260527_0003
Create Date: 2026-05-28 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0004"
down_revision: str | None = "20260527_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    customer_columns = {column["name"] for column in inspector.get_columns("customers")}
    if "legacy_company_id" not in customer_columns:
        op.add_column("customers", sa.Column("legacy_company_id", sa.String(length=32), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("customers")}
    if "ix_customers_legacy_company_id" not in indexes:
        op.create_index("ix_customers_legacy_company_id", "customers", ["legacy_company_id"])


def downgrade() -> None:
    op.drop_index("ix_customers_legacy_company_id", table_name="customers")
    op.drop_column("customers", "legacy_company_id")
