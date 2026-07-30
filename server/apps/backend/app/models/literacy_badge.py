# Re-export shim — implementation in packages/db/models/literacy_badge.py
from packages.db.models.literacy_badge import (
    LiteracyBadge,
    LiteracyBadgeDefinition,
)

__all__ = ["LiteracyBadge", "LiteracyBadgeDefinition"]
