"""add is_builtin column back to ai_agents

Revision ID: b6895c98ds3
Revises: a5894b97cs2
Create Date: 2026-06-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6895c98ds3"
down_revision: str | None = "a5894b97cs2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add is_builtin column (was previously dropped by a53453cf574b)
    op.add_column(
        "ai_agents",
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Backfill existing agents: system and builtin agents should have is_builtin=true
    op.execute(
        "UPDATE ai_agents SET is_builtin = true WHERE agent_type IN ('system', 'builtin')"
    )


def downgrade() -> None:
    op.drop_column("ai_agents", "is_builtin")