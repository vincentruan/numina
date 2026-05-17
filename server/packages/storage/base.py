"""Abstract storage backend interface and error hierarchy."""
from abc import ABC, abstractmethod


class StorageError(Exception):
    """Base class for all storage backend errors."""


class StorageRateLimitError(StorageError):
    """Raised when a remote backend rate limit is hit."""

    def __init__(self, message: str = "Rate limit exceeded", reset_at: int | None = None):
        super().__init__(message)
        self.reset_at = reset_at  # Unix epoch seconds when limit resets


class StorageConflictError(StorageError):
    """Raised when a remote backend reports a conflict (e.g. stale SHA) after max retries."""


class StorageConnectionError(StorageError):
    """Raised on network/transport failures connecting to a remote backend."""


class StorageAuthError(StorageError):
    """Raised when authentication to a remote backend fails (401/403)."""


class StorageBackend(ABC):
    """Abstract interface for file storage backends."""

    @property
    def write_delay_range(self) -> tuple[float, float]:
        return (0.2, 1.0)

    @abstractmethod
    async def save(self, content: bytes, filename: str, date_dir: str, family_id: str = "", user_id: str = "") -> str:
        """Persist file content and return the remote_path string."""

    @abstractmethod
    async def delete(self, remote_path: str) -> None:
        """Delete a file at the given remote_path."""

    @abstractmethod
    def get_url(self, remote_path: str) -> str:
        """Return a URL suitable for accessing/previewing the file."""
