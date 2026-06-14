"""Add plate number reservations

Revision ID: 20260605_0013
Revises: 20260603_0012
Create Date: 2026-06-05 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260605_0013"
down_revision: str | None = "20260603_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    indexes.update(item["name"] for item in inspector.get_unique_constraints(table_name))
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "plate_number_reservations" not in inspector.get_table_names():
        op.create_table(
            "plate_number_reservations",
            sa.Column("plate_no", sa.String(length=64), nullable=False),
            sa.Column("prefix", sa.String(length=4), nullable=False),
            sa.Column("year_month", sa.String(length=6), nullable=False),
            sa.Column("sequence_no", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("assigned_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("used_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=True),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_plate_no", ["plate_no"], unique=True)
    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_prefix", ["prefix"])
    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_year_month", ["year_month"])
    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_sequence_no", ["sequence_no"])
    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_status", ["status"])
    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_assigned_user_id", ["assigned_user_id"])
    _create_index_if_missing("plate_number_reservations", "ix_plate_number_reservations_used_order_id", ["used_order_id"])


def downgrade() -> None:
    op.drop_table("plate_number_reservations")
