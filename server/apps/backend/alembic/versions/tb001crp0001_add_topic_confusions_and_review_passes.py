"""add topic_confusions table + consecutive_review_passes column (teach-back)

Revision ID: tb001crp0001
Revises: h0011q22r3s4, rwc001
Create Date: 2026-11-12

Merges the two existing heads (h0011q22r3s4 and rwc001) and adds:
- topic_confusions table for preset teach-back misconceptions
- consecutive_review_passes column on learning_progress
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "tb001crp0001"
down_revision: tuple[str, ...] = ("h0011q22r3s4", "rwc001")  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # -- topic_confusions table --
    if not bind.dialect.has_table(bind, "topic_confusions"):
        op.create_table(
            "topic_confusions",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("confusion_text", sa.Text(), nullable=False),
            sa.Column("confusion_text_zh", sa.Text(), nullable=True),
            sa.Column(
                "age_group", sa.String(10), nullable=False, server_default="mid"
            ),
            sa.Column("rubric", sa.Text(), nullable=False),
            sa.Column("expected_expression", sa.Text(), nullable=True),
            sa.Column(
                "review_status",
                sa.String(10),
                nullable=False,
                server_default="pending",
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
            sa.UniqueConstraint(
                "topic_id",
                "age_group",
                "sequence",
                name="uq_confusion_topic_age_seq",
            ),
        )
        op.create_index(
            "ix_topic_confusions_topic_id",
            "topic_confusions",
            ["topic_id"],
            unique=False,
        )

    # -- consecutive_review_passes column on learning_progress --
    if bind.dialect.has_table(bind, "learning_progress"):
        cols = {
            c["name"] for c in bind.dialect.get_columns(bind, "learning_progress")
        }
        if "consecutive_review_passes" not in cols:
            op.add_column(
                "learning_progress",
                sa.Column(
                    "consecutive_review_passes",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.has_table(bind, "learning_progress"):
        cols = {
            c["name"] for c in bind.dialect.get_columns(bind, "learning_progress")
        }
        if "consecutive_review_passes" in cols:
            op.drop_column(
                "learning_progress", "consecutive_review_passes"
            )

    if bind.dialect.has_table(bind, "topic_confusions"):
        op.drop_index(
            "ix_topic_confusions_topic_id", table_name="topic_confusions"
        )
        op.drop_table("topic_confusions")
