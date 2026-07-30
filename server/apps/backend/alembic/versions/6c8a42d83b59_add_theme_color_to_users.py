"""add theme_color to users

Revision ID: 6c8a42d83b59
Revises: d4e5f6a7b8c9
Create Date: 2026-07-22 08:24:07.809063

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6c8a42d83b59'
down_revision: str | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('theme_color', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'theme_color')
