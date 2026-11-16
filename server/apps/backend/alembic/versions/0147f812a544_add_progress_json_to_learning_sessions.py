"""add_progress_json_to_learning_sessions

Revision ID: 0147f812a544
Revises: st0101sched0
Create Date: 2026-11-05 01:55:37.322947

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0147f812a544'
down_revision: str | None = 'st0101sched0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_sessions",
        sa.Column("progress_json", sa.Text(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("learning_sessions", "progress_json")
