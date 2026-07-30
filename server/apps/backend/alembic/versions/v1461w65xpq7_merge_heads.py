"""merge heads u1350v54wop6 and w0159x32vnm9

Revision ID: v1461w65xpq7
Revises: u1350v54wop6, w0159x32vnm9
Create Date: 2026-05-20

Merges the circuit breaker enhancement branch with the extraction audit branch.
"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'v1461w65xpq7'
down_revision: tuple[str, ...] = ('u1350v54wop6', 'w0159x32vnm9')  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No schema changes - this is a merge migration
    pass


def downgrade() -> None:
    # No schema changes - this is a merge migration
    pass