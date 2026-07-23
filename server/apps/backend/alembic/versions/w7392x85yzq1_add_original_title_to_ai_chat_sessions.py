"""add original_title column to ai_chat_sessions

Revision ID: w7392x85yzq1
Revises: 538588b30845
Create Date: 2026-07-07

Stores the auto-generated title before the user manually renames a session,
so the original DeerFlow TitleMiddleware-produced title is never lost.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "w7392x85yzq1"
down_revision: str | None = "538588b30845"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap creates ai_chat_sessions with original_title already.
    bind = op.get_bind()
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')} if bind.dialect.has_table(bind, 'ai_chat_sessions') else set()
    if 'original_title' not in cols:
        op.add_column(
            "ai_chat_sessions",
            sa.Column("original_title", sa.String(length=256), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("ai_chat_sessions", "original_title")
