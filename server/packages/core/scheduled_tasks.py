"""System-wide defaults for user-visible scheduled tasks.

Cron expressions are authored in Asia/Shanghai (see packages.core.cron).
These defaults mirror the legacy APScheduler jobs so migration does not change
when reports are generated.
"""

from typing import TypedDict


class ScheduledTaskDefault(TypedDict):
    cron_expression: str
    is_enabled: bool


SYSTEM_SCHEDULED_TASK_DEFAULTS: dict[str, ScheduledTaskDefault] = {
    "asset-report": {
        "cron_expression": "35 8 * * *",  # Daily 08:35 (legacy auto_report_job)
        "is_enabled": True,
    },
    "literacy-weekly-report": {
        "cron_expression": "0 2 * * 0",  # Sunday 02:00 (legacy literacy job)
        "is_enabled": True,
    },
}
