"""demote builtin agents and seed numina

Revision ID: b6745e8a2c14
Revises: a53453cf574b
Create Date: 2026-05-27

NOTE: Agent seeding moved to app/bootstrap/agents.py (runs on every startup).
This migration is retained as a no-op to preserve the Alembic revision chain.
The old builtin agents (asset-health-advisor, finance-optimizer) were deleted
by this migration historically; that deletion is now permanent state.
"""

from collections.abc import Sequence

revision: str = "b6745e8a2c14"
down_revision: str | None = "a53453cf574b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
