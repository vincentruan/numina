# storage/CLAUDE.md

Module-specific guidance for the pluggable file storage backends package.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `server/`:

```bash
uv run ruff check packages/storage/        # lint
uv run ruff check packages/storage/ --fix  # lint + auto-fix
uv run ruff format packages/storage/       # format (only files you touch)
uv run mypy packages/storage/ --explicit-package-bases  # type check
uv run pytest packages/storage/ -v         # run tests
```

## Tooling

- **uv:** package manager. Use `uv add`/`uv remove`. Never `pip install`.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`.
- **mypy:** type checker. Requires `--explicit-package-bases` to avoid namespace collision with other `packages/` directories.

## Key Invariants

1. **Import direction** — `packages/storage` must never import from `apps/`. Dependency flow is one-way: `apps/` → `packages/`. Violating this creates circular imports.
2. **Always use the factory** — obtain backends via `get_backend_for_type()` or `get_local_backend()`. Never instantiate `LocalStorageBackend`, `GitHubStorageBackend`, `WebDAVStorageBackend`, or any other backend class directly. The factory manages singleton instances and configuration.
3. **Catch `StorageError` at the app boundary** — `StorageError` and its subclasses (`StorageRateLimitError`, `StorageConflictError`) must be caught at the app layer (router or job) and converted to appropriate HTTP responses or logged. Never let storage exceptions propagate unwrapped to API responses.

## Don't Do

- **Don't import from `apps/`** — import direction rule: `packages/` must not import sibling `apps/`. Use other `packages/` for shared logic.
- **Don't instantiate backend classes directly** — use `get_backend_for_type()` or `get_local_backend()`.
- **Don't let `StorageError` propagate to API responses** — catch at the app boundary and handle explicitly.
- **Don't run commands from the package directory** — quality commands must be invoked from `server/`, not from `packages/storage/`.

## Modules

| File | Purpose |
|------|---------|
| `base.py` | Abstract `StorageBackend` ABC + the `StorageError` exception hierarchy (`StorageRateLimitError`, `StorageConflictError`, `StorageConnectionError`, `StorageAuthError`) |
| `factory.py` | `get_backend_for_type(type_str)` and `get_local_backend()` — singleton lookup. Always use these |
| `local.py` | `LocalStorageBackend` — files on local disk |
| `github.py` | `GitHubStorageBackend` — files as GitHub repo contents |
| `webdav.py` | `WebDAVStorageBackend` — files on a WebDAV server |
| `config_crypto.py` | `decrypt_config(text)` / `encrypt_config(dict)` — Fernet encryption for per-family backend config (key from `STORAGE_ENCRYPTION_KEY`, falls back to `SECRET_KEY` derivation with a warning) |

Backend configuration is stored encrypted in the database (model: `packages/db/models/storage_backend.py`). The factory decrypts via `config_crypto.decrypt_config` before instantiating a backend.

## Backends

| Backend | Type string | Use case |
|---------|-------------|---------|
| `LocalStorageBackend` | `"local"` | Default; stores files on local disk |
| `GitHubStorageBackend` | `"github"` | Stores files as GitHub repo contents |
| `WebDAVStorageBackend` | `"webdav"` | Stores files on a WebDAV server |

## Patterns

### Obtaining a backend

```python
# ✅ Correct — use the factory
from packages.storage.factory import get_backend_for_type, get_local_backend

backend = get_backend_for_type("local")   # by type string
backend = get_local_backend()             # convenience for local

# ❌ Wrong — never instantiate directly
from packages.storage.backends.local import LocalStorageBackend
backend = LocalStorageBackend(...)  # bypasses factory singleton management
```

### Error handling at the app boundary

```python
from packages.storage.exceptions import StorageError

try:
    await backend.upload(path, data)
except StorageError as e:
    raise HTTPException(status_code=502, detail=str(e))
```

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, exports table
