"""Backward-compatible shim — implementation moved to app/bootstrap/categories.py."""
from apps.backend.app.bootstrap.categories import (
    SYSTEM_CATEGORIES,
    bootstrap_categories,
)

seed_categories = bootstrap_categories

__all__ = ["SYSTEM_CATEGORIES", "seed_categories"]
