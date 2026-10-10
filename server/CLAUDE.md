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

## Solutions (Backend/Agent Lessons Learned)

Check these docs before working in `server/` — they document verified fixes for known pitfalls.

### Architecture Patterns

| Doc | Topic |
|-----|-------|
| [`deerflow-adapter-decoupling`](../docs/solutions/architecture-patterns/deerflow-adapter-decoupling-stream-bridge-subclass.md) | DeerFlow adapter 解耦 — stream_bridge 提取 |
| [`mcp-caller-bound-principal`](../docs/solutions/architecture-patterns/mcp-caller-bound-principal-2026-05-31.md) | MCP 调用者绑定身份 (防 confused-deputy) |
| [`mcp-chat-adapter`](../docs/solutions/architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md) | MCP Chat Adapter 分层设计 |

### Best Practices

| Doc | Topic |
|-----|-------|
| [`altcha-captcha`](../docs/solutions/best-practices/altcha-captcha-best-practices-2026-04-03.md) | ALTCHA 验证码最佳实践 |
| [`cache-key-granularity`](../docs/solutions/best-practices/cache-key-granularity-matches-data-scope-2026-04-27.md) | 缓存键粒度匹配数据范围 |
| [`db-check-constraint-pydantic-sync`](../docs/solutions/best-practices/db-check-constraint-pydantic-regex-sync.md) | DB Check 约束与 Pydantic regex 同步 |
| [`fastapi-pydantic-validation-i18n`](../docs/solutions/best-practices/fastapi-pydantic-validation-error-localization-2026-04-16.md) | Pydantic v2 验证错误国际化 |
| [`jti-revocation-db-persistence`](../docs/solutions/best-practices/jti-revocation-requires-db-persistence-2026-04-27.md) | JWT JTI 撤销必须持久化到 DB |
| [`logging-config`](../docs/solutions/best-practices/logging-config.md) | 日志配置 (轮转/归档/保留) |
| [`redis-fail-fast`](../docs/solutions/best-practices/redis-fail-fast-strategy.md) | Redis 缓存快速失败策略 |
| [`file-storage-abstraction`](../docs/solutions/best-practices/file-storage-abstraction-2026-04-10.md) | 可插拔文件存储抽象 |
| [`security-protection`](../docs/solutions/best-practices/security-protection.md) | 安全防护 (速率限制/缓存/暴力破解) |
| [`security-audit`](../docs/solutions/best-practices/security-audit.md) | 安全审计 (日志/文件上传验证) |

### Integration Issues

| Doc | Topic |
|-----|-------|
| [`deerflow-integration-historical`](../docs/solutions/integration-issues/deerflow-integration-historical-lessons.md) | DeerFlow 历史集成教训 (adapter/harness) |
| [`deerflow-glm5-thinking`](../docs/solutions/integration-issues/deerflow-glm5-thinking-provider-endpoint-mismatch-2026-05-16.md) | GLM-5 深度思考 provider/endpoint 不匹配 |
| [`thinking-block-leaking`](../docs/solutions/integration-issues/thinking-block-content-leaking-into-titles.md) | Thinking block 内容泄漏到标题 |
| [`mcp-cache-asyncio-lock`](../docs/solutions/integration-issues/mcp-cache-asyncio-lock-threading-deadlock.md) | MCP 缓存 asyncio.Lock 线程死锁 |
| [`asr-wer-tokenization`](../docs/solutions/integration-issues/asr-wer-whitespace-stripping-tokenization.md) | ASR WER 空格剥离/分词 |
| [`stream-closure-fix`](../docs/solutions/integration-issues/stream-closure-fix-2026-06-15.md) | AI Chat 流关闭修复 |

### Database

| Doc | Topic |
|-----|-------|
| [`auto-migrate-string-default`](../docs/solutions/database-issues/auto-migrate-string-default-quoting-postgresql.md) | SQLAlchemy auto-migrate VARCHAR 默认值引号 |

### Workflow

| Doc | Topic |
|-----|-------|
| [`server-monorepo-consolidation`](../docs/solutions/workflow-issues/server-monorepo-consolidation-phase2-2026-05-14.md) | Phase 2 服务 Monorepo 合并 |
| [`backend-module-extraction`](../docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md) | Backend 模块提取工作流 |

### Developer Experience

| Doc | Topic |
|-----|-------|
| [`monorepo-lint-format`](../docs/solutions/developer-experience/monorepo-module-level-lint-format-typecheck-2026-04-12.md) | Monorepo 模块级 lint/format/typecheck |
| [`pr-merge-verification`](../docs/solutions/developer-experience/pr-merge-verification-squash.md) | PR 合并状态验证 (squash merge 陷阱) |

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, project overview
- Module CLAUDE.md files: [`apps/backend`](./apps/backend/CLAUDE.md), [`apps/agent`](./apps/agent/CLAUDE.md), [`apps/scheduler_worker`](./apps/scheduler_worker/CLAUDE.md), [`packages/core`](./packages/core/CLAUDE.md), [`packages/db`](./packages/db/CLAUDE.md), [`packages/domain`](./packages/domain/CLAUDE.md), [`packages/security`](./packages/security/CLAUDE.md), [`packages/storage`](./packages/storage/CLAUDE.md)
