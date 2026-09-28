"""add_learning_paths_and_cluster_summary_zh

Revision ID: 99aaefc36764
Revises: 1ad863667f70
Create Date: 2026-09-27 20:05:18.181423

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "99aaefc36764"
down_revision: str | None = "1ad863667f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- learning_clusters.summary_zh ---
    if bind.dialect.has_table(bind, "learning_clusters"):
        cols = {c["name"] for c in bind.dialect.get_columns(bind, "learning_clusters")}
        if "summary_zh" not in cols:
            op.add_column(
                "learning_clusters",
                sa.Column("summary_zh", sa.Text(), nullable=True),
            )

    # --- learning_paths ---
    if not bind.dialect.has_table(bind, "learning_paths"):
        op.create_table(
            "learning_paths",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column(
                "family_id",
                sa.BigInteger(),
                sa.ForeignKey("families.id"),
                nullable=False,
            ),
            sa.Column(
                "child_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "created_by",
                sa.BigInteger(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("name_zh", sa.String(200), nullable=True),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("description_zh", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column(
                "per_task_score", sa.Integer(), nullable=False, server_default="5"
            ),
            sa.Column("bonus_score", sa.Integer(), nullable=False, server_default="10"),
            sa.Column(
                "milestone_scores_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_learning_paths_family_id", "learning_paths", ["family_id"])
        op.create_index("ix_learning_paths_child_id", "learning_paths", ["child_id"])

    # --- learning_path_items ---
    if not bind.dialect.has_table(bind, "learning_path_items"):
        op.create_table(
            "learning_path_items",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column(
                "path_id",
                sa.BigInteger(),
                sa.ForeignKey("learning_paths.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "topic_id",
                sa.BigInteger(),
                sa.ForeignKey("learning_topics.id"),
                nullable=False,
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="pending"
            ),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_learning_path_items_path_id",
            "learning_path_items",
            ["path_id"],
        )


def downgrade() -> None:
    op.drop_table("learning_path_items")
    op.drop_table("learning_paths")
    op.drop_column("learning_clusters", "summary_zh")
