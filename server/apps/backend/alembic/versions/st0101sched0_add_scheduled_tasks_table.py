"""add scheduled_tasks table

Revision ID: st0101sched0
Revises: bk0101brun01
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "st0101sched0"
down_revision: str | None = "bk0101brun01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "scheduled_tasks"):
        return  # table already present (fresh-DB bootstrap)

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column(
            "family_id",
            sa.BigInteger(),
            sa.ForeignKey("families.id"),
            nullable=False,
        ),
        sa.Column("skill_id", sa.String(length=50), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=False),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="idle",
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
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
    op.create_index(
        "ix_scheduled_tasks_family_enabled",
        "scheduled_tasks",
        ["family_id", "is_enabled"],
    )
    op.create_index(
        "ix_scheduled_tasks_poll",
        "scheduled_tasks",
        ["is_enabled", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_tasks_poll", table_name="scheduled_tasks")
    op.drop_index(
        "ix_scheduled_tasks_family_enabled", table_name="scheduled_tasks"
    )
    op.drop_table("scheduled_tasks")
