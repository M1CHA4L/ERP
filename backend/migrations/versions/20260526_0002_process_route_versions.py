"""Add process route version source

Revision ID: 20260526_0002
Revises: 20260526_0001
Create Date: 2026-05-26 14:45:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0002"
down_revision: str | None = "20260526_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("process_routes")}
    if "source_route_id" not in columns:
        op.add_column("process_routes", sa.Column("source_route_id", sa.UUID(), nullable=True))
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("process_routes")}
    if "fk_process_routes_source_route_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_process_routes_source_route_id",
            "process_routes",
            "process_routes",
            ["source_route_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("process_routes")}
    if "fk_process_routes_source_route_id" in foreign_keys:
        op.drop_constraint("fk_process_routes_source_route_id", "process_routes", type_="foreignkey")
    columns = {column["name"] for column in inspector.get_columns("process_routes")}
    if "source_route_id" in columns:
        op.drop_column("process_routes", "source_route_id")
