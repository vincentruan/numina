"""merge heads

Revision ID: fa6bcb4dcc4d
Revises: 7e657997df69, y3692z75arq0
Create Date: 2026-06-02 21:12:09.799410

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'fa6bcb4dcc4d'
down_revision: tuple[str, ...] = ('7e657997df69', 'y3692z75arq0')  # type: ignore[assignment]
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass