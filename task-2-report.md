# Task 2 Report — Database Migration

**Status:** DONE_WITH_CONCERNS

**Commit:** `6fa3ffbf` feat(notification): add digest_mode, digest_time, digest_sent_at columns

## What Was Done

1. **`server/packages/db/models/notification_channel.py`** — Added two columns:
   - `digest_mode: Mapped[str]` with `server_default="immediate"`
   - `digest_time: Mapped[str]` with `server_default="21:00"`

2. **`server/packages/db/models/reminder.py`** — Added one column:
   - `digest_sent_at: Mapped[datetime | None]` using `UTCDateTime()`, nullable

3. **Alembic migration** — Generated `75e411962098_add_notification_enhancements.py` via `--autogenerate`, then trimmed to only the 3 column-add operations (removed ~300 lines of unrelated drift from stale DB state). Applied via `alembic upgrade head`.

4. **`server/apps/backend/app/schemas/notification_channel.py`** — Added to all three schemas:
   - `NotificationChannelCreate`: `digest_mode: str = "immediate"`, `digest_time: str = "21:00"`
   - `NotificationChannelUpdate`: `digest_mode: str | None = None`, `digest_time: str | None = None`
   - `NotificationChannelResponse` (extends `SnowflakeBase`): same defaults as Create

5. **DB verified** — `sqlite3` PRAGMA confirms all 3 columns exist with correct types and defaults.

## Concerns

**Pre-existing migration bugs were blocking `alembic upgrade head` on fresh DBs.** Several prior migrations were not idempotent and failed on clean installs. I fixed them so the upgrade chain can run:

| File | Fix |
|------|-----|
| `a7b8c9d0e1f2_standardize_skill_id_names.py` | Added missing `revision` / `down_revision` variables |
| `x9876y54zqr0_add_task_tracking_fields.py` | Guarded `ix_ai_tasks_family_skill_status` index creation on `"skill_id" in existing_columns` |
| `a1b2c3d4e5f7_add_last_synced_at_to_storage_backends.py` | Wrapped `add_column` in `if "last_synced_at" not in existing_columns` |
| `e4f5g6h7i8j9_fix_ai_agents_name_constraint.py` | Guarded constraint drop/create with inspector check |
| `f5g6h7i8j9k0_add_family_id_to_storage_backends.py` | Guarded column add and unique constraint with inspector checks |
| `c7timestz01_unify_datetime_to_timestamptz.py` | Skip `batch_alter_table` for tables not yet present (`table not in existing_tables`) |

These fixes were committed as a separate commit (`1c9b6795`) to keep task-2 focused. The drift was detected during autogenerate because the worktree's SQLite DB had been initialized from an older migration snapshot and was out of sync with the current model definitions.

## Files Changed

- `server/packages/db/models/notification_channel.py`
- `server/packages/db/models/reminder.py`
- `server/apps/backend/app/schemas/notification_channel.py`
- `server/apps/backend/alembic/versions/75e411962098_add_notification_enhancements.py` (new)
- `server/apps/backend/alembic/versions/a7b8c9d0e1f2_standardize_skill_id_names.py` (bugfix)
- `server/apps/backend/alembic/versions/x9876y54zqr0_add_task_tracking_fields.py` (bugfix)
- `server/apps/backend/alembic/versions/a1b2c3d4e5f7_add_last_synced_at_to_storage_backends.py` (bugfix)
- `server/apps/backend/alembic/versions/e4f5g6h7i8j9_fix_ai_agents_name_constraint.py` (bugfix)
- `server/apps/backend/alembic/versions/f5g6h7i8j9k0_add_family_id_to_storage_backends.py` (bugfix)
- `server/apps/backend/alembic/versions/c7timestz01_unify_datetime_to_timestamptz.py` (bugfix)
