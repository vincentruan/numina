"""add assigned_by_user_id and claimed_at to chore_instances

Revision ID: m4613o96nki3
Revises: l3502n85mjh2
Create Date: 2026-05-15 00:00:00.000000

Adds:
- assigned_by_user_id (BigInteger, nullable FK to users.id) — records which parent
  hard-assigned a pool instance to a specific child
- claimed_at (DateTime, nullable) — records when a child self-claimed a pool instance
"""

import sqlalchemy as sa
from alembic import op

revision = 'm4613o96nki3'
down_revision = '0b0a9def92f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('chore_instances', sa.Column('assigned_by_user_id', sa.BigInteger(), nullable=True))
    op.add_column('chore_instances', sa.Column('claimed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('chore_instances', 'claimed_at')
    op.drop_column('chore_instances', 'assigned_by_user_id')
