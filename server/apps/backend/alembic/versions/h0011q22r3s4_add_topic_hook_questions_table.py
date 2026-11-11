"""add topic_hook_questions table

Revision ID: h0011q22r3s4
Revises: 0147f812a544
Create Date: 2026-11-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h0011q22r3s4"
down_revision: str | None = "0147f812a544"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topic_hook_questions",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_text_zh", sa.Text(), nullable=True),
        sa.Column("age_group", sa.String(10), nullable=False, server_default="mid"),
        sa.Column("difficulty", sa.String(10), nullable=False, server_default="medium"),
        sa.Column(
            "review_status", sa.String(10), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["learning_topics.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("topic_id", "age_group", name="uq_hook_topic_age"),
    )
    op.create_index(
        "ix_topic_hook_questions_topic_id",
        "topic_hook_questions",
        ["topic_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_topic_hook_questions_topic_id", table_name="topic_hook_questions")
    op.drop_table("topic_hook_questions")
