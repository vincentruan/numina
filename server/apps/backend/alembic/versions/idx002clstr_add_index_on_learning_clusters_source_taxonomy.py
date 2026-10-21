"""add index on learning_clusters.source_taxonomy

Revision ID: idx002clstr
Revises: e805c16f361a
Create Date: 2026-10-21

"""
from alembic import op

revision = "idx002clstr"
down_revision = "e805c16f361a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_learning_clusters_source_taxonomy",
        "learning_clusters",
        ["source_taxonomy"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_clusters_source_taxonomy", table_name="learning_clusters"
    )
