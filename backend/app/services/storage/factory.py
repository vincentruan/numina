"""Storage backend factory — returns a backend instance by type string."""
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorageBackend

# Singleton instances keyed by a cache key string
_instances: dict[str, StorageBackend] = {}


def get_local_backend(upload_dir: str) -> LocalStorageBackend:
    """Return a singleton LocalStorageBackend for the given upload_dir."""
    key = f"local:{upload_dir}"
    if key not in _instances:
        _instances[key] = LocalStorageBackend(upload_dir)
    return _instances[key]  # type: ignore[return-value]


def get_backend_for_type(backend_type: str, config: dict) -> StorageBackend:
    """Instantiate and return a storage backend by type and config dict.

    Args:
        backend_type: One of 'local', 'github', 'webdav'.
        config: Decrypted config dict for the backend.

    Returns:
        StorageBackend instance.

    Raises:
        ValueError: If backend_type is not registered.
    """
    if backend_type == "local":
        upload_dir = config.get("upload_dir", "./data/uploads")
        return get_local_backend(upload_dir)

    # GitHub and WebDAV are registered lazily to avoid import-time httpx dependency
    if backend_type == "github":
        from app.services.storage.github import GitHubStorageBackend  # noqa: PLC0415
        return GitHubStorageBackend(
            token=config["token"],
            repo=config["repo"],
            branch=config.get("branch", "main"),
        )

    if backend_type == "webdav":
        from app.services.storage.webdav import WebDAVStorageBackend  # noqa: PLC0415
        return WebDAVStorageBackend(
            base_url=config["url"],
            username=config["username"],
            password=config["password"],
            verify_ssl=config.get("verify_ssl", True),
        )

    raise ValueError(f"未知存储后端类型: {backend_type}")


def reset_instances() -> None:
    """Clear all cached backend instances. Used in tests."""
    _instances.clear()
