"""add backup_runs table

Revision ID: bk0101brun01
Revises: brg001infr
Create Date: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bk0101brun01"
down_revision: str | None = "brg001infr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "backup_runs"):
        return  # table already present (fresh-DB bootstrap)

    op.create_table(
        "backup_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "family_id",
            sa.BigInteger(),
            sa.ForeignKey("families.id"),
            nullable=False,
        ),
        sa.Column("backup_date", sa.String(length=8), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_backup_runs_family_id", "backup_runs", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_backup_runs_family_id", table_name="backup_runs")
    op.drop_table("backup_runs")
