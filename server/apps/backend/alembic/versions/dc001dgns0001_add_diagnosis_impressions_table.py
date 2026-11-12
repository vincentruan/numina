"""add diagnosis_impressions table (prerequisite backtrace diagnosis)

Revision ID: dc001dgns0001
Revises: h0011q22r3s4, rwc001
Create Date: 2026-11-12

Merges the two existing heads (h0011q22r3s4 and rwc001) and adds the
diagnosis_impressions table — one server-side record per qualified
weak-prerequisite candidate returned by a backtrace diagnosis run.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dc001dgns0001"
down_revision: tuple[str, ...] = ("h0011q22r3s4", "rwc001")  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, "diagnosis_impressions"):
        op.create_table(
            "diagnosis_impressions",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("child_id", sa.BigInteger(), nullable=False),
            sa.Column("target_topic_id", sa.BigInteger(), nullable=False),
            sa.Column("recommended_topic_id", sa.BigInteger(), nullable=False),
            sa.Column("bkt_mastery", sa.Float(), nullable=False),
            sa.Column("sample_size", sa.Integer(), nullable=False),
            sa.Column("config_version", sa.String(50), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["child_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["target_topic_id"],
                ["learning_topics.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["recommended_topic_id"],
                ["learning_topics.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_diagnosis_impressions_child_id",
            "diagnosis_impressions",
            ["child_id"],
            unique=False,
        )
        op.create_index(
            "ix_diagnosis_impressions_target_topic_id",
            "diagnosis_impressions",
            ["target_topic_id"],
            unique=False,
        )
        op.create_index(
            "ix_diagnosis_impressions_recommended_topic_id",
            "diagnosis_impressions",
            ["recommended_topic_id"],
            unique=False,
        )
        op.create_index(
            "ix_diagnosis_impression_child_created",
            "diagnosis_impressions",
            ["child_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.has_table(bind, "diagnosis_impressions"):
        op.drop_index(
            "ix_diagnosis_impression_child_created",
            table_name="diagnosis_impressions",
        )
        op.drop_index(
            "ix_diagnosis_impressions_recommended_topic_id",
            table_name="diagnosis_impressions",
        )
        op.drop_index(
            "ix_diagnosis_impressions_target_topic_id",
            table_name="diagnosis_impressions",
        )
        op.drop_index(
            "ix_diagnosis_impressions_child_id",
            table_name="diagnosis_impressions",
        )
        op.drop_table("diagnosis_impressions")
