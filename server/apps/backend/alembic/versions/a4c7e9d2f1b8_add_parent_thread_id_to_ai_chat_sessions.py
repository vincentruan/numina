"""add parent_thread_id column to ai_chat_sessions

Revision ID: a4c7e9d2f1b8
Revises: b8d9e0f1a2b3
Create Date: 2026-07-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c7e9d2f1b8"
down_revision: str | None = "b8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap creates ai_chat_sessions with parent_thread_id already.
    bind = op.get_bind()
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')} if bind.dialect.has_table(bind, 'ai_chat_sessions') else set()
    if 'parent_thread_id' not in cols:
        op.add_column(
            "ai_chat_sessions",
            sa.Column("parent_thread_id", sa.String(64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("ai_chat_sessions", "parent_thread_id")
