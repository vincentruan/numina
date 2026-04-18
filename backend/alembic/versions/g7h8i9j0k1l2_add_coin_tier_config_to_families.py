"""add_coin_tier_config_to_families

Revision ID: g7h8i9j0k1l2
Revises: e5f6a7b8c9d0
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('families')}
    with op.batch_alter_table('families') as batch_op:
        if 'coin_copper_to_silver' not in cols:
            batch_op.add_column(sa.Column('coin_copper_to_silver', sa.Integer(), nullable=False, server_default='10'))
        if 'coin_silver_to_gold' not in cols:
            batch_op.add_column(sa.Column('coin_silver_to_gold', sa.Integer(), nullable=False, server_default='10'))


def downgrade() -> None:
    with op.batch_alter_table('families') as batch_op:
        batch_op.drop_column('coin_silver_to_gold')
        batch_op.drop_column('coin_copper_to_silver')
