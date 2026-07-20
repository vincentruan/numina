"""migrate payment_records.amount Float -> Numeric(18,2)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-20

Review follow-up (#9): PaymentRecord.amount was Float (silent precision loss on
payment history; record_payment passes a Decimal that SQLAlchemy silently
coerced). Migrate to NUMERIC(18,2) to mirror WishSavingsLog + the liability
money fields. Activity.amount stays Float (cross-entity display snapshot, not a
ledger; asset model is still Float so a Decimal Activity would reverse-coerce).
"""

import sqlalchemy as sa
from alembic import op

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('payment_records', schema=None) as batch_op:
        batch_op.alter_column(
            'amount',
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('payment_records', schema=None) as batch_op:
        batch_op.alter_column(
            'amount',
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )
