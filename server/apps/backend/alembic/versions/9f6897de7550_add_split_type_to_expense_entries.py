"""add split_type to expense_entries

Revision ID: 9f6897de7550
Revises: 3fee53d71f7e
Create Date: 2026-09-21 18:21:02.994865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f6897de7550'
down_revision: Union[str, None] = '3fee53d71f7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('expense_entries', sa.Column('split_type', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('expense_entries', 'split_type')
