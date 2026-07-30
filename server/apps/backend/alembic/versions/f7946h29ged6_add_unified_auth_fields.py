"""add unified auth fields

Revision ID: f7946h29ged6
Revises: d6835g18fdc5
Create Date: 2026-04-29 14:00:00.000000

Adds:
- users.numeric_pin_hash, numeric_pin_fail_count, numeric_pin_locked_until (adult PIN)
- users.second_factor_type, second_factor_enabled (second factor config)
- device_sessions.browser_fingerprint (device trust by fingerprint)
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7946h29ged6"
down_revision: str | None = "d6835g18fdc5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("numeric_pin_hash", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("numeric_pin_fail_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("numeric_pin_locked_until", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("second_factor_type", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("second_factor_enabled", sa.Boolean(), nullable=False, server_default="0"))

    with op.batch_alter_table("device_sessions") as batch_op:
        batch_op.add_column(sa.Column("browser_fingerprint", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_sessions") as batch_op:
        batch_op.drop_column("browser_fingerprint")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("second_factor_enabled")
        batch_op.drop_column("second_factor_type")
        batch_op.drop_column("numeric_pin_locked_until")
        batch_op.drop_column("numeric_pin_fail_count")
        batch_op.drop_column("numeric_pin_hash")
