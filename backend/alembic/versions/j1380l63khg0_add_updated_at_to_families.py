"""add updated_at to families

Revision ID: j1380l63khg0
Revises: i0279k52jgf9
Create Date: 2026-05-10 00:00:00.000000

Adds:
- families.updated_at: timestamp updated on every write
"""

import sqlalchemy as sa

from alembic import op

revision = 'j1380l63khg0'
down_revision = 'i0279k52jgf9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'families',
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('families', 'updated_at')
