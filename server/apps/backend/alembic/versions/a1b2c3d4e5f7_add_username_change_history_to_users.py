"""add username_change_history to users

Revision ID: a1b2c3d4e5f7
Revises: m1a2n3i4f5e6
Create Date: 2026-08-02 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: str | None = 'm1a2n3i4f5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username_change_history', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'username_change_history')
