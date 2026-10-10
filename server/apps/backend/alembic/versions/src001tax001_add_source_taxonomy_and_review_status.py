"""add source_taxonomy and review_status columns

Revision ID: src001tax001
Revises: lrnst001
Create Date: 2026-10-09

Downgrade caveat: reverting this migration restores a single-column unique
constraint on ``topic_key``. Once Beijing data has been seeded, the table
legitimately holds the same ``topic_key`` under two ``source_taxonomy`` values,
so the downgrade will fail on the uniqueness check. Downgrade is therefore only
safe before the first ``--source beijing`` seed, or after deleting the
duplicate-``topic_key`` rows the composite constraint allowed.
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
    # (topic_key, source_taxonomy).
    #
    # The original uniqueness mechanism varies by dialect:
    #   - PostgreSQL: the original migration (7fc4e7ea69ca) created a unique
    #     INDEX named ix_learning_topics_topic_key via create_index(unique=True).
    #     It also auto-names inline UNIQUE clauses as "<table>_<column>_key".
    #     Drop both the index and any constraint to cover all cases.
    #   - SQLite: uses batch_alter_table which rebuilds the table from the
    #     current model definition (index=True, not unique=True).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Drop the original unique INDEX (created by create_index unique=True)
        op.execute("DROP INDEX IF EXISTS ix_learning_topics_topic_key")
        # Also drop any constraint variants (defense in depth)
        op.execute(
            "ALTER TABLE learning_topics "
            "DROP CONSTRAINT IF EXISTS learning_topics_topic_key_key"
        )
        op.execute(
            "ALTER TABLE learning_topics "
            "DROP CONSTRAINT IF EXISTS uq_learning_topics_topic_key"
        )
        op.create_unique_constraint(
            "uq_topic_key_source",
            "learning_topics",
            ["topic_key", "source_taxonomy"],
        )
    else:
        # SQLite: batch_alter_table rebuilds the table
        with op.batch_alter_table("learning_topics") as batch_op:
            batch_op.drop_constraint(
                "uq_learning_topics_topic_key", type_="unique"
            )
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

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE learning_topics "
            "DROP CONSTRAINT IF EXISTS uq_topic_key_source"
        )
        op.create_unique_constraint(
            "learning_topics_topic_key_key",
            "learning_topics",
            ["topic_key"],
        )
    else:
        with op.batch_alter_table("learning_topics") as batch_op:
            batch_op.drop_constraint("uq_topic_key_source", type_="unique")
            batch_op.create_unique_constraint(
                "uq_learning_topics_topic_key", ["topic_key"]
            )

    op.drop_index("ix_learning_topics_source_taxonomy", table_name="learning_topics")
    op.drop_column("learning_topics", "curriculum_standards_json")
    op.drop_column("learning_topics", "source_taxonomy")
