"""merge_heads_for_stamp

Revision ID: b6b918b0cb30
Revises: c2d3e4f5a6b7, m1a2n3i4f5e6
Create Date: 2026-09-10 11:38:58.895566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6b918b0cb30'
down_revision: Union[str, None] = ('c2d3e4f5a6b7', 'm1a2n3i4f5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass