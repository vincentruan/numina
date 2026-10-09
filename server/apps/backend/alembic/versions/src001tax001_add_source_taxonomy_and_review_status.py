"""add source_taxonomy and review_status columns

Revision ID: src001tax001
Revises: lrnst001
Create Date: 2026-10-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "src001tax001"
down_revision: str | None = "lrnst001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # LearningTopic: add source_taxonomy and curriculum_standards_json
    op.add_column(
        "learning_topics",
        sa.Column(
            "source_taxonomy",
            sa.String(20),
            nullable=False,
            server_default="os-taxonomy",
        ),
    )
    op.create_index(
        "ix_learning_topics_source_taxonomy",
        "learning_topics",
        ["source_taxonomy"],
        unique=False,
    )
    op.add_column(
        "learning_topics",
        sa.Column(
            "curriculum_standards_json",
            sa.Text(),
            nullable=True,
            server_default="[]",
        ),
    )

    # LearningTopic: replace unique constraint on topic_key with composite
    # (topic_key, source_taxonomy)
    bind = op.get_bind()
    # Drop existing unique constraint on topic_key (SQLite uses batch mode)
    with op.batch_alter_table("learning_topics") as batch_op:
        batch_op.drop_constraint("uq_learning_topics_topic_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_topic_key_source", ["topic_key", "source_taxonomy"]
        )

    # LearningDependency: add review_status
    op.add_column(
        "learning_dependencies",
        sa.Column("review_status", sa.String(10), nullable=True),
    )

    # LearningCluster: add source_taxonomy
    op.add_column(
        "learning_clusters",
        sa.Column(
            "source_taxonomy",
            sa.String(20),
            nullable=False,
            server_default="os-taxonomy",
        ),
    )


def downgrade() -> None:
    op.drop_column("learning_clusters", "source_taxonomy")
    op.drop_column("learning_dependencies", "review_status")

    with op.batch_alter_table("learning_topics") as batch_op:
        batch_op.drop_constraint("uq_topic_key_source", type_="unique")
        batch_op.create_unique_constraint("uq_learning_topics_topic_key", ["topic_key"])

    op.drop_index("ix_learning_topics_source_taxonomy", table_name="learning_topics")
    op.drop_column("learning_topics", "curriculum_standards_json")
    op.drop_column("learning_topics", "source_taxonomy")
