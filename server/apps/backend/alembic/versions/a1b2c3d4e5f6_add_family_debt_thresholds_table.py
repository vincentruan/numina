"""add family_debt_thresholds table

Revision ID: a1b2c3d4e5f6
Revises: c2d3e4f5a6b7
Create Date: 2026-07-20

Adds:
- family_debt_thresholds table for W5 (Plan B T8): per-family high-interest-debt
  thresholds (credit_card / personal_loan / mortgage / other). One row per family.
"""

import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'family_debt_thresholds',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('family_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('credit_card', sa.Integer, nullable=False, server_default=sa.text('12')),
        sa.Column('personal_loan', sa.Integer, nullable=False, server_default=sa.text('10')),
        sa.Column('mortgage', sa.Integer, nullable=False, server_default=sa.text('6')),
        sa.Column('other', sa.Integer, nullable=False, server_default=sa.text('10')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('family_id', name='uq_family_debt_thresholds_family'),
    )


def downgrade() -> None:
    op.drop_table('family_debt_thresholds')
