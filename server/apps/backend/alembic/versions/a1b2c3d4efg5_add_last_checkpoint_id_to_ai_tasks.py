"""add last_checkpoint_id to ai_tasks

Revision ID: a1b2c3d4efg5
Revises: z4783a86brs1
Create Date: 2026-09-23 10:00:00.000000

Adds last_checkpoint_id column for checkpoint-based resume support.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4efg5"
down_revision: str | None = "z4783a86brs1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add last_checkpoint_id column to ai_tasks."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("ai_tasks")}

    with op.batch_alter_table("ai_tasks", schema=None) as batch_op:
        if "last_checkpoint_id" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "last_checkpoint_id",
                    sa.String(128),
                    nullable=True,
                    comment="Last LangGraph checkpoint ID for resume",
                )
            )


def downgrade() -> None:
    """Remove last_checkpoint_id column."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col["name"] for col in inspector.get_columns("ai_tasks")}

    with op.batch_alter_table("ai_tasks", schema=None) as batch_op:
        if "last_checkpoint_id" in existing_columns:
            batch_op.drop_column("last_checkpoint_id")
