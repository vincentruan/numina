"""merge heads

Revision ID: 724957cc6de9
Revises: ac070c6b7aaf, g8057i30hfe7
Create Date: 2026-05-03 17:28:38.531822

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '724957cc6de9'
down_revision: tuple[str, ...] = ('ac070c6b7aaf', 'g8057i30hfe7')  # type: ignore[assignment]
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass