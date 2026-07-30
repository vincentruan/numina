"""merge agent and wishes heads

Revision ID: 1f81374239ae
Revises: b6745e8a2c14, c7583a86bst1
Create Date: 2026-05-28 21:07:35.017363

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '1f81374239ae'
down_revision: tuple[str, ...] = ('b6745e8a2c14', 'c7583a86bst1')  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass