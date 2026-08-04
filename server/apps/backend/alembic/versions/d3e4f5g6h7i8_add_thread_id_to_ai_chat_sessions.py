"""add thread_id column to ai_chat_sessions

Stores the LangGraph UUID thread_id so that sessions created via the
frontend createThread path (UUID) can be looked up in addition to
sessions created via the backend chat_stream path (Snowflake PK).

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2026-08-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5g6h7i8"
down_revision: str | None = "c2d3e4f5g6h7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if _has_column("ai_chat_sessions", "thread_id"):
        return
    with op.batch_alter_table("ai_chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("thread_id", sa.String(64), nullable=True))
        batch_op.create_index(
            op.f("ix_ai_chat_sessions_thread_id"),
            ["thread_id"],
            unique=True,
        )


def downgrade() -> None:
    if not _has_column("ai_chat_sessions", "thread_id"):
        return
    with op.batch_alter_table("ai_chat_sessions") as batch_op:
        batch_op.drop_index(op.f("ix_ai_chat_sessions_thread_id"))
        batch_op.drop_column("thread_id")
