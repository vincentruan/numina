"""add parent_thread_id column to ai_chat_sessions

Revision ID: a4c7e9d2f1b8
Revises: b8d9e0f1a2b3
Create Date: 2026-07-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c7e9d2f1b8"
down_revision: Union[str, None] = "b8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_chat_sessions",
        sa.Column("parent_thread_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_chat_sessions", "parent_thread_id")
