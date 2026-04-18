"""add_streak_bonus_to_chore_instances

Revision ID: b2c3d4e5f6a7
Revises: perf_idx_001
Create Date: 2026-04-16 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'perf_idx_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    existing_cols = {c['name'] for c in inspector.get_columns('chore_instances')}
    if 'streak_bonus' not in existing_cols:
        op.add_column(
            'chore_instances',
            sa.Column('streak_bonus', sa.Integer(), nullable=False, server_default='0'),
        )


def downgrade() -> None:
    op.drop_column('chore_instances', 'streak_bonus')
