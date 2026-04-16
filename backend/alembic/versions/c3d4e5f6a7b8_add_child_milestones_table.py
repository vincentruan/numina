"""add_child_milestones_table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-16 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'child_milestones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('family_id', sa.String(length=36), nullable=False),
        sa.Column('child_user_id', sa.String(length=36), nullable=False),
        sa.Column('milestone_type', sa.String(length=50), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('ref_id', sa.String(length=36), nullable=True),
        sa.Column('ref_type', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['child_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_child_milestones_child_user_id', 'child_milestones', ['child_user_id'])
    op.create_index('ix_child_milestones_child_type', 'child_milestones', ['child_user_id', 'milestone_type'])
    op.create_unique_constraint('uq_child_milestone_type', 'child_milestones', ['child_user_id', 'milestone_type'])


def downgrade() -> None:
    op.drop_constraint('uq_child_milestone_type', 'child_milestones', type_='unique')
    op.drop_index('ix_child_milestones_child_type', table_name='child_milestones')
    op.drop_index('ix_child_milestones_child_user_id', table_name='child_milestones')
    op.drop_table('child_milestones')
