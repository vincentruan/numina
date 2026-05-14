"""add ai_tasks table

Revision ID: h9168j41ife8
Revises: g8057i30hfe7
Create Date: 2026-05-04 10:00:00.000000

Adds:
- ai_tasks table for tracking async AI capability task status
"""

import sqlalchemy as sa

from alembic import op

revision = 'h9168j41ife8'
down_revision = '2b8b34306273'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_tasks',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('capability', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('ai_chat_sessions.id'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
    )
    op.create_index('ix_ai_tasks_family_id', 'ai_tasks', ['family_id'])
    op.create_index('ix_ai_tasks_capability', 'ai_tasks', ['capability'])
    # Partial unique index: at most one running task per family+capability
    op.execute(
        "CREATE UNIQUE INDEX uq_ai_tasks_family_capability_running "
        "ON ai_tasks (family_id, capability) WHERE status = 'running'"
    )


def downgrade() -> None:
    op.drop_index('uq_ai_tasks_family_capability_running', table_name='ai_tasks')
    op.drop_index('ix_ai_tasks_capability', table_name='ai_tasks')
    op.drop_index('ix_ai_tasks_family_id', table_name='ai_tasks')
    op.drop_table('ai_tasks')
