"""merge heads

Revision ID: 6861f2ca98ef
Revises: 9350dbcfcb04, src001tax001
Create Date: 2026-10-12 18:11:34.013696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6861f2ca98ef'
down_revision: Union[str, None] = ('9350dbcfcb04', 'src001tax001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass