"""add source column to ai_chat_sessions

Revision ID: y3692z75arq0
Revises: x2581y64zqr9
Create Date: 2026-06-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "y3692z75arq0"
down_revision: str | None = "x2581y64zqr9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap creates ai_chat_sessions with source already.
    bind = op.get_bind()
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')} if bind.dialect.has_table(bind, 'ai_chat_sessions') else set()
    if 'source' not in cols:
        op.add_column(
            "ai_chat_sessions",
            sa.Column("source", sa.String(32), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("ai_chat_sessions", "source")
