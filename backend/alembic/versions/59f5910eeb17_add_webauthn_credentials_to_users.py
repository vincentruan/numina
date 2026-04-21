"""add webauthn_credentials to users

Revision ID: 59f5910eeb17
Revises: m4n5o6p7q8r9
Create Date: 2026-04-21 16:33:59.315645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '59f5910eeb17'
down_revision: Union[str, None] = 'm4n5o6p7q8r9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('webauthn_credentials', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'webauthn_credentials')
