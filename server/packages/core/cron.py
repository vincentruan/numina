"""Cron expression helpers shared by the scheduled-task API and polling job.

Cron expressions are authored and interpreted in the family's local timezone
(Asia/Shanghai) so "0 9 * * *" means 09:00 Beijing time regardless of where the
server runs. Persisted timestamps are always UTC.
"""

from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

SCHEDULE_TZ = ZoneInfo("Asia/Shanghai")

# Standard 5-field cron: minute hour day-of-month month day-of-week
_CRON_FIELD_COUNT = 5


def is_valid_cron(expression: str) -> bool:
    """Return True when ``expression`` is a valid 5-field cron pattern."""
    fields = expression.split()
    if len(fields) != _CRON_FIELD_COUNT:
        return False
    try:
        return bool(croniter.is_valid(expression))
    except (CroniterBadCronError, CroniterBadDateError, ValueError):
        return False


def compute_next_run_at(expression: str, *, after: datetime | None = None) -> datetime:
    """Return the next fire time for ``expression`` as an aware UTC datetime.

    ``after`` defaults to now. It is interpreted as-is when aware and assumed to
    be UTC when naive.
    """
    base = after or datetime.now(UTC)
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)

    local_base = base.astimezone(SCHEDULE_TZ)
    next_local = cast(datetime, croniter(expression, local_base).get_next(datetime))
    if next_local.tzinfo is None:
        next_local = next_local.replace(tzinfo=SCHEDULE_TZ)
    return next_local.astimezone(UTC)
