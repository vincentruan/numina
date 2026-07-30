"""add memory_enabled column to ai_agents

Revision ID: a9c4f2e1b7d3
Revises: z4783a86brs1
Create Date: 2026-07-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c4f2e1b7d3"
down_revision: str | None = "d7b2c4e9f108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # memory_enabled defaults True (chat + custom agents keep memory). System
    # agent asset-report is updated to False by bootstrap_agents on startup.
    op.add_column(
        "ai_agents",
        sa.Column(
            "memory_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_agents", "memory_enabled")
