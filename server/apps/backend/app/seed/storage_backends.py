"""Backward-compatible shim — implementation moved to app/bootstrap/storage_backends.py."""
from apps.backend.app.bootstrap.storage_backends import bootstrap_storage_backends

seed_storage_backends = bootstrap_storage_backends

__all__ = ["seed_storage_backends"]
