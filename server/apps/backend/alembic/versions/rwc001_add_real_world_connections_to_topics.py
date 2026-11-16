"""add real_world_connections columns to learning_topics

Revision ID: rwc001
Revises: 0147f812a544
Create Date: 2026-11-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "rwc001"
down_revision: str | None = "0147f812a544"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = (
        {c["name"] for c in bind.dialect.get_columns(bind, "learning_topics")}
        if bind.dialect.has_table(bind, "learning_topics")
        else set()
    )
    if "real_world_connections_json" in cols:
        return  # already present (fresh-DB bootstrap)

    op.add_column(
        "learning_topics",
        sa.Column("real_world_connections_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "learning_topics",
        sa.Column("real_world_connections_zh_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_topics", "real_world_connections_zh_json")
    op.drop_column("learning_topics", "real_world_connections_json")
