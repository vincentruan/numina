"""add child_learning_stats table

Revision ID: a1b2c3d4e5f6
Revises: 99aaefc36764
Create Date: 2026-09-28
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "lrnst001"
down_revision: str | None = "99aaefc36764"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: if table already exists (created by Base.metadata.create_all),
    # skip migration.
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "child_learning_stats"):
        return

    op.create_table(
        "child_learning_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "child_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "family_id",
            sa.BigInteger(),
            sa.ForeignKey("families.id"),
            nullable=False,
        ),
        sa.Column("cumulative_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "learning_streak_days", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("last_learning_date", sa.Date(), nullable=True),
        sa.Column(
            "current_zone", sa.String(10), nullable=False, server_default="growth"
        ),
        sa.Column(
            "onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("xp_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_xp_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_child_learning_stats_child_id", "child_learning_stats", ["child_id"])
    op.create_index("ix_child_learning_stats_family_id", "child_learning_stats", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_child_learning_stats_family_id", table_name="child_learning_stats")
    op.drop_index("ix_child_learning_stats_child_id", table_name="child_learning_stats")
    op.drop_table("child_learning_stats")
