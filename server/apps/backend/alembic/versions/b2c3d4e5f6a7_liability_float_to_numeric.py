"""migrate liability money columns Float → Numeric(18,2)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20

Plan B follow-up (T8b): liability original_amount/remaining_amount/
monthly_payment were Float (currency precision risk). Migrate to NUMERIC(18,2)
to match the money-as-str convention (Decimal in Python, str on the wire).
interest_rate stays Float (it's a percentage, not a money amount).
"""

import sqlalchemy as sa
from alembic import op

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot ALTER COLUMN type directly; use batch_alter_table so
    # Alembic performs the table-recreate dance transparently. The existing
    # Float values coerce cleanly to NUMERIC(18,2).
    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.alter_column(
            'original_amount',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'remaining_amount',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'monthly_payment',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.alter_column(
            'monthly_payment',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'remaining_amount',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'original_amount',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )
