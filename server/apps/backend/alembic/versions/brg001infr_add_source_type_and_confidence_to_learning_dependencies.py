"""add source_type and confidence to learning_dependencies

Revision ID: brg001infr
Revises: idx002clstr
Create Date: 2026-10-22

Adds provenance tracking for cross-subject bridge edges:
- source_type: 'explicit' (human-curated) or 'inferred' (algorithm-generated)
- confidence: 0.0–1.0 score for inferred edges, NULL for explicit
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "brg001infr"
down_revision: str | None = "idx002clstr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_dependencies",
        sa.Column(
            "source_type",
            sa.String(20),
            nullable=False,
            server_default="explicit",
        ),
    )
    op.add_column(
        "learning_dependencies",
        sa.Column("confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_dependencies", "confidence")
    op.drop_column("learning_dependencies", "source_type")
