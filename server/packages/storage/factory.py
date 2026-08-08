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
        from packages.storage.github import GitHubStorageBackend
        # Compose repo from repo_owner/repo_name (new schema) or use repo directly (legacy)
        repo = config.get("repo") or f"{config.get('repo_owner', '')}/{config.get('repo_name', '')}"
        token = config.get("token", "")
        # Include a token hash in the cache key so credential rotation invalidates
        # the cached instance.
        token_hash = hash(token) & 0xFFFFFFFF
        key = f"github:{repo}:{config.get('branch', 'main')}:{token_hash}"
        if key not in _instances:
            _instances[key] = GitHubStorageBackend(
                token=token,
                repo=repo,
                branch=config.get("branch", "main"),
            )
        return _instances[key]  # type: ignore[return-value]

    if backend_type == "webdav":
        from packages.storage.webdav import WebDAVStorageBackend
        # Accept both url (legacy) and base_url (new schema)
        url = config.get("url") or config.get("base_url", "")
        password = config.get("password", "")
        # Include a password hash in the cache key so credential rotation invalidates
        # the cached instance.
        password_hash = hash(password) & 0xFFFFFFFF
        key = f"webdav:{url}:{config.get('username')}:{password_hash}"
        if key not in _instances:
            _instances[key] = WebDAVStorageBackend(
                base_url=url,
                username=config["username"],
                password=password,
                verify_ssl=config.get("verify_ssl", True),
            )
        return _instances[key]  # type: ignore[return-value]

    raise ValueError(f"未知存储后端类型: {backend_type}")


def reset_instances() -> None:
    """Clear all cached backend instances. Used in tests."""
    _instances.clear()
