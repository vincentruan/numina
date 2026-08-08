"""add ai_enabled column to families

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2026-08-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5g6h7"
down_revision: str | None = "b1c2d3e4f5g6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return bind.dialect.has_table(bind, table)


def _has_column(table: str, col: str) -> bool:
    if not _has_table(table):
        return False
    bind = op.get_bind()
    cols = {c["name"] for c in bind.dialect.get_columns(bind, table)}
    return col in cols


def upgrade() -> None:
    if not _has_column("families", "ai_enabled"):
        op.add_column(
            "families",
            sa.Column(
                "ai_enabled",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )

    # Backfill: families with at least one active AI provider → ai_enabled = true
    if _has_table("ai_providers"):
        op.execute(
            """
            UPDATE families SET ai_enabled = true
            WHERE id IN (
                SELECT DISTINCT family_id FROM ai_providers
                WHERE is_active = true AND api_key_encrypted IS NOT NULL
            )
            """
        )


def downgrade() -> None:
    op.drop_column("families", "ai_enabled")
