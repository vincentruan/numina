---
date: 2026-05-14
topic: scheduler-worker-docs
status: active
origin: docs/brainstorms/2026-05-14-scheduler-worker-docs-requirements.md
---

# Plan: scheduler_worker Documentation Treatment

## Problem Frame

`server/apps/scheduler_worker` has a 1-line README and no CLAUDE.md. Two files need to be written:
1. `server/apps/scheduler_worker/README.md` — replace the 1-line placeholder with a job inventory table and dev commands
2. `server/apps/scheduler_worker/CLAUDE.md` — new file following the project's established module template

No Python source files are modified. This is documentation only.

## Files Touched

| File | Action |
|------|--------|
| `server/apps/scheduler_worker/README.md` | Replace (rewrite from 1-line placeholder) |
| `server/apps/scheduler_worker/CLAUDE.md` | Create (new file) |

## Patterns to Follow

- `server/apps/backend/CLAUDE.md` — Quality Commands → Tooling → Key Invariants → Patterns → Links structure
- `server/apps/agent/CLAUDE.md` — same structure; note that agent uses `uv run mypy . --exclude vendor` while backend uses `uv run mypy app/`
- Root `server/CLAUDE.md` — cross-cutting conventions; CLAUDE.md must reference it via relative link

## Implementation Units

### Unit 1: README.md

**File:** `server/apps/scheduler_worker/README.md`

**Content spec:**

1. **Header + purpose paragraph** — one paragraph: what the module is (standalone APScheduler + FastAPI process), what it does (runs 7 background jobs independently from the backend), how it starts (uvicorn on port 8002 via Docker).

2. **Job inventory table** — 7 rows, sourced from `scheduler.py`'s `setup_all_jobs()`:

| Job ID | Function | Trigger | Schedule | Domain Package | Produces |
|--------|----------|---------|----------|----------------|----------|
| `exchange_rate` | `fetch_rates_job` | cron | Every 2h, 08:00–22:00, ±15min jitter | `packages.domain.exchange_rate.service` | Exchange rate records in DB |
| `file_sync` | `file_sync_job` | interval | Every `FILE_SYNC_INTERVAL_MINUTES` min | `packages.storage.*`, `packages.db.models.*` | Syncs pending files to remote storage backend |
| `audit_log_purge` | `audit_log_purge_job` | cron | Daily 03:00 | `packages.domain.audit.service` | Deletes audit log entries older than 90 days |
| `revoked_token_cleanup` | `revoked_token_cleanup_job` | cron | Hourly at :30 | `packages.security.revoke_jti` | Deletes expired revoked JWT records |
| `device_session_cleanup` | `device_session_cleanup_job` | cron | Hourly at :15 | `packages.domain.device.service` | Expires stale + purges old revoked device sessions |
| `reminder_daily` | `reminder_job` | cron | Daily 09:20 | `packages.domain.notification.service` | Runs scheduled notification/reminder checks |
| `snapshot_daily` | `snapshot_job` | cron | Daily 00:05 | `packages.domain.snapshot.service` | Generates daily asset snapshots for all families |

3. **Dev commands** — run from `server/`:
```bash
uv run ruff check apps/scheduler_worker/        # lint
uv run ruff check apps/scheduler_worker/ --fix  # lint + auto-fix
uv run ruff format apps/scheduler_worker/       # format (only files you touch)
uv run mypy apps/scheduler_worker/ --explicit-package-bases  # type check
uv run pytest apps/scheduler_worker/ -v         # run tests
```

---

### Unit 2: CLAUDE.md

**File:** `server/apps/scheduler_worker/CLAUDE.md`

**Section spec** (follow backend/CLAUDE.md structure exactly):

**Header:**
```
# scheduler_worker/CLAUDE.md

Module-specific guidance for the APScheduler background job worker.
See root [`CLAUDE.md`](../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.
```

**## Quality Commands**
Same commands as README dev commands section (see Unit 1). Include the `--explicit-package-bases` flag on mypy.

**## Tooling**
- **uv:** package manager. Use `uv add`/`uv remove`. Never `pip install`.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`.
- **mypy:** type checker. Requires `--explicit-package-bases` flag to avoid namespace collision with other `apps/` packages.
- **APScheduler 3.x:** `AsyncIOScheduler` — allows async jobs (`file_sync_job`) to run natively in the event loop.

**## Key Invariants**

1. **`max_instances=1`** — every `scheduler.add_job()` call must include this. Prevents concurrent runs of the same job if a previous run is still executing.
2. **`coalesce=True`** — every `scheduler.add_job()` call must include this. If the scheduler was down and missed runs, only one catch-up execution fires.
3. **`replace_existing=True`** — every `scheduler.add_job()` call must include this. Makes job registration idempotent on restart.
4. **Lazy imports inside job bodies** — never add module-level imports of domain services. All `from packages.domain.*` and `from packages.storage.*` imports go inside the job function body with `# noqa: PLC0415`. This prevents circular import issues at module load time.
5. **Session management** — most jobs create `db = SessionLocal()` and close it in a `finally` block. Jobs that delegate entirely to a domain service (e.g., `audit_log_purge_job` calls `purge_old_audit_logs()`) may let the service manage its own session — both patterns are valid. Never leave a session open outside a `finally` block.

**## Don't Do**

- **Don't import from `apps/backend` or `apps/agent`** — import direction rule: `apps/` must not import sibling `apps/`. Use `packages/` for shared logic.
- **Don't add module-level imports of domain services** — breaks the lazy-import pattern; causes import errors at startup.
- **Don't run the scheduler from the module directory** — quality commands and `uvicorn` must be invoked from `server/`, not from `apps/scheduler_worker/`.
- **Don't use `SyncScheduler`** — the worker uses `AsyncIOScheduler` so async jobs run natively. Switching to a sync scheduler would require wrapping async jobs.

**## Watch Out**

- **`FILE_SYNC_INTERVAL_MINUTES`** — the file sync job interval is controlled by this env var (from `packages.core.settings`). If not set, it falls back to the default in `Settings`. Check the value before assuming the job runs on a fixed schedule.
- **Exchange rate job cron window** — the job only runs between 08:00 and 22:00 (hours `8,10,12,14,16,18,20,22`) with a 15-minute jitter (`jitter=900`). It does not run overnight. This is intentional to avoid hitting the exchange rate API during off-hours.
- **`audit_log_purge_job` has no `SessionLocal()`** — it delegates session management to `purge_old_audit_logs()` in `packages.domain.audit.service`. This is the only job that does not manage its own session directly.
- **`file_sync_job` is async** — it is the only async job. APScheduler handles it natively via `AsyncIOScheduler`. Do not wrap it in `asyncio.run()`.

**## Patterns**

**Adding a new job (two-step process):**

Step 1 — Define the job function in `server/apps/scheduler_worker/jobs/__init__.py`:
```python
def my_new_job() -> None:
    """One-line description of what this job does."""
    from packages.domain.my_domain.service import my_service_function  # noqa: PLC0415

    db = SessionLocal()
    try:
        my_service_function(db)
        logger.info("任务完成")
    except Exception as e:
        logger.exception(f"任务失败: {e}")
    finally:
        db.close()
```

Step 2 — Register the job in `server/apps/scheduler_worker/scheduler.py`'s `setup_all_jobs()`:
```python
from apps.scheduler_worker.jobs import my_new_job  # noqa: PLC0415

scheduler.add_job(
    my_new_job,
    trigger="cron",
    hour=2,
    minute=30,
    id="my_new_job",
    name="my_new_job",
    replace_existing=True,   # required
    max_instances=1,         # required
    coalesce=True,           # required
)
```

Step 3 — Add a row to the job inventory table in `server/apps/scheduler_worker/README.md`.

**## Links**

- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, job inventory table, dev commands

## Decisions

- **`--explicit-package-bases` on mypy** — required because `apps/scheduler_worker/` is not a top-level package; mypy needs this flag to resolve the namespace correctly. Verified against the monorepo structure. (see origin: docs/brainstorms/2026-05-14-scheduler-worker-docs-requirements.md R3, R5)
- **Job table in README, recipe in CLAUDE.md** — operational reference (who runs what, when) belongs in README for human readers; coding patterns (how to add a job) belong in CLAUDE.md for agents and developers modifying code. (see origin: Key Decisions)
- **Lazy-import pattern as Key Invariant, not just a Pattern** — an agent would naturally write module-level imports; the invariant placement ensures it's seen before the Patterns section. (see origin: Key Decisions)
- **`audit_log_purge_job` session exception documented in Watch Out** — the job is the only one that doesn't manage its own `SessionLocal()`. Documenting it prevents a developer from "fixing" it by adding an unnecessary session. (see origin: R6)

## Sequencing

Unit 1 (README) and Unit 2 (CLAUDE.md) are independent — implement in either order or in parallel. No source code changes, no migrations, no test files required.

## Verification

After writing both files:
- README job table has exactly 7 rows matching the jobs registered in `scheduler.py`'s `setup_all_jobs()`
- CLAUDE.md sections appear in order: Quality Commands → Tooling → Key Invariants → Don't Do → Watch Out → Patterns → Links
- All `uv run` commands in both files use paths relative to `server/` (e.g., `apps/scheduler_worker/`, not absolute paths)
- Relative links in CLAUDE.md (`../../CLAUDE.md`, `./README.md`) resolve correctly from `server/apps/scheduler_worker/`
