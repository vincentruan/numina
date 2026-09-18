"""merge notification and ASR CB migrations

Revision ID: e8674585435d
Revises: 75e411962098, m3x9k7p2qr5w
Create Date: 2026-09-18 10:50:42.318356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8674585435d'
down_revision: Union[str, None] = ('75e411962098', 'm3x9k7p2qr5w')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass