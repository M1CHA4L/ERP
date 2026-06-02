"""Add user device binding and order visibility controls

Revision ID: 20260529_0008
Revises: 20260528_0007
Create Date: 2026-05-29 00:00:00
"""
from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260529_0008"
down_revision: str | None = "20260528_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_PERMISSIONS = (
    ("order:history:view", "View historical orders", "action", 200),
    ("order:plate_detail:view", "View plate details", "action", 201),
)
ROLE_PERMISSION_CODES = {
    "admin": ("order:history:view", "order:plate_detail:view"),
    "boss": ("order:history:view", "order:plate_detail:view"),
    "sales": ("order:history:view", "order:plate_detail:view"),
    "production_manager": ("order:history:view", "order:plate_detail:view"),
}


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def _seed_permissions() -> None:
    bind = op.get_bind()
    permission_ids: dict[str, str] = {}
    for code, name, permission_type, sort_no in NEW_PERMISSIONS:
        existing = bind.execute(sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}).scalar()
        if existing:
            permission_ids[code] = str(existing)
            continue
        permission_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, name, type, sort_no)
                VALUES (:id, :code, :name, :type, :sort_no)
                """
            ),
            {"id": permission_id, "code": code, "name": name, "type": permission_type, "sort_no": sort_no},
        )
        permission_ids[code] = permission_id

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role_id = bind.execute(sa.text("SELECT id FROM roles WHERE code = :code"), {"code": role_code}).scalar()
        if not role_id:
            continue
        for permission_code in permission_codes:
            permission_id = permission_ids.get(permission_code)
            if not permission_id:
                continue
            exists = bind.execute(
                sa.text(
                    """
                    SELECT 1 FROM role_permissions
                    WHERE role_id = :role_id AND permission_id = :permission_id
                    """
                ),
                {"role_id": role_id, "permission_id": permission_id},
            ).first()
            if not exists:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (:role_id, :permission_id)
                        """
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )


def upgrade() -> None:
    _add_column_if_missing("users", "device_mac_address", sa.Column("device_mac_address", sa.String(length=128), nullable=True))
    _add_column_if_missing("users", "device_bound_at", sa.Column("device_bound_at", sa.DateTime(timezone=True), nullable=True))
    _create_index_if_missing("users", "ix_users_device_mac_address", ["device_mac_address"])

    _add_column_if_missing(
        "sales_orders",
        "rework_source_order_id",
        sa.Column("rework_source_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=True),
    )
    _add_column_if_missing(
        "sales_orders",
        "rework_source_work_order_id",
        sa.Column("rework_source_work_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_orders.id"), nullable=True),
    )
    _add_column_if_missing(
        "sales_orders",
        "rework_source_inspection_id",
        sa.Column("rework_source_inspection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_records.id"), nullable=True),
    )
    _create_index_if_missing("sales_orders", "ix_sales_orders_rework_source_order_id", ["rework_source_order_id"])

    _add_column_if_missing(
        "rework_records",
        "rework_sales_order_id",
        sa.Column("rework_sales_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_orders.id"), nullable=True),
    )
    _create_index_if_missing("rework_records", "ix_rework_records_rework_sales_order_id", ["rework_sales_order_id"])

    _seed_permissions()


def downgrade() -> None:
    bind = op.get_bind()
    permission_ids = [
        str(item[0])
        for item in bind.execute(
            sa.text("SELECT id FROM permissions WHERE code IN ('order:history:view', 'order:plate_detail:view')")
        ).all()
    ]
    for permission_id in permission_ids:
        bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :permission_id"), {"permission_id": permission_id})
    bind.execute(sa.text("DELETE FROM permissions WHERE code IN ('order:history:view', 'order:plate_detail:view')"))

    op.drop_index("ix_rework_records_rework_sales_order_id", table_name="rework_records")
    op.drop_column("rework_records", "rework_sales_order_id")
    op.drop_index("ix_sales_orders_rework_source_order_id", table_name="sales_orders")
    op.drop_column("sales_orders", "rework_source_inspection_id")
    op.drop_column("sales_orders", "rework_source_work_order_id")
    op.drop_column("sales_orders", "rework_source_order_id")
    op.drop_index("ix_users_device_mac_address", table_name="users")
    op.drop_column("users", "device_bound_at")
    op.drop_column("users", "device_mac_address")
