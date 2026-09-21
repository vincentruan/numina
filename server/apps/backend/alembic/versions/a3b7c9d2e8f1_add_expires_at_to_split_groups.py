"""add expires_at to split_groups

Revision ID: a3b7c9d2e8f1
Revises: 9f6897de7550
Create Date: 2026-09-21
"""

import sqlalchemy as sa

from alembic import op

revision = "a3b7c9d2e8f1"
down_revision = "9f6897de7550"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "split_groups",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("split_groups", "expires_at")
