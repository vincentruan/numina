"""make ai result asset_id nullable

Revision ID: r9047s21tlm7
Revises: q8046r20skm6
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r9047s21tlm7'
down_revision = 'q8046r20skm6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make asset_id nullable in ai_asset_alerts
    op.alter_column('ai_asset_alerts', 'asset_id',
        existing_type=sa.BigInteger(),
        nullable=True)

    # Make asset_id nullable in ai_disposal_suggestions
    op.alter_column('ai_disposal_suggestions', 'asset_id',
        existing_type=sa.BigInteger(),
        nullable=True)

    # Make asset_id nullable in ai_spending_leaks
    op.alter_column('ai_spending_leaks', 'asset_id',
        existing_type=sa.BigInteger(),
        nullable=True)


def downgrade() -> None:
    # Revert asset_id to non-nullable in ai_spending_leaks
    op.alter_column('ai_spending_leaks', 'asset_id',
        existing_type=sa.BigInteger(),
        nullable=False)

    # Revert asset_id to non-nullable in ai_disposal_suggestions
    op.alter_column('ai_disposal_suggestions', 'asset_id',
        existing_type=sa.BigInteger(),
        nullable=False)

    # Revert asset_id to non-nullable in ai_asset_alerts
    op.alter_column('ai_asset_alerts', 'asset_id',
        existing_type=sa.BigInteger(),
        nullable=False)