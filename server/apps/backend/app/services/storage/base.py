# Re-export shim — implementation moved to packages/storage/base.py
from packages.storage.base import (  # noqa: F401
    StorageAuthError,
    StorageBackend,
    StorageConflictError,
    StorageConnectionError,
    StorageError,
    StorageRateLimitError,
)
