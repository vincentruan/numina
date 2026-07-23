"""migrate asset-side money fields Float -> Numeric(18,2)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-20

Asset-side money migration (P2): completes the money ledger unification
started on the liability side. Migrates 9 Float money columns across 3
tables to NUMERIC(18,2):

- assets.purchase_price / current_value / annual_maintenance_cost / target_daily_cost
- asset_valuations.value
- asset_lifecycle_events.sell_price / sell_fee

asset.interest_rate stays Float (percentage, mirrors liability.interest_rate).
Activity.amount stays Float (cross-entity display snapshot; see c3d4e5f6a7b8).

Decimal in compute / str on wire / float at aggregation boundaries — see
docs/solutions/best-practices/money-decimal-str-float-split.md.
"""

import sqlalchemy as sa
from alembic import op

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column(
            'purchase_price',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'current_value',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'annual_maintenance_cost',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'target_daily_cost',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )

    with op.batch_alter_table('asset_valuations', schema=None) as batch_op:
        batch_op.alter_column(
            'value',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=False,
        )

    with op.batch_alter_table('asset_lifecycle_events', schema=None) as batch_op:
        batch_op.alter_column(
            'sell_price',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'sell_fee',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('asset_lifecycle_events', schema=None) as batch_op:
        batch_op.alter_column(
            'sell_fee',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'sell_price',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )

    with op.batch_alter_table('asset_valuations', schema=None) as batch_op:
        batch_op.alter_column(
            'value',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )

    with op.batch_alter_table('assets', schema=None) as batch_op:
        batch_op.alter_column(
            'target_daily_cost',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'annual_maintenance_cost',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'current_value',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'purchase_price',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
