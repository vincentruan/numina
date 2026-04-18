"""add_performance_indexes

Revision ID: a1b2c3d4e5f6
Revises: f32c9ec07d5e
Create Date: 2026-04-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'perf_idx_001'
down_revision: Union[str, None] = 'f32c9ec07d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # child_wishes: queries filter by family_id+child_user_id and family_id+status
    op.create_index('ix_child_wishes_child_user_id', 'child_wishes', ['child_user_id'], if_not_exists=True)
    op.create_index('ix_child_wishes_family_status', 'child_wishes', ['family_id', 'status'], if_not_exists=True)

    # chore_instances: queries filter by child_user_id and status
    op.create_index('ix_chore_instances_child_user_id', 'chore_instances', ['child_user_id'], if_not_exists=True)
    op.create_index('ix_chore_instances_family_status', 'chore_instances', ['family_id', 'status'], if_not_exists=True)

    # coin_transactions: queries filter by child_user_id
    op.create_index('ix_coin_transactions_child_user_id', 'coin_transactions', ['child_user_id'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_coin_transactions_child_user_id', table_name='coin_transactions', if_exists=True)
    op.drop_index('ix_chore_instances_family_status', table_name='chore_instances', if_exists=True)
    op.drop_index('ix_chore_instances_child_user_id', table_name='chore_instances', if_exists=True)
    op.drop_index('ix_child_wishes_family_status', table_name='child_wishes', if_exists=True)
    op.drop_index('ix_child_wishes_child_user_id', table_name='child_wishes', if_exists=True)
