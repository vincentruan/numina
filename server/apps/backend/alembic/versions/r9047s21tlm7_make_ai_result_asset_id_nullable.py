"""make ai result asset_id nullable

Revision ID: r9047s21tlm7
Revises: q8046r20skm6
Create Date: 2026-05-17

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'r9047s21tlm7'
down_revision = 'q8046r20skm6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make asset_id nullable in ai_asset_alerts / ai_disposal_suggestions /
    # ai_spending_leaks. Use batch_alter_table for SQLite compatibility (bare
    # op.alter_column emits `ALTER COLUMN` which SQLite rejects). Guard each so
    # it's a no-op when the column is already nullable (fresh-DB from models).
    bind = op.get_bind()

    def _make_nullable(table: str) -> None:
        if not bind.dialect.has_table(bind, table):
            return
        cols = {c['name']: c for c in bind.dialect.get_columns(bind, table)}
        if 'asset_id' not in cols:
            return
        if cols['asset_id'].get('nullable', False):
            return  # already nullable
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column('asset_id', existing_type=sa.BigInteger(), nullable=True)

    _make_nullable('ai_asset_alerts')
    _make_nullable('ai_disposal_suggestions')
    _make_nullable('ai_spending_leaks')


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