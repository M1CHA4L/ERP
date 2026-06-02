"""Add plate finance and inventory tables

Revision ID: 20260529_0010
Revises: 20260529_0009
Create Date: 2026-05-29 00:00:00
"""
from collections.abc import Sequence

from alembic import op

from app.db.base import Base

revision: str = "20260529_0010"
down_revision: str | None = "20260529_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    "receipt_allocations",
    "receipt_daily_entries",
    "monthly_payment_summaries",
    "customer_statement_runs",
    "inventory_transactions",
    "inventory_lots",
    "cylinder_stocks",
)


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for table_name in TABLES:
        Base.metadata.tables[table_name].drop(bind=op.get_bind(), checkfirst=True)
