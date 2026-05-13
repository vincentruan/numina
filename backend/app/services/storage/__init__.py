# Re-export shim — implementations moved to packages/storage/
from packages.storage.base import (  # noqa: F401
    StorageAuthError,
    StorageBackend,
    StorageConflictError,
    StorageConnectionError,
    StorageError,
    StorageRateLimitError,
)
