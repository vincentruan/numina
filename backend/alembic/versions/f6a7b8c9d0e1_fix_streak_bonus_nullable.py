"""fix_streak_bonus_nullable

Make coin_transactions.streak_bonus NOT NULL DEFAULT 0 for consistency
with chore_instances.streak_bonus. Fill existing NULLs with 0.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fill existing NULLs with 0 before making column NOT NULL
    op.execute(
        "UPDATE coin_transactions SET streak_bonus = 0 WHERE streak_bonus IS NULL"
    )
    with op.batch_alter_table('coin_transactions') as batch_op:
        batch_op.alter_column(
            'streak_bonus',
            existing_type=sa.Integer(),
            nullable=False,
            server_default='0',
        )


def downgrade() -> None:
    with op.batch_alter_table('coin_transactions') as batch_op:
        batch_op.alter_column(
            'streak_bonus',
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )