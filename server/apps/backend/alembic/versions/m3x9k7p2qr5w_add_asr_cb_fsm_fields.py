"""add ASR circuit breaker FSM fields

Revision ID: m3x9k7p2qr5w
Revises: 1fnymxs8brc2
Create Date: 2026-09-15

Add the 6 missing FSM columns to asr_provider_configs so it is fully
compatible with CircuitBreakerMixin (the other 3 columns already existed).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from packages.db.session import UTCDateTime

revision: str = "m3x9k7p2qr5w"
down_revision: str | None = "1fnymxs8brc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("asr_provider_configs") as batch_op:
        batch_op.add_column(
            sa.Column("circuit_reason", sa.String(30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("recovery_schedule", sa.String(100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_failure_type", sa.String(30), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "half_open_success_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "half_open_failure_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("half_open_window_start", UTCDateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("asr_provider_configs") as batch_op:
        batch_op.drop_column("half_open_window_start")
        batch_op.drop_column("half_open_failure_count")
        batch_op.drop_column("half_open_success_count")
        batch_op.drop_column("last_failure_type")
        batch_op.drop_column("recovery_schedule")
        batch_op.drop_column("circuit_reason")
