"""Add last_synced_at to storage_backends

Tracks when the scheduler last successfully synced files to each backend.

Revision ID: a1b2c3d4e5f7
Revises: f5g6h7i8j9k0
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f5g6h7i8j9k0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "storage_backends",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("storage_backends", "last_synced_at")
