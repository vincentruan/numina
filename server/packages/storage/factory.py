"""Storage backend factory — returns a backend instance by type string."""
from packages.storage.base import StorageBackend
from packages.storage.local import LocalStorageBackend

# Singleton instances keyed by a cache key string
_instances: dict[str, StorageBackend] = {}


def get_local_backend(upload_dir: str) -> LocalStorageBackend:
    """Return a singleton LocalStorageBackend for the given upload_dir."""
    key = f"local:{upload_dir}"
    if key not in _instances:
        _instances[key] = LocalStorageBackend(upload_dir)
    return _instances[key]  # type: ignore[return-value]


def get_backend_for_type(backend_type: str, config: dict) -> StorageBackend:
    """Instantiate and return a storage backend by type and config dict."""
    if backend_type == "local":
        upload_dir = config.get("upload_dir", "./data/uploads")
        return get_local_backend(upload_dir)

    if backend_type == "github":
        from packages.storage.github import GitHubStorageBackend  # noqa: PLC0415
        key = f"github:{config.get('repo')}:{config.get('branch', 'main')}"
        if key not in _instances:
            _instances[key] = GitHubStorageBackend(
                token=config["token"],
                repo=config["repo"],
                branch=config.get("branch", "main"),
            )
        return _instances[key]  # type: ignore[return-value]

    if backend_type == "webdav":
        from packages.storage.webdav import WebDAVStorageBackend  # noqa: PLC0415
        key = f"webdav:{config.get('url')}:{config.get('username')}"
        if key not in _instances:
            _instances[key] = WebDAVStorageBackend(
                base_url=config["url"],
                username=config["username"],
                password=config["password"],
                verify_ssl=config.get("verify_ssl", True),
            )
        return _instances[key]  # type: ignore[return-value]

    raise ValueError(f"未知存储后端类型: {backend_type}")


def reset_instances() -> None:
    """Clear all cached backend instances. Used in tests."""
    _instances.clear()
