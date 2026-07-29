"""add asr_provider_configs table

Revision ID: 780b6dcce28c
Revises: 2c22be59d705
Create Date: 2026-07-29 21:01:59.442593

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '780b6dcce28c'
down_revision: Union[str, None] = '2c22be59d705'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'asr_provider_configs',
        sa.Column('id', sa.BIGINT(), nullable=False),
        sa.Column('family_id', sa.BIGINT(), nullable=False),
        sa.Column('name', sa.VARCHAR(length=100), nullable=False),
        sa.Column('provider', sa.VARCHAR(length=20), nullable=False),
        sa.Column('api_key_encrypted', sa.TEXT(), nullable=True),
        sa.Column('base_url', sa.TEXT(), nullable=True),
        sa.Column('model_id', sa.VARCHAR(length=100), nullable=True),
        sa.Column('model_2_id', sa.VARCHAR(length=100), nullable=True),
        sa.Column('model_3_id', sa.VARCHAR(length=100), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False),
        sa.Column('display_order', sa.INTEGER(), nullable=True),
        sa.Column('circuit_state', sa.VARCHAR(length=20), nullable=False),
        sa.Column('failure_count', sa.INTEGER(), nullable=False),
        sa.Column('last_failure_at', sa.DATETIME(), nullable=True),
        sa.Column('test_passed', sa.BOOLEAN(), nullable=True),
        sa.Column('test_message', sa.TEXT(), nullable=True),
        sa.Column('test_latency_ms', sa.INTEGER(), nullable=True),
        sa.Column('tested_at', sa.DATETIME(), nullable=True),
        sa.Column('created_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DATETIME(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_asr_provider_configs_family_id'), 'asr_provider_configs', ['family_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_asr_provider_configs_family_id'), table_name='asr_provider_configs')
    op.drop_table('asr_provider_configs')
