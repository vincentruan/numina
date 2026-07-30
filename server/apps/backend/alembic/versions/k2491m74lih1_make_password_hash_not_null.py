"""make password_hash NOT NULL (all users including children require a password)

Revision ID: k2491m74lih1
Revises: j1380l63khg0
Create Date: 2026-05-10 00:00:00.000000

Changes:
- users.password_hash: nullable=True → nullable=False
  Pre-condition: all rows must already have a non-NULL password_hash.
  Run seed_data.py --reset before applying this migration on a dev/test DB.
  On production, backfill any NULL rows first.
"""

import sqlalchemy as sa
from alembic import op

revision = 'k2491m74lih1'
down_revision = 'j1380l63khg0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail fast if any NULL rows remain — prevents silent data corruption.
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT COUNT(*) FROM users WHERE password_hash IS NULL"))
    null_count = result.scalar()
    if null_count:
        raise RuntimeError(
            f"Cannot apply migration: {null_count} user(s) have NULL password_hash. "
            "Backfill passwords before running this migration."
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(255),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(255),
            nullable=True,
        )
