"""add agent_id column to ai_chat_sessions

Revision ID: z4783a86brs1
Revises: fa6bcb4dcc4d
Create Date: 2026-06-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z4783a86brs1"
down_revision: str | None = "fa6bcb4dcc4d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap creates ai_chat_sessions.agent_id (without FK, since
    # ai_agents didn't exist at bootstrap time). ai_agents now exists (created by
    # x2581y64zqr9 which runs before this). Skip add_column when agent_id exists;
    # the FK is omitted on fresh DB (acceptable — column is nullable, app enforces).
    bind = op.get_bind()
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_chat_sessions')} if bind.dialect.has_table(bind, 'ai_chat_sessions') else set()
    if 'agent_id' in cols:
        return  # column already present (fresh-DB bootstrap)
    op.add_column(
        "ai_chat_sessions",
        sa.Column("agent_id", sa.BigInteger(), sa.ForeignKey("ai_agents.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index(
        "ix_ai_chat_sessions_agent_id",
        "ai_chat_sessions",
        ["agent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_chat_sessions_agent_id", table_name="ai_chat_sessions")
    op.drop_column("ai_chat_sessions", "agent_id")