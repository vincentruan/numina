"""add agent_id column to ai_chat_sessions

Revision ID: z4783a86brs1
Revises: fa6bcb4dcc4d
Create Date: 2026-06-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z4783a86brs1"
down_revision: Union[str, None] = "fa6bcb4dcc4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_sessions",
        sa.Column("agent_id", sa.BigInteger(), nullable=True),
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