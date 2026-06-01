"""Backward-compatible shim — implementation moved to app/bootstrap/currencies.py."""
from apps.backend.app.bootstrap.currencies import (
    FAVORITE_CURRENCIES,
    bootstrap_currencies,
)

seed_currencies = bootstrap_currencies

__all__ = ["FAVORITE_CURRENCIES", "seed_currencies"]
