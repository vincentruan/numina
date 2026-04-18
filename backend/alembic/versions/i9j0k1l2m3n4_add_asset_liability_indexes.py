"""add asset and liability performance indexes

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-18 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # assets: most common dashboard filter (family_id + is_archived)
    op.create_index('ix_assets_family_id_is_archived', 'assets', ['family_id', 'is_archived'], if_not_exists=True)
    # assets: get_home_assets and get_states_summary GROUP BY status
    op.create_index('ix_assets_family_id_status', 'assets', ['family_id', 'status'], if_not_exists=True)
    # liabilities: liability aggregation filter (family_id + is_active)
    op.create_index('ix_liabilities_family_id_is_active', 'liabilities', ['family_id', 'is_active'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_liabilities_family_id_is_active', table_name='liabilities', if_exists=True)
    op.drop_index('ix_assets_family_id_status', table_name='assets', if_exists=True)
    op.drop_index('ix_assets_family_id_is_archived', table_name='assets', if_exists=True)
