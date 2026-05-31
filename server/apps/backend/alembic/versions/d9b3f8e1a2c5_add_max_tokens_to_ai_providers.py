"""add max_tokens to ai_providers

Revision ID: d9b3f8e1a2c5
Revises: c8a1e7d3f4b2
Create Date: 2026-05-31

Adds nullable ``max_tokens`` column to ``ai_providers`` so the per-family AI
provider config can hold an explicit per-response output token cap. NULL means
"use system default", which is resolved by the agent's
``_resolve_max_tokens`` helper against ``system-config.yaml`` (prefix table).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9b3f8e1a2c5"
down_revision: str | None = "c8a1e7d3f4b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_providers",
        sa.Column("max_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_providers", "max_tokens")
