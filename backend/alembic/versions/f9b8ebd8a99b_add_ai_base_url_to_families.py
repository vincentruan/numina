"""add ai_base_url to families

Revision ID: f9b8ebd8a99b
Revises: a8f3b2c1d4e5
Create Date: 2026-04-13 12:12:25.241734

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9b8ebd8a99b'
down_revision: Union[str, None] = 'a8f3b2c1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('families', sa.Column('ai_base_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('families', 'ai_base_url')
