---
title: "refactor: Unified DATA_ROOT path management across all server modules"
type: refactor
status: active
created: 2026-05-17
deepened: 2026-05-17
---

# refactor: Unified DATA_ROOT path management across all server modules

## Problem Frame

All three server apps (backend, agent, scheduler_worker) construct local file paths independently using scattered relative-path defaults. There is no single configurable root — `UPLOAD_DIR`, `WORKSPACE_ROOT`, `CHAT_DIR`, `LOG_DIR`, `DATABASE_URL`, `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR`, and two DeerFlow SQLite databases all have separate defaults that happen to land under `./data/` only by convention. Several paths are hardcoded entirely (DeerFlow checkpointer, audit log).

This makes the system hard to relocate (e.g., to a different disk or user home), requires operators to set 6+ env vars to move data, and creates Docker volume mapping confusion. The agent's audit log goes to a separate named volume (`agent_logs:/app/logs`) while all other data goes to `./data:/app/data` — two volumes for one logical data store.

**Goal:** Introduce a single `DATA_ROOT` env var (default `~/.numina/data/`) from which all sub-paths derive. Docker deployments set `DATA_ROOT=/app/.numina/data` and map one volume. All existing per-path env vars remain as overrides for operators who need them.

---

## Scope Boundaries

**In scope:**
- Add `DATA_ROOT` to both `packages/core/settings.py` (backend/scheduler) and `apps/agent/app/config.py` (agent)
- Derive all current path defaults from `DATA_ROOT`
- Fix hardcoded paths: DeerFlow checkpointer DB in `main.py` and `base/config.yaml`, audit log in `audit_logger.py`, StaticFiles mount in `backend/main.py`
- Restructure sub-paths to match the agreed layout (see Target Layout below)
- Update `docker-compose.yml` to use one volume and inject `DATA_ROOT`
- Update `.env.example` files

**Deferred to Follow-Up Work:**
- Merging `CHAT_DIR` (backend chat JSONL) and `SESSIONS_DATA_DIR` (agent session journal JSONL) into a single path — both will live under `DATA_ROOT` after this refactor but remain separate sub-trees
- Remote storage backends (S3, WebDAV) — unaffected by this refactor
- Log aggregation (ELK/Loki) — unaffected

**Outside scope:**
- Changing the DeerFlow skills path (`/app/skills/custom`) — this is a code asset, not a data path
- Frontend changes

---

## Target Directory Layout

```
~/.numina/data/                              ← DATA_ROOT
├── db/
│   ├── numina.db                            ← SQLite main DB (backend/scheduler)
│   └── deerflow-checkpoints.db             ← LangGraph SqliteSaver (agent)
├── workspace/
│   └── {family_id}/
│       ├── upload/
│       │   └── {user_id}/                  ← user uploads (images, etc.)
│       ├── agent/
│       │   ├── {capability}/
│       │   │   └── {user_id}/
│       │   │       └── {session_id}.jsonl  ← session journal (agent)
│       │   └── memory.json                 ← DeerFlow per-family memory (shared across capabilities)
│       ├── chat/
│       │   └── {session_id}.jsonl          ← backend chat_session.py (unchanged structure, new root)
│       ├── skills/                         ← family custom skill prompts
│       ├── prompts/                        ← family custom prompts
│       └── exports/                        ← export files
└── logs/
    ├── app.log
    ├── security.log
    └── agent-audit.log
```

---

## Key Technical Decisions

**1. `~` expansion is explicit, not automatic.**
pydantic-settings stores path fields as `str`. No existing code calls `.expanduser()`. The `DATA_ROOT` value must be expanded at the point of use: `Path(settings.DATA_ROOT).expanduser().resolve()`. A `@model_validator(mode="after")` that resolves `DATA_ROOT` to an absolute path at settings construction time is the cleanest approach — it runs once at import time and all downstream consumers get a stable absolute string.

**2. Existing per-path env vars are preserved as overrides.**
`UPLOAD_DIR`, `WORKSPACE_ROOT`, `CHAT_DIR`, `LOG_DIR`, `DATABASE_URL`, `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR` all remain in `Settings` / `AgentSettings`. Their defaults change from hardcoded relative strings to `""` (empty), and a `@model_validator` fills them from `DATA_ROOT` when empty. Operators who set these vars explicitly are unaffected.

**3. `audit_logger.py` runs at import time — settings must be read lazily.**
`audit_logger.py` calls `os.makedirs("logs", ...)` and opens the log file at module level, before `AgentSettings` is fully initialized in some import orders. The fix is to defer directory creation and file opening to first use (lazy init pattern), reading `settings.LOG_DIR` at that point rather than at module load.

**4. `_generate_temp_config()` uses dict mutation, not string replacement.**
Reading the actual code confirms: `_generate_temp_config()` calls `yaml.safe_load()` → mutates the Python dict → `yaml.dump()`. It does NOT do text-level `$VAR` string replacement. The `$AI_MODEL`/`$AI_API_KEY` placeholders in `base/config.yaml` are consumed by DeerFlow's own loader (which reads the final temp file), not by `_generate_temp_config()`. Therefore: inject the checkpointer path via dict assignment (`config['checkpointer']['path'] = settings.DEERFLOW_DB_PATH`) — the same pattern used for memory path injection (`config['memory']['storage_path'] = str(memory_path)`). No `$DEERFLOW_CHECKPOINTER_PATH` placeholder is needed in `base/config.yaml`.

**5. `backend/main.py` StaticFiles mount reads env directly — fix to use `settings`.**
Line 392 calls `os.getenv("UPLOAD_DIR", "./data/uploads")` directly, bypassing `settings`. Change to `settings.UPLOAD_DIR` so there is one source of truth.

**6. Docker: one bind-mount volume, `DATA_ROOT` injected as env var.**
All services get `DATA_ROOT=/app/.numina/data` and a single volume `${NUMINA_DATA_DIR:-./data}:/app/.numina/data`. The `agent_logs` named volume is removed — logs now live under `DATA_ROOT/logs/`. A comment in `docker-compose.yml` warns operators to map the volume in production.

**7. `CHAT_DIR != UPLOAD_DIR` validation is preserved.**
The existing `Path.resolve()` + `is_relative_to()` check at the bottom of `settings.py` must remain. After the refactor, both paths derive from `DATA_ROOT` but land in different subdirectories (`workspace/` vs `workspace/{family_id}/upload/`), so the check will still pass — but it must not be removed.

---

## High-Level Technical Design

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
DATA_ROOT = ~/.numina/data/   (expanded to absolute at settings construction)
    │
    ├── packages/core/settings.py
    │     DATA_ROOT → str (model_validator expands ~ and resolves)
    │     DATABASE_URL  = "sqlite:///{DATA_ROOT}/db/numina.db"   (if empty)
    │     UPLOAD_DIR    = "{DATA_ROOT}/workspace"                (if empty) ─┐
    │     WORKSPACE_ROOT= "{DATA_ROOT}/workspace"                (if empty) ─┤ 同一根目录，
    │     CHAT_DIR      = "{DATA_ROOT}/workspace"                (if empty) ─┘ 子路径由各 service 内部拼接
    │     LOG_DIR       = "{DATA_ROOT}/logs"                     (if empty)
    │
    ├── apps/agent/app/config.py
    │     DATA_ROOT → str (same expand pattern, independent settings class)
    │     SESSIONS_DATA_DIR = "{DATA_ROOT}/workspace"            (if empty)
    │     AGENT_DATA_DIR    = "{DATA_ROOT}/workspace"            (if empty)
    │     LOG_DIR           = "{DATA_ROOT}/logs"                 (if empty)
    │     DEERFLOW_DB_PATH  = "{DATA_ROOT}/db/deerflow-checkpoints.db" (if empty)
    │
    └── docker-compose.yml
          DATA_ROOT=/app/.numina/data  (all services)
          volume: ${NUMINA_DATA_DIR:-./data}:/app/.numina/data
```

> **为什么 UPLOAD_DIR / WORKSPACE_ROOT / CHAT_DIR 都指向同一个 `workspace/` 目录？**
> 因为它们的子路径由各自的 service 内部拼接：`local.py` 拼 `{family_id}/upload/{user_id}/`，`workspace.py` 拼 `{family_id}/skills/`，`chat_session.py` 拼 `{family_id}/chat/`。三个变量保留是为了向后兼容——运维可以单独覆盖某一个变量将其指向不同磁盘。

Sub-path construction (unchanged call sites, new roots):
- `workspace.py`: `Path(settings.WORKSPACE_ROOT) / family_id / "skills"` → same code, new root
- `session_journal.py`: `Path(settings.SESSIONS_DATA_DIR) / family_id / "agent" / capability / user_id / f"{session_id}.jsonl"`
- `local.py` (storage): `Path(settings.UPLOAD_DIR) / family_id / "upload" / user_id / date_dir`
- `chat_session.py`: `Path(settings.CHAT_DIR) / family_id / "chat" / f"{session_id}.jsonl"`

---

## Implementation Units

### U1. Add `DATA_ROOT` to `packages/core/settings.py` with derived defaults

**Goal:** Introduce `DATA_ROOT` as the single configurable root for backend and scheduler_worker. All existing path settings derive their defaults from it when not explicitly set.

**Requirements:** Operators who already set `UPLOAD_DIR`, `WORKSPACE_ROOT`, etc. explicitly are unaffected. `~` in `DATA_ROOT` is expanded to an absolute path at settings construction time.

**Dependencies:** None

**Files:**
- `server/packages/core/settings.py`
- `server/tests/backend/test_settings_data_root.py` (new)

**Approach:**
- Add `DATA_ROOT: str = "~/.numina/data"` field
- Add `@model_validator(mode="after")` that: (1) expands and resolves `DATA_ROOT` to an absolute path string, (2) fills `DATABASE_URL`, `UPLOAD_DIR`, `WORKSPACE_ROOT`, `CHAT_DIR`, `LOG_DIR` from `DATA_ROOT` when they are at their old defaults or empty
- The validator must run after all fields are set, so it can reference `self.DATA_ROOT`
- Keep the existing `CHAT_DIR != UPLOAD_DIR` post-instantiation check — it still applies
- Keep all existing fields and their types unchanged (all `str`)
- `DATA_ROOT` itself is validated to be non-empty

**Patterns to follow:**
- Existing module-level validation blocks in `settings.py` (lines 86–132) for the style of post-instantiation checks
- `@model_validator(mode="after")` from pydantic v2 — see `server/apps/backend/CLAUDE.md` §Pydantic v2

**Test scenarios:**
- Default `DATA_ROOT` (`~/.numina/data`) expands to an absolute path (no `~` in result)
- `UPLOAD_DIR` is derived as `{expanded_DATA_ROOT}/workspace` when not explicitly set
- `LOG_DIR` is derived as `{expanded_DATA_ROOT}/logs` when not explicitly set
- `DATABASE_URL` is derived as `sqlite:///{expanded_DATA_ROOT}/db/numina.db` when not explicitly set
- Explicitly setting `UPLOAD_DIR=./custom` overrides the derived default
- `CHAT_DIR != UPLOAD_DIR` validation still raises `RuntimeError` when violated
- Setting `DATA_ROOT=/tmp/test` causes all derived paths to be under `/tmp/test`

**Verification:** `uv run pytest tests/ -v -k "settings_data_root"` passes; `uv run mypy app/` passes.

---

### U2. Add `DATA_ROOT` to `apps/agent/app/config.py` with derived defaults

**Goal:** Mirror U1 for the agent service. Agent has its own `AgentSettings` class (independent from `packages/core`) and needs `DATA_ROOT`, `LOG_DIR`, and `DEERFLOW_DB_PATH` added.

**Requirements:** `SESSIONS_DATA_DIR` and `AGENT_DATA_DIR` derive from `DATA_ROOT`. New `DEERFLOW_DB_PATH` setting added for the checkpointer DB path.

**Dependencies:** None (independent of U1 — agent is a separate service)

**Files:**
- `server/apps/agent/app/config.py`
- `server/tests/agent/unit/test_agent_config_data_root.py` (new)

**Approach:**
- Add `DATA_ROOT: str = "~/.numina/data"` field
- Add `LOG_DIR: str = ""` field (new — currently hardcoded in audit_logger.py)
- Add `DEERFLOW_DB_PATH: str = ""` field (new — currently hardcoded in main.py and config.yaml)
- Add `@model_validator(mode="after")` that expands `DATA_ROOT` and fills `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR`, `LOG_DIR`, `DEERFLOW_DB_PATH` from it when empty
- `SESSIONS_DATA_DIR` default: `{DATA_ROOT}/workspace`
- `AGENT_DATA_DIR` default: `{DATA_ROOT}/workspace`
- `LOG_DIR` default: `{DATA_ROOT}/logs`
- `DEERFLOW_DB_PATH` default: `{DATA_ROOT}/db/deerflow-checkpoints.db`

**Patterns to follow:** Same `@model_validator(mode="after")` pattern as U1.

**Test scenarios:**
- Default `DATA_ROOT` expands `~` to absolute path
- `SESSIONS_DATA_DIR` derives from `DATA_ROOT` when not set
- `DEERFLOW_DB_PATH` derives as `{DATA_ROOT}/db/deerflow-checkpoints.db` when not set
- Explicit `SESSIONS_DATA_DIR` override is respected
- `LOG_DIR` derives from `DATA_ROOT` when not set

**Verification:** `uv run pytest tests/ -v -k "agent_config_data_root"` passes; `uv run mypy . --exclude vendor` passes.

---

### U3. Fix hardcoded DeerFlow paths in `agent/main.py` and `family_adapter_cache.py`

**Goal:** Replace the two hardcoded DeerFlow SQLite paths with configurable values driven by `settings.DEERFLOW_DB_PATH` (from U2).

**Requirements:** The DeerFlow persistence engine DB (`.deer-flow/data/deerflow.db`) and the LangGraph checkpointer DB (`/app/data/deerflow-checkpoints.db`) both move under `DATA_ROOT/db/`. The checkpointer path is injected via dict mutation in `_generate_temp_config()` (same pattern as memory path).

**Dependencies:** U2

**Files:**
- `server/apps/agent/app/main.py`
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`

**Approach:**

*`main.py` (lines 37–43):*
- Replace `db_dir = ".deer-flow/data"` with `db_path = settings.DEERFLOW_DB_PATH`
- Create parent directory with `Path(db_path).parent.mkdir(parents=True, exist_ok=True)`
- Pass `db_path` directly to `init_engine(url=f"sqlite+aiosqlite:///{db_path}", sqlite_dir=str(Path(db_path).parent))`

*`family_adapter_cache.py`:*
- In `_get_shared_checkpointer()`: replace the hardcoded `/app/data/deerflow-checkpoints.db` fallback with `settings.DEERFLOW_DB_PATH`
- In `_generate_temp_config()`: after `yaml.safe_load()`, add dict assignment (mirrors existing memory path pattern at line 264):
  ```python
  config['checkpointer']['path'] = settings.DEERFLOW_DB_PATH
  ```
- Update the per-family memory path from `Path(settings.AGENT_DATA_DIR) / family_id / "memory.json"` to `Path(settings.AGENT_DATA_DIR) / family_id / "agent" / "memory.json"` (adds `agent/` subdirectory to match new layout)

*`base/config.yaml`:*
- No changes needed — the hardcoded `checkpointer.path` value in the template is overwritten by dict mutation before the temp file is written

**Patterns to follow:** Existing `_generate_temp_config()` dict mutation pattern: `config['memory']['storage_path'] = str(memory_path)` (line 264).

**Test scenarios:**
- `main.py` lifespan creates the DB parent directory before calling `init_engine`
- `_get_shared_checkpointer()` uses `settings.DEERFLOW_DB_PATH` rather than a hardcoded path
- `_generate_temp_config()` sets `config['checkpointer']['path']` via dict assignment (not string replacement)
- Per-family memory path includes `agent/` subdirectory
- `base/config.yaml` is unchanged (template value is overwritten at runtime)

**Verification:** `uv run pytest tests/ -v -k "deerflow or checkpointer"` passes; `uv run mypy . --exclude vendor` passes.

---

### U4. Fix `audit_logger.py` hardcoded `logs/` path

**Goal:** Replace the hardcoded `"logs"` directory in `audit_logger.py` with `settings.LOG_DIR` (from U2). The logger currently runs `os.makedirs("logs", ...)` at module import time — this must be deferred to first use.

**Requirements:** Audit log lands at `{DATA_ROOT}/logs/agent-audit.log`. No behavior change to log rotation (daily, 30-day retention).

**Dependencies:** U2

**Files:**
- `server/apps/agent/services/audit_logger.py`

**Approach:**
- Remove the module-level `os.makedirs("logs", ...)` and `logging.handlers.TimedRotatingFileHandler(filename="logs/agent-audit.log", ...)` calls
- Create a `setup_audit_logger()` function that reads `settings.LOG_DIR`, creates the directory, and configures the handler
- Call `setup_audit_logger()` from `main.py` lifespan startup, after `settings.validate_required()` (line 16) and before `setup_schedules()` (line 18)

**Patterns to follow:** `apps/agent/core/logging.py` `setup_logging()` pattern — called explicitly from `main.py` at startup.

**Test scenarios:**
- Audit logger creates `{settings.LOG_DIR}/agent-audit.log` (not `logs/agent-audit.log`)
- Patching `settings.LOG_DIR` to a `tmp_path` causes the log file to land there
- Log rotation config (daily, 30-day retention) is unchanged

**Verification:** `uv run pytest tests/ -v -k "audit_logger"` passes.

---

### U5. Fix `backend/main.py` StaticFiles mount to use `settings.UPLOAD_DIR`

**Goal:** Remove the second source of truth for `UPLOAD_DIR` in `backend/main.py` (line 392), which reads `os.getenv("UPLOAD_DIR", "./data/uploads")` directly instead of using `settings`.

**Requirements:** StaticFiles mount uses the same `UPLOAD_DIR` value as the rest of the backend.

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/main.py`

**Approach:**
- Replace `upload_dir = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))` with `upload_dir = Path(settings.UPLOAD_DIR)`
- Remove the `os` import if it becomes unused after this change (check other usages first)

**Patterns to follow:** Other `settings.*` usages in `main.py`.

**Test scenarios:**
- StaticFiles mount path matches `settings.UPLOAD_DIR`
- No `os.getenv("UPLOAD_DIR", ...)` call remains in `main.py`

**Verification:** `uv run mypy app/` passes; grep confirms no `os.getenv("UPLOAD_DIR"` in `main.py`.

---

### U6. Update upload path structure in `packages/storage/local.py`

**Goal:** Change the upload storage path from `{UPLOAD_DIR}/images/{date}/` to `{UPLOAD_DIR}/{family_id}/upload/{user_id}/{date}/` to match the new per-family, per-user layout.

**Requirements:** `family_id` and `user_id` must be passed to the storage backend. Path traversal protection must be preserved. **Existing `cached_file.local_path` records must be migrated** — current records store absolute paths like `./data/uploads/images/20240101/abc.jpg` which will not resolve under the new structure.

**Dependencies:** U1

**Files:**
- `server/packages/storage/local.py`
- `server/apps/backend/app/services/storage/service.py`
- `server/tests/backend/test_storage_local.py`
- `server/apps/backend/alembic/versions/XXX_migrate_cached_file_paths.py` (new migration)

**Approach:**

*Path structure change:*
- `LocalStorageBackend.save()` currently takes `(content, filename, date_dir)`. Add `family_id: str` and `user_id: str` parameters
- Change `target_dir` from `self._upload_dir / "images" / date_dir` to `self._upload_dir / family_id / "upload" / user_id / date_dir`
- Validate `family_id` and `user_id` against `_SAFE_ID_PATTERN` to prevent path traversal
- Update `storage/service.py` to pass `family_id` and `user_id` from the `user` context (user.family_id, user.id)

*Database migration for existing records:*
- Create an Alembic migration that rewrites `cached_file.local_path` values from the old format (`{UPLOAD_DIR}/images/{date}/{filename}`) to the new format (`{UPLOAD_DIR}/{family_id}/upload/{user_id}/{date}/{filename}`)
- Migration reads each `CachedFile` row, extracts `family_id`, `user_id`, and `date_dir` from existing columns, reconstructs the new path, and updates `local_path`
- Run migration before deploying U6 code changes

*Physical file migration:*
- Migration also moves files on disk from old location to new location
- Use `shutil.move()` with error handling for missing files (may have been deleted)

**Patterns to follow:**
- `session_journal.py` `_validate_id()` pattern for ID validation
- Existing `.resolve()` + `.startswith()` traversal check in `local.py` lines 28–30

**Test scenarios:**
- File saved to `{UPLOAD_DIR}/{family_id}/upload/{user_id}/{date}/{filename}`
- Invalid `family_id` (path traversal attempt like `../evil`) raises `ValueError`
- Invalid `user_id` raises `ValueError`
- Path traversal check still rejects paths outside `UPLOAD_DIR`
- Existing test coverage for `LocalStorageBackend` continues to pass

**Verification:** `uv run pytest tests/ -v -k "storage"` passes.

---

### U7. Update `session_journal.py` path structure for agent capability/user isolation

**Goal:** Change session journal path from `{SESSIONS_DATA_DIR}/{family_id}/{session_id}.jsonl` to `{SESSIONS_DATA_DIR}/{family_id}/agent/{capability}/{user_id}/{session_id}.jsonl`.

**Requirements:** `capability` and `user_id` must be available at `SessionJournalService` construction or per-session. The module-level singleton `session_journal` must still work.

**Dependencies:** U2

**Files:**
- `server/apps/agent/services/session_journal.py`
- `server/apps/agent/services/orchestrator.py` (caller — passes `jsonl_path`)
- `server/tests/agent/unit/test_session_journal.py`

**Approach:**
- `_session_path()` currently takes `(family_id, session_id)`. Add `capability: str` and `user_id: str` parameters
- New path: `self._base_dir / family_id / "agent" / capability / user_id / f"{session_id}.jsonl"`
- Validate `capability` and `user_id` with `_validate_id()`
- `write_session_start()` already accepts `jsonl_path` as an override — the orchestrator sets this. Update `orchestrator.py` to construct the new path and pass it as `jsonl_path`
- The module-level singleton `session_journal = SessionJournalService(settings.SESSIONS_DATA_DIR)` is unchanged — path construction happens per-call

**Patterns to follow:** Existing `_validate_id()` and `_session_path()` patterns in `session_journal.py`.

**Test scenarios:**
- Path constructed as `{base}/{family_id}/agent/{capability}/{user_id}/{session_id}.jsonl`
- Invalid `capability` raises `ValueError`
- Invalid `user_id` raises `ValueError`
- `write_session_start()` with explicit `jsonl_path` override still works (backward compat for orchestrator)
- `read_events()` with `jsonl_path` override still works

**Verification:** `uv run pytest tests/ -v -k "session_journal"` passes.

---

### U8. Update `docker-compose.yml` and `.env.example` files

**Goal:** Consolidate Docker volumes to a single bind mount under `DATA_ROOT`. Remove the `agent_logs` named volume. Add `DATA_ROOT` env var to all services. Update `.env.example` files with documentation.

**Requirements:** Operators can override the host path via `NUMINA_DATA_DIR` env var. A clear comment warns about volume mapping in production.

**Dependencies:** U1, U2, U4 (audit log now under DATA_ROOT, so agent_logs named volume can be removed)

**Files:**
- `docker-compose.yml`
- `server/apps/backend/.env.example`
- `server/apps/agent/.env.example` (if it exists)

**Approach:**

*`docker-compose.yml`:*
- Add `DATA_ROOT=/app/.numina/data` to all three service `environment` blocks
- Change all `./data:/app/data` volume mounts to `${NUMINA_DATA_DIR:-./data}:/app/.numina/data`
- Remove `agent_logs:/app/logs` volume from agent service (logs now under DATA_ROOT)
- Remove `agent_logs:` from the top-level `volumes:` block
- Add comment block above the volume definition:
  ```yaml
  # ⚠️  DATA_ROOT defaults to /app/.numina/data inside the container.
  # Production deployments MUST map this volume to a persistent host path:
  #   volumes:
  #     - /your/host/data/path:/app/.numina/data
  # Without a volume mapping, all data is lost on container restart.
  ```
- Update `DATABASE_URL` default from `sqlite:////app/data/numina.db` to `sqlite:////app/.numina/data/db/numina.db`
- Update `WORKSPACE_ROOT` default from `/app/data/workspace` to `/app/.numina/data/workspace`

*`.env.example`:*
- Add `DATA_ROOT=~/.numina/data` with explanation comment
- Update all sub-path defaults to show they derive from `DATA_ROOT`
- Add Docker deployment note

**Test scenarios:**
- `Test expectation: none` — docker-compose.yml changes are verified by manual inspection and Docker smoke test

**Verification:** `docker-compose config` validates without errors; all service `environment` blocks contain `DATA_ROOT`.

---

## System-Wide Impact

| Surface | Impact |
|---|---|
| Backend service | `settings.UPLOAD_DIR`, `WORKSPACE_ROOT`, `CHAT_DIR`, `LOG_DIR`, `DATABASE_URL` defaults change — existing explicit env var overrides unaffected |
| Agent service | `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR`, `LOG_DIR`, `DEERFLOW_DB_PATH` defaults change; audit log moves from named volume to DATA_ROOT |
| Scheduler worker | Inherits backend settings — `DATABASE_URL`, `UPLOAD_DIR` defaults change |
| Docker operators | One volume to map instead of two; `NUMINA_DATA_DIR` controls host path |
| Local dev (bare uvicorn) | Data now lands in `~/.numina/data/` instead of `./data/` relative to CWD |
| Existing deployments | **Migration note:** existing `./data/` contents must be moved to the new `DATA_ROOT` path, or operators must set `DATA_ROOT=./data` to preserve the old location |

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Existing deployments lose data if `DATA_ROOT` changes silently | Document migration in `.env.example`; operators can set `DATA_ROOT=./data` to keep old behavior |
| `~` not expanded in some code paths | `@model_validator` expands at construction time; all consumers get an absolute string |
| `audit_logger.py` import-time side effects break if settings not ready | Move setup to explicit lifespan call (U4) |
| DeerFlow config.yaml env var substitution not supported | Verified: `_generate_temp_config()` uses dict mutation (yaml.safe_load → dict assignment → yaml.dump), not string replacement. U3 uses the same dict assignment pattern as memory path injection. |
| `CHAT_DIR != UPLOAD_DIR` validation fails after refactor | Both paths derive from `DATA_ROOT/workspace` but are different sub-paths — validation will pass; add a test to confirm |

---

## Deferred Implementation Notes

- The `session_journal.py` module-level singleton is initialized at import time with `settings.SESSIONS_DATA_DIR`. After U2, this value is an absolute path. Verify that the singleton is not imported before `AgentSettings` is constructed in any test fixture.
- `storage/service.py` currently instantiates `LocalStorageBackend(settings.UPLOAD_DIR)` inside `upload_file()` (not at module level). After U6, `family_id` and `user_id` are passed as parameters to `backend.save()`. The `StorageService.upload_file()` method already has access to `user.family_id` and `user.id` — pass them through.
