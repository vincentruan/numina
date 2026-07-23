"""Drop legacy notification columns from reminders

Revision ID: b8d9e0f1a2b3
Revises: 1fnymxs8brc2
Create Date: 2026-07-17

reminders.notified_channels and reminders.send_retry_count were migrated to
the reminder_notifications table (see ac070c6b7aaf_drop_migrated_columns on the
sibling branch). The current branch's DB never received that drop, so the
columns linger as NOT NULL while the ORM model (packages/db/models/reminder.py)
no longer writes them — causing reminder_job to fail with
"NOT NULL constraint failed: reminders.notified_channels" on every insert.

This migration drops the two legacy columns to align the schema with the model.
It is idempotent (guarded by _has_column) so it is safe on DBs that already
ran ac070c6b7aaf (the columns will already be absent).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "b8d9e0f1a2b3"
down_revision: str | None = "1fnymxs8brc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    if not _has_table("reminders"):
        return
    # batch_alter_table handles SQLite's inability to drop columns with
    # constraints directly (table recreation) and is a no-op-friendly path on PG.
    with op.batch_alter_table("reminders", schema=None) as batch_op:
        if _has_column("reminders", "notified_channels"):
            batch_op.drop_column("notified_channels")
        if _has_column("reminders", "send_retry_count"):
            batch_op.drop_column("send_retry_count")


def downgrade() -> None:
    # Restore the legacy columns. Defaults match the original
    # b1c2d3e4f5a6_phase4_smart_reminders definitions.
    with op.batch_alter_table("reminders", schema=None) as batch_op:
        if not _has_column("reminders", "send_retry_count"):
            batch_op.add_column(
                sa.Column("send_retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False)
            )
        if not _has_column("reminders", "notified_channels"):
            batch_op.add_column(
                sa.Column("notified_channels", sa.Text(), server_default=sa.text("'[]'"), nullable=False)
            )
