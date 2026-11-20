"""add per-feature homepage AI toggles to families

Revision ID: abc123feature001
Revises: mrg001lrnheads
Create Date: 2026-11-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "abc123feature001"
down_revision: str | None = "mrg001lrnheads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in bind.dialect.get_columns(bind, table)}
    return col in cols


def upgrade() -> None:
    if not _has_column("families", "finance_coach_enabled"):
        op.add_column(
            "families",
            sa.Column(
                "finance_coach_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )
    if not _has_column("families", "narrative_enabled"):
        op.add_column(
            "families",
            sa.Column(
                "narrative_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )
    if not _has_column("families", "literacy_enabled"):
        op.add_column(
            "families",
            sa.Column(
                "literacy_enabled",
                sa.Boolean(),
                server_default=sa.text("true"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_column("families", "literacy_enabled")
    op.drop_column("families", "narrative_enabled")
    op.drop_column("families", "finance_coach_enabled")
