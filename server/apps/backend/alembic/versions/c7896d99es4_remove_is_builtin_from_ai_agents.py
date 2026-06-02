"""remove is_builtin column from ai_agents

Revision ID: c7896d99es4
Revises: b6895c98ds3
Create Date: 2026-06-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7896d99es4"
down_revision: Union[str, None] = "b6895c98ds3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the is_builtin column — agent_type='system' now unified with former builtin agents
    op.drop_column("ai_agents", "is_builtin")
    # Update agent_type default from 'builtin' to 'system' (no more builtin type)
    op.alter_column(
        "ai_agents",
        "agent_type",
        server_default=sa.text("'system'"),
    )
    # Migrate any remaining 'builtin' rows to 'system' (should be zero after b6745e8a2c14)
    op.execute(
        "UPDATE ai_agents SET agent_type = 'system' WHERE agent_type = 'builtin'"
    )


def downgrade() -> None:
    # Re-add is_builtin column
    op.add_column(
        "ai_agents",
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Backfill: system agents get is_builtin=true
    op.execute(
        "UPDATE ai_agents SET is_builtin = true WHERE agent_type = 'system'"
    )
    # Restore original default for agent_type
    op.alter_column(
        "ai_agents",
        "agent_type",
        server_default=sa.text("'builtin'"),
    )