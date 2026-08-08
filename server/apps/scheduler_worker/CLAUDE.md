# scheduler_worker/CLAUDE.md

Module-specific guidance for the APScheduler background job worker.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `server/`:

```bash
uv run uvicorn apps.scheduler_worker.main:app --reload --port 8002  # Dev worker
uv run ruff check apps/scheduler_worker/        # lint
uv run ruff check apps/scheduler_worker/ --fix  # lint + auto-fix
uv run ruff format apps/scheduler_worker/       # format (only files you touch)
uv run mypy apps/scheduler_worker/ --explicit-package-bases  # type check
uv run pytest apps/scheduler_worker/ -v         # run tests
```

## Tooling

- **uv:** package manager. Use `uv add`/`uv remove`. Never `pip install`.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`.
- **mypy:** type checker. Requires `--explicit-package-bases` to avoid namespace collision with other `apps/` packages.
- **APScheduler 3.x:** uses `AsyncIOScheduler` so async jobs (`file_sync_job`) run natively in the event loop.

## Directory Structure

```
scheduler_worker/
├── main.py            # FastAPI app entry point + lifespan (top-level, not under app/)
├── scheduler.py       # AsyncIOScheduler + setup_all_jobs() — register new jobs here
├── jobs/
│   └── __init__.py    # All job function definitions (add new jobs here)
└── app/
    └── config.py      # Settings (pydantic-settings)
```

The worker has no `routers/` — it exposes only liveness/readiness probes from `main.py`.

## Job Inventory

7 jobs are registered in `scheduler.py:setup_all_jobs()`:

| Job ID | Function | Trigger | Purpose |
|--------|----------|---------|---------|
| `exchange_rate` | `fetch_rates_job` | Cron `hour=8,10,12,14,16,18,20,22` (15-min jitter) | Refresh currency rates during waking hours |
| `file_sync` | `file_sync_job` (async) | Interval `FILE_SYNC_INTERVAL_MINUTES` env | Sync local files to remote storage backend |
| `audit_log_purge` | `audit_log_purge_job` | Cron daily 03:00 | Drop audit log rows past retention window |
| `revoked_token_cleanup` | `revoked_token_cleanup_job` | Cron hourly :30 | Remove expired entries from `revoked_token` table |
| `device_session_cleanup` | `device_session_cleanup_job` | Cron hourly :15 | Remove expired device sessions |
| `reminder_daily` | `reminder_job` | Cron daily 09:20 | Compute due reminders + dispatch via notification channels |
| `snapshot_daily` | `snapshot_job` | Cron daily 00:05 | Take per-family net-worth snapshot |

## Key Invariants

1. **`max_instances=1`** — every `scheduler.add_job()` call must include this. Prevents concurrent runs if a previous execution is still in progress.
2. **`coalesce=True`** — every `scheduler.add_job()` call must include this. If the scheduler was down and missed runs, only one catch-up execution fires.
3. **`replace_existing=True`** — every `scheduler.add_job()` call must include this. Makes job registration idempotent on restart.
4. **Lazy imports inside job bodies** — never add module-level imports of domain services. All `from packages.domain.*` and `from packages.storage.*` imports go inside the job function body with `# noqa: PLC0415`. Prevents circular import errors at startup.
5. **Session management** — most jobs create `db = SessionLocal()` and close it in a `finally` block. Jobs that delegate entirely to a domain service (e.g., `audit_log_purge_job` calls `purge_old_audit_logs()`) may let the service manage its own session — both patterns are valid. Never leave a session open outside a `finally` block.

## Don't Do

- **Don't add module-level imports of domain services** — breaks the lazy-import pattern and causes import errors at startup.
- **Don't use `SyncScheduler`** — the worker uses `AsyncIOScheduler` so async jobs run natively. Switching would require wrapping async jobs.

## Watch Out

- **`FILE_SYNC_INTERVAL_MINUTES`** — the file sync job interval is controlled by this env var (from `packages.core.settings`). Check the value before assuming the job runs on a fixed schedule.
- **Exchange rate job cron window** — only runs between 08:00 and 22:00 (`hour="8,10,12,14,16,18,20,22"`) with a 15-minute jitter. Does not run overnight — intentional.
- **`audit_log_purge_job` has no `SessionLocal()`** — it delegates session management to `purge_old_audit_logs()` in `packages.domain.audit.service`. This is the only job that does not manage its own session directly. Do not "fix" it by adding one.
- **`file_sync_job` is async** — the only async job. APScheduler handles it natively. Do not wrap it in `asyncio.run()`.
- **`reminder_job` runs once daily at 09:20** — if you need quicker reminder dispatch (e.g. minute-of-day scheduling), do not lower the cron interval; instead, queue dispatch from the backend's request path.
- **`device_session_cleanup_job` and `revoked_token_cleanup_job`** — both are hourly housekeeping jobs that delete expired rows. They do not flag stale-but-active sessions; that is the security middleware's job.

## Patterns

**Adding a new job (two steps):**

Step 1 — Define the job function in `apps/scheduler_worker/jobs/__init__.py`:

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

Step 2 — Register the job in `setup_all_jobs()` in `apps/scheduler_worker/scheduler.py`:

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

Step 3 — Add a row to the job inventory table in `apps/scheduler_worker/README.md`.

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, job inventory table, dev commands
