# packages/storage

Pluggable file storage backends for the Numina server monorepo. Supports local filesystem, GitHub repository, and WebDAV backends behind a common `StorageBackend` interface. Apps obtain backends via the factory functions — never instantiate backend classes directly.

## Exports

| Symbol | Type | Description |
|--------|------|-------------|
| `StorageBackend` | abstract class | Common interface all backends implement |
| `StorageError` | exception | Base class for all storage errors |
| `StorageRateLimitError` | exception | Raised when a remote backend hits a rate limit |
| `StorageConflictError` | exception | Raised on write conflict after max retries |
| `get_backend_for_type` | function | Factory — returns a backend instance by type string and config dict |
| `get_local_backend` | function | Factory — returns a singleton `LocalStorageBackend` for a given upload dir |
