"""add total_approved_count to users

Revision ID: s0158t32umn8
Revises: r9047s21tlm7
Create Date: 2026-05-19

Adds:
- users.total_approved_count: integer tracking cumulative approved tasks
"""

import sqlalchemy as sa
from alembic import op

revision = 's0158t32umn8'
down_revision = 'r9047s21tlm7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot ADD COLUMN NOT NULL with a non-constant default in one step.
    # Add nullable first, backfill with 0, then alter to NOT NULL.
    op.add_column(
        'users',
        sa.Column(
            'total_approved_count',
            sa.Integer(),
            nullable=True,
        ),
    )
    op.execute("UPDATE users SET total_approved_count = 0 WHERE total_approved_count IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'total_approved_count')