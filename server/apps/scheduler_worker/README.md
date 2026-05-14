# apps/scheduler_worker

Standalone APScheduler + FastAPI process that runs all 7 background jobs independently from the backend API. Starts on port 8002 via Docker and exposes `/health` for container healthchecks.

## Jobs

| Job ID | Function | Trigger | Schedule | Domain Package | Produces |
|--------|----------|---------|----------|----------------|----------|
| `exchange_rate` | `fetch_rates_job` | cron | Every 2h, 08:00–22:00, ±15min jitter | `packages.domain.exchange_rate.service` | Exchange rate records in DB |
| `file_sync` | `file_sync_job` | interval | Every `FILE_SYNC_INTERVAL_MINUTES` min | `packages.storage.*`, `packages.db.models.*` | Syncs pending files to remote storage backend |
| `audit_log_purge` | `audit_log_purge_job` | cron | Daily 03:00 | `packages.domain.audit.service` | Deletes audit log entries older than 90 days |
| `revoked_token_cleanup` | `revoked_token_cleanup_job` | cron | Hourly at :30 | `packages.security.revoke_jti` | Deletes expired revoked JWT records |
| `device_session_cleanup` | `device_session_cleanup_job` | cron | Hourly at :15 | `packages.domain.device.service` | Expires stale + purges old revoked device sessions |
| `reminder_daily` | `reminder_job` | cron | Daily 09:20 | `packages.domain.notification.service` | Runs scheduled notification/reminder checks |
| `snapshot_daily` | `snapshot_job` | cron | Daily 00:05 | `packages.domain.snapshot.service` | Generates daily asset snapshots for all families |

## Dev Commands

Run all commands from `server/`:

```bash
uv run ruff check apps/scheduler_worker/        # lint
uv run ruff check apps/scheduler_worker/ --fix  # lint + auto-fix
uv run ruff format apps/scheduler_worker/       # format (only files you touch)
uv run mypy apps/scheduler_worker/ --explicit-package-bases  # type check
uv run pytest apps/scheduler_worker/ -v         # run tests
```
