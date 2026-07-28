# Re-export shim — implementation in packages/db/models/literacy_report.py
from packages.db.models.literacy_report import LiteracyWeeklyReport  # noqa: F401

__all__ = ["LiteracyWeeklyReport"]
