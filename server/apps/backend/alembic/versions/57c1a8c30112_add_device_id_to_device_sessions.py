"""add device_id to device_sessions

Revision ID: 57c1a8c30112
Revises: 1f81374239ae
Create Date: 2026-05-29 11:32:47.670409

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '57c1a8c30112'
down_revision: str | Sequence[str] | None = '1f81374239ae'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Clear stale sessions — all users will re-login and re-trust after deploy.
    op.execute("DELETE FROM device_sessions")

    op.add_column(
        "device_sessions",
        sa.Column("device_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_device_sessions_user_device",
        "device_sessions",
        ["user_id", "device_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_sessions_user_device", table_name="device_sessions")
    op.drop_column("device_sessions", "device_id")
