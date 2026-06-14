"""Add entrust layout templates

Revision ID: 20260603_0012
Revises: 20260601_0011
Create Date: 2026-06-03 00:00:00
"""
from collections.abc import Sequence

from alembic import op

from app.db.base import Base

revision: str = "20260603_0012"
down_revision: str | None = "20260601_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.tables["entrust_layout_templates"].drop(bind=op.get_bind(), checkfirst=True)
