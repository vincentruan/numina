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

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, exports table
