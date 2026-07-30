"""Re-export shim — implementation moved to packages/domain/literacy/service.py.

Backend consumers can import from here or directly from packages.domain.
The scheduler_worker imports from packages.domain to avoid cross-app imports.
"""

from packages.domain.literacy.service import (
    _aggregate_signals,
    _build_fallback_narrative,
    _build_report_narrative,
    _get_age_group,
    _sunday_of,
    generate_weekly_report,
)

__all__ = [
    "_aggregate_signals",
    "_build_fallback_narrative",
    "_build_report_narrative",
    "_get_age_group",
    "_sunday_of",
    "generate_weekly_report",
]
