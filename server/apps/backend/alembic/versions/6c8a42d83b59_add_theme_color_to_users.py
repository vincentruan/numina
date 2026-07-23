"""add theme_color to users

Revision ID: 6c8a42d83b59
Revises: d4e5f6a7b8c9
Create Date: 2026-07-22 08:24:07.809063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c8a42d83b59'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('theme_color', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'theme_color')
