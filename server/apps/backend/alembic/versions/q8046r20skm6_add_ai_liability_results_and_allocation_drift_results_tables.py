"""add ai_liability_results and ai_allocation_drift_results tables

Revision ID: q8046r20skm6
Revises: p6935q19rjk5
Create Date: 2026-05-17 10:00:00.000000

Adds:
- ai_liability_results table for storing liability advice analysis results
- ai_allocation_drift_results table for storing allocation drift check results
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'q8046r20skm6'
down_revision: Union[str, None] = 'p6935q19rjk5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ai_liability_results table
    op.create_table(
        'ai_liability_results',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('has_liabilities', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('total_remaining', sa.Float(), nullable=True),
        sa.Column('total_monthly_payment', sa.Float(), nullable=True),
        sa.Column('liability_count', sa.Integer(), nullable=True),
        sa.Column('narrative', sa.Text(), nullable=True),
        sa.Column('recommended_strategy', sa.String(20), nullable=True),
        sa.Column('strategies_json', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ai_liability_results_family_id', 'ai_liability_results', ['family_id'])

    # ai_allocation_drift_results table
    op.create_table(
        'ai_allocation_drift_results',
        sa.Column('id', sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('has_significant_drift', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('narrative', sa.Text(), nullable=True),
        sa.Column('drifts_json', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ai_allocation_drift_results_family_id', 'ai_allocation_drift_results', ['family_id'])


def downgrade() -> None:
    op.drop_index('ix_ai_allocation_drift_results_family_id', table_name='ai_allocation_drift_results')
    op.drop_table('ai_allocation_drift_results')
    op.drop_index('ix_ai_liability_results_family_id', table_name='ai_liability_results')
    op.drop_table('ai_liability_results')