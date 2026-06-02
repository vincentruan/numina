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


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (SQLite-compatible)."""
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result.fetchall()]
    return column_name in columns


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN for changing defaults.
    # We rely on the model's server_default definition instead.
    # The model already has server_default=text("'system'") which will apply
    # to new rows. For SQLite, we skip the alter_column operation.

    # Migrate any remaining 'builtin' rows to 'system' (should be zero after b6745e8a2c14)
    op.execute(
        "UPDATE ai_agents SET agent_type = 'system' WHERE agent_type = 'builtin'"
    )

    # Drop the is_builtin column — agent_type='system' now unified with former builtin agents
    # SQLite 3.35.0+ supports DROP COLUMN, but not IF EXISTS syntax
    # Check if column exists before dropping
    if _column_exists("ai_agents", "is_builtin"):
        op.drop_column("ai_agents", "is_builtin")


def downgrade() -> None:
    # Re-add is_builtin column if it doesn't exist
    if not _column_exists("ai_agents", "is_builtin"):
        op.add_column(
            "ai_agents",
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    # Backfill: system agents get is_builtin=true
    op.execute(
        "UPDATE ai_agents SET is_builtin = true WHERE agent_type = 'system'"
    )