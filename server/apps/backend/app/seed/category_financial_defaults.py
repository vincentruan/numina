"""Backward-compatible shim — implementation moved to app/bootstrap/category_financial_defaults.py."""
from apps.backend.app.bootstrap.category_financial_defaults import (
    DEFAULTS,
    bootstrap_category_financial_defaults,
)

seed_category_financial_defaults = bootstrap_category_financial_defaults

__all__ = ["DEFAULTS", "seed_category_financial_defaults"]
