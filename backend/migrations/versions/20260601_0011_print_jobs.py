"""Add print job audit table

Revision ID: 20260601_0011
Revises: 20260529_0010
Create Date: 2026-06-01 00:00:00
"""
from collections.abc import Sequence

from alembic import op

from app.db.base import Base

revision: str = "20260601_0011"
down_revision: str | None = "20260529_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.tables["print_jobs"].drop(bind=op.get_bind(), checkfirst=True)
