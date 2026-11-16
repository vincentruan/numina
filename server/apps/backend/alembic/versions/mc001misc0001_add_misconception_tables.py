"""add misconceptions and misconception_detections tables

Revision ID: mc001misc0001
Revises: dc001dgns0001
Create Date: 2026-11-16

Adds the misconception catalog (Misconception model) and detection recording
(MisconceptionDetection model) for Issue #214.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "mc001misc0001"
down_revision: tuple[str, ...] = ("dc001dgns0001",)  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "misconceptions"):
        op.create_table(
            "misconceptions",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_pattern_json", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("description_zh", sa.Text(), nullable=True),
            sa.Column(
                "age_group",
                sa.String(10),
                nullable=False,
                server_default="mid",
            ),
            sa.Column("diagnostic_question_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "review_status",
                sa.String(20),
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
            sa.ForeignKeyConstraint(
                ["diagnostic_question_id"],
                ["questions.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "topic_id", "age_group", "sequence",
                name="uq_misconception_topic_age_seq",
            ),
        )
        op.create_index(
            "ix_misconceptions_topic_id",
            "misconceptions",
            ["topic_id"],
            unique=False,
        )

    if not bind.dialect.has_table(bind, "misconception_detections"):
        op.create_table(
            "misconception_detections",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), nullable=False),
            sa.Column("misconception_id", sa.BigInteger(), nullable=False),
            sa.Column("question_id", sa.BigInteger(), nullable=False),
            sa.Column("wrong_answer_json", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["child_id"],
                ["users.id"],
            ),
            sa.ForeignKeyConstraint(
                ["topic_id"],
                ["learning_topics.id"],
            ),
            sa.ForeignKeyConstraint(
                ["misconception_id"],
                ["misconceptions.id"],
            ),
            sa.ForeignKeyConstraint(
                ["question_id"],
                ["questions.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_misconception_detections_child_id",
            "misconception_detections",
            ["child_id"],
            unique=False,
        )
        op.create_index(
            "ix_misconception_detections_topic_id",
            "misconception_detections",
            ["topic_id"],
            unique=False,
        )
        op.create_index(
            "ix_misconception_detections_misconception_id",
            "misconception_detections",
            ["misconception_id"],
            unique=False,
        )
        op.create_index(
            "ix_misconception_detections_question_id",
            "misconception_detections",
            ["question_id"],
            unique=False,
        )
        op.create_index(
            "ix_misconception_detection_child_topic_created",
            "misconception_detections",
            ["child_id", "topic_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.has_table(bind, "misconception_detections"):
        op.drop_index(
            "ix_misconception_detection_child_topic_created",
            table_name="misconception_detections",
        )
        op.drop_index(
            "ix_misconception_detections_question_id",
            table_name="misconception_detections",
        )
        op.drop_index(
            "ix_misconception_detections_misconception_id",
            table_name="misconception_detections",
        )
        op.drop_index(
            "ix_misconception_detections_topic_id",
            table_name="misconception_detections",
        )
        op.drop_index(
            "ix_misconception_detections_child_id",
            table_name="misconception_detections",
        )
        op.drop_table("misconception_detections")

    if bind.dialect.has_table(bind, "misconceptions"):
        op.drop_index(
            "ix_misconceptions_topic_id",
            table_name="misconceptions",
        )
        op.drop_table("misconceptions")
