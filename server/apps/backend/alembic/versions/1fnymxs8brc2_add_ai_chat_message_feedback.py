"""add ai_chat_message_feedback table

Revision ID: 1fnymxs8brc2
Revises: e4e455e0567e
Create Date: 2026-07-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1fnymxs8brc2"
down_revision: Union[str, None] = "e4e455e0567e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_chat_message_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "family_id",
            sa.BigInteger(),
            sa.ForeignKey("families.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("feedback", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "family_id",
            "thread_id",
            "message_id",
            "user_id",
            name="uq_feedback_family_thread_msg_user",
        ),
    )
    op.create_index(
        "ix_ai_chat_message_feedback_family_id",
        "ai_chat_message_feedback",
        ["family_id"],
    )
    op.create_index(
        "ix_ai_chat_message_feedback_user_id",
        "ai_chat_message_feedback",
        ["user_id"],
    )
    op.create_index(
        "ix_ai_chat_message_feedback_thread_id",
        "ai_chat_message_feedback",
        ["thread_id"],
    )
    op.create_index(
        "ix_ai_chat_message_feedback_message_id",
        "ai_chat_message_feedback",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_chat_message_feedback_message_id",
        table_name="ai_chat_message_feedback",
    )
    op.drop_index(
        "ix_ai_chat_message_feedback_thread_id",
        table_name="ai_chat_message_feedback",
    )
    op.drop_index(
        "ix_ai_chat_message_feedback_user_id",
        table_name="ai_chat_message_feedback",
    )
    op.drop_index(
        "ix_ai_chat_message_feedback_family_id",
        table_name="ai_chat_message_feedback",
    )
    op.drop_table("ai_chat_message_feedback")
