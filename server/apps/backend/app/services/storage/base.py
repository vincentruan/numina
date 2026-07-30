# Re-export shim — implementation moved to packages/storage/base.py
from packages.storage.base import (
    StorageAuthError,
    StorageBackend,
    StorageConflictError,
    StorageConnectionError,
    StorageError,
    StorageRateLimitError,
)
