"""add partial unique index on device_sessions (user_id, device_id)

Revision ID: a7b2c3d4e5f6
Revises: 57c1a8c30112
Create Date: 2026-05-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a7b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '57c1a8c30112'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_device_sessions_user_device", table_name="device_sessions")

    op.execute(
        "CREATE UNIQUE INDEX uq_device_sessions_user_device_active "
        "ON device_sessions (user_id, device_id) WHERE is_revoked = 0"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_device_sessions_user_device_active")

    op.create_index(
        "ix_device_sessions_user_device",
        "device_sessions",
        ["user_id", "device_id"],
    )
