"""add index for chore instances family_date_child query

Revision ID: n5724p07oki4
Revises: m4613o96nki3
Create Date: 2026-05-15 23:30:00.000000

Performance index for:
- list_children_chores (parent view of all children's chores)
- get_or_create_instances (child view of visible chores)

Query pattern:
WHERE family_id = X AND (child_user_id IN (...) OR child_user_id = family_id)
  AND date_bucket IN (...)

Index: (family_id, date_bucket, child_user_id)
"""

from alembic import op

revision = 'n5724p07oki4'
down_revision = 'm4613o96nki3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_chore_instances_family_date_child',
        'chore_instances',
        ['family_id', 'date_bucket', 'child_user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_chore_instances_family_date_child', table_name='chore_instances')