"""add preset_learning_paths table

Revision ID: lrnprst00001
Revises: 1f05a4b6a5de
Create Date: 2026-10-19 10:00:00.000000

Adds preset_learning_paths table for curriculum-aligned learning path templates.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "lrnprst00001"
down_revision: str | None = "1f05a4b6a5de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create preset_learning_paths table."""
    op.create_table(
        "preset_learning_paths",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("semester", sa.String(10), nullable=False),
        sa.Column("subject", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_zh", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic_ids_json", sa.Text(), nullable=False),
        sa.Column("topic_count", sa.Integer(), nullable=False),
        sa.Column("age_group", sa.String(10), nullable=False),
        sa.Column("source_taxonomy", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_preset_learning_paths_grade"),
        "preset_learning_paths",
        ["grade"],
        unique=False,
    )
    op.create_index(
        op.f("ix_preset_learning_paths_subject"),
        "preset_learning_paths",
        ["subject"],
        unique=False,
    )


def downgrade() -> None:
    """Drop preset_learning_paths table."""
    op.drop_index(
        op.f("ix_preset_learning_paths_subject"), table_name="preset_learning_paths"
    )
    op.drop_index(
        op.f("ix_preset_learning_paths_grade"), table_name="preset_learning_paths"
    )
    op.drop_table("preset_learning_paths")
