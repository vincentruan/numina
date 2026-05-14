"""add composite index for ai_tasks queued lookup

Revision ID: l3502n85mjh2
Revises: 22e92ca97778
Create Date: 2026-05-11 21:00:00.000000

Adds:
- Composite index on (family_id, status, queue_position) for efficient
  get_next_queued_task queries that filter by family+status and order by position.
"""

from alembic import op

revision = 'l3502n85mjh2'
down_revision = '22e92ca97778'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_ai_tasks_family_status_queue',
        'ai_tasks',
        ['family_id', 'status', 'queue_position'],
    )


def downgrade() -> None:
    op.drop_index('ix_ai_tasks_family_status_queue', table_name='ai_tasks')
