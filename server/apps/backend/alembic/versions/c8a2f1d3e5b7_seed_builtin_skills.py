"""seed builtin skills into ai_skills table

Revision ID: c8a2f1d3e5b7
Revises: 4637e33e94ac
Create Date: 2026-06-01

NOTE: Data seeding moved to app/bootstrap/skills.py (runs on every startup).
This migration is retained as a no-op to preserve the Alembic revision chain.
"""

from collections.abc import Sequence

revision: str = "c8a2f1d3e5b7"
down_revision: str | None = "4637e33e94ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
