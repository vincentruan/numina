# server/CLAUDE.md

Server workspace guidance. All Python apps (`backend`, `agent`, `scheduler_worker`) and shared packages (`core`, `db`, `domain`, `security`, `storage`, `stream_bridge`) live here in a single `uv` workspace.

## Quality Commands

Run all commands from `server/` (the uv workspace root). Each tool command takes a path argument to scope to a specific module:

```bash
uv run ruff check <path>               # lint
uv run ruff check <path> --fix         # lint + auto-fix
uv run ruff format <path>              # format (only files you touch)
uv run mypy <path> [--explicit-package-bases]  # type check
uv run pytest tests/<module>/ -v       # run module tests
```

| Module | Test root | mypy flag |
|--------|-----------|-----------|
| `apps/backend` | `tests/backend/` | — |
| `apps/agent` | `tests/agent/` | `--exclude vendor` |
| `apps/scheduler_worker` | `tests/scheduler_worker/` | `--explicit-package-bases` |
| `packages/core` | `tests/packages/core/` | `--explicit-package-bases` |
| `packages/db` | `tests/packages/db/` | `--explicit-package-bases` |
| `packages/domain` | `tests/packages/domain/` | `--explicit-package-bases` |
| `packages/security` | `tests/packages/security/` | `--explicit-package-bases` |
| `packages/storage` | `tests/packages/storage/` | `--explicit-package-bases` |

`pytest` from `server/` runs the full suite (`testpaths = ["tests"]` in `pyproject.toml`). Each test gets a fresh in-memory SQLite DB.

Run `alembic` from `server/apps/backend/`:

```bash
cd apps/backend
uv run alembic upgrade head              # apply all pending migrations
uv run alembic revision --autogenerate -m "description"  # create migration
uv run alembic downgrade -1              # revert last migration
```

## Tooling

| Tool | Purpose | Config |
|------|---------|--------|
| **uv** | Package manager. `uv add`/`uv remove` — never `pip install` | `server/pyproject.toml` |
| **ruff** | Lint + format | `[tool.ruff]` — rules: E, F, I, UP |
| **mypy** | Type checker | `python_version = "3.12"`, `ignore_missing_imports = true`, `plugins = ["pydantic.mypy"]` |
| **pytest** | Test runner | `asyncio_mode = "auto"` for agent tests |

## Import Direction

Dependencies flow one-way: `apps/` → `packages/`.

- `apps/` modules **must not** import sibling apps (`from apps.backend import ...` inside agent code is forbidden). Use `packages/` for shared logic, or HTTP via `core/backend_client.py` for agent→backend.
- `packages/` modules **must not** import `apps/`.
- `packages/` subpackages (`core`, `db`, `domain`, `security`, `storage`, `stream_bridge`) must not import each other (except `domain` → `db` for ORM models).

## Patterns

### Pydantic v2

```python
from pydantic import BaseModel, ConfigDict, field_validator

class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("field_name")
    @classmethod
    def validate_field(cls, v: str) -> str:
        return v.strip()

# Use model_validate (not from_orm)
obj = MySchema.model_validate(orm_instance)
```

### Code Style

- **Import order:** stdlib → third-party → local, blank line between groups
- **Type annotations:** `str | None`, `list[str]` (Python 3.10+ union syntax)
- **Private helpers:** leading underscore `_to_response(...)`

## Cross-Cutting Conventions

### URL Style — No Trailing Slash, No Redirects

All API endpoints must respond with 200 directly — no 307 redirects.

`redirect_slashes=False` is set in `app/main.py`. Router root-path decorators must use `""` not `"/"`:

```python
# ✅ Correct
@router.get("")
@router.post("")

# ❌ Wrong — FastAPI issues 307 redirect, breaks HTTPS behind nginx
@router.get("/")
```

### API Return Code Conventions

- **Auth endpoints return 200** — `register`, `login`, `join-family` return `TokenResponse` with status 200, not 201.
- **Asset/Liability POST endpoints return 201** — explicit `status_code=201` on router decorators.
- `TokenResponse` does not include `user` — frontend must call `/auth/me` after login.

### Error Messages

Backend HTTP exceptions use Chinese detail strings: `raise HTTPException(status_code=404, detail="Asset not found")`. Note: actual code uses Chinese strings (e.g., `"资产不存在"`) — this documents the pattern, not the literal string to use.

Backend uses `AppError` (`app/errors/exceptions.py`) with `ErrorCode` enum. The global `error_handlers.py` catches `AppError`, `RequestValidationError`, `StarletteHTTPException`, and `StorageError`, returning a unified JSON envelope: `{"code": "ERROR_CODE", "message": "localized message", "data": null, "request_id": "..."}`. Language is selected via `Accept-Language` header.

### Snowflake ID Serialization

All response schemas containing IDs inherit from `SnowflakeBase` (defined in `apps/backend/app/schemas/base.py`). IDs defined as `int` in schemas are automatically serialized as `str` in JSON output (JS loses precision on integers > 2⁵³). See `apps/backend/CLAUDE.md` §Snowflake ID Serialization for the full pattern.

### Scheduler Worker Conventions

All `scheduler.add_job()` calls must include `max_instances=1`, `coalesce=True`, `replace_existing=True`. See `apps/scheduler_worker/CLAUDE.md` for details.

### Run Commands from Workspace Root

All quality commands and `uvicorn` must be invoked from `server/`, not from individual module directories.

### Logging

1. **Use `get_logger`** — `from packages.core.logging import get_logger; logger = get_logger(__name__)`. Never call `logging.getLogger()` directly for module loggers.
2. **Log levels by semantics** — DEBUG (dev detail), INFO (important events), WARNING (recoverable anomaly), ERROR (operation failed), CRITICAL (system failure).
3. **Parameterized logging** — `logger.info("msg: %s", val)`. Never f-strings in log calls.
4. **Preserve traceback** — In `except` blocks: `logger.exception("context: %s", detail)` or `logger.warning("context: %s", detail, exc_info=True)`. Never `logger.error("msg: %s", e)`.
5. **Relevant context only** — Log `task_id`, `family_id`, `duration_ms`, `status` when the event needs them. Do not over-log.
6. **No sensitive data** — Never log passwords, tokens, API keys, or Authorization headers.
7. **Control volume** — In high-frequency paths (loops, streaming, polling), use DEBUG level or sampling.
8. **Rotation managed by `setup_logging()`** — `RotatingFileHandler` (size) or `TimedRotatingFileHandler` (time) based on `LOG_ROTATION_MODE`. Do not add custom file handlers.
9. **Docker services** — Log to stdout + file; rotation is managed by the Python handler.
10. **No `print()` in server code** — CLI scripts (`scripts/`, `reconcile/__main__.py`) may use `print()`.

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, project overview
- Module CLAUDE.md files: [`apps/backend`](./apps/backend/CLAUDE.md), [`apps/agent`](./apps/agent/CLAUDE.md), [`apps/scheduler_worker`](./apps/scheduler_worker/CLAUDE.md), [`packages/core`](./packages/core/CLAUDE.md), [`packages/db`](./packages/db/CLAUDE.md), [`packages/domain`](./packages/domain/CLAUDE.md), [`packages/security`](./packages/security/CLAUDE.md), [`packages/storage`](./packages/storage/CLAUDE.md)
- [`docs/solutions/`](../docs/solutions/) — documented solutions to past problems
