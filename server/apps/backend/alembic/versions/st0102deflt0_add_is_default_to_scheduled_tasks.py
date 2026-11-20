"""add is_default column and backfill defaults for existing families

Revision ID: st0102deflt0
Revises: abc123feature001
Create Date: 2026-11-20
"""

from collections.abc import Sequence
from datetime import UTC

import sqlalchemy as sa
from alembic import op

revision: str = "st0102deflt0"
down_revision: str | None = "abc123feature001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirror of packages.core.scheduled_tasks.SYSTEM_SCHEDULED_TASK_DEFAULTS.
# Hard-coded here so the migration is stable even if code defaults change later.
_DEFAULT_CRONS: dict[str, str] = {
    "asset-report": "35 8 * * *",
    "literacy-weekly-report": "0 2 * * 0",
}


def _compute_next_run_at(cron: str):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from croniter import croniter

    tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(tz)
    nxt = croniter(cron, now).get_next(datetime)
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=tz)
    return nxt.astimezone(UTC)


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in bind.dialect.get_columns(bind, table)}
    return col in cols


def upgrade() -> None:
    # auto-migrate may have added this column at app startup; do not duplicate it.
    if not _has_column("scheduled_tasks", "is_default"):
        op.add_column(
            "scheduled_tasks",
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    # Backfill: for every family that has no scheduled_tasks rows, insert
    # the system defaults so DB is authoritative from the start.
    from packages.core.snowflake import next_id

    bind = op.get_bind()
    families = bind.execute(
        sa.text("SELECT id FROM families")
    ).fetchall()

    for (family_id,) in families:
        has_tasks = bind.execute(
            sa.text(
                "SELECT 1 FROM scheduled_tasks WHERE family_id = :fid LIMIT 1"
            ),
            {"fid": family_id},
        ).first()
        if has_tasks is not None:
            continue

        for skill_id, cron in _DEFAULT_CRONS.items():
            next_run = _compute_next_run_at(cron)
            bind.execute(
                sa.text(
                    "INSERT INTO scheduled_tasks "
                    "(id, family_id, skill_id, cron_expression, is_enabled, "
                    "is_default, next_run_at, status, created_at, updated_at) "
                    "VALUES (:id, :fid, :sid, :cron, TRUE, TRUE, :nxt, 'idle', :now, :now)"
                ),
                {
                    "id": next_id(),
                    "fid": family_id,
                    "sid": skill_id,
                    "cron": cron,
                    "nxt": next_run,
                    "now": next_run,
                },
            )


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "is_default")
