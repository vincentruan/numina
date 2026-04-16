"""add_streak_bonus_to_coin_transactions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-16 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'coin_transactions',
        sa.Column('streak_bonus', sa.Integer(), nullable=True, comment='Bonus coins from streak multiplier (actual_amount - base_reward). NULL for non-chore transactions.'),
    )
    # Ensure triggered_at on child_milestones stores timezone-aware timestamps
    with op.batch_alter_table('child_milestones') as batch_op:
        batch_op.alter_column(
            'triggered_at',
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('child_milestones') as batch_op:
        batch_op.alter_column(
            'triggered_at',
            type_=sa.DateTime(timezone=False),
            existing_nullable=False,
        )
    op.drop_column('coin_transactions', 'streak_bonus')
