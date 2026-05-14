# packages/domain/notification

Owns scheduled notification dispatch — reminders and alerts for family members.

## Public API

| Name | Signature | What it does |
|------|-----------|--------------|
| `run_scheduled_checks` | `(db: Session) -> None` | Runs all scheduled notification checks. Called by `scheduler_worker`. |

## Consumers

- `apps/scheduler_worker` — calls `run_scheduled_checks` on a scheduled job

## Calling Conventions

Standard `Session` parameter. The caller creates and manages the session lifecycle.

## ⚠️ Phase 2 Stub (Extraction Deferred to Phase 3)

`run_scheduled_checks` is a **Phase 2 stub**. It does not contain notification logic directly — it lazy-imports the real implementation from `apps/backend`:

```
apps.backend.app.services.notification.dispatcher.run_scheduled_checks
```

**Requirement:** `apps/backend` must be present in the Python path when this function is called. If the import fails, the function raises `RuntimeError` with a descriptive message.

This coupling will be removed in Phase 3 when the notification logic is fully extracted into this package.

## Phase 3 Removal Checklist

When extracting notification logic from `apps/backend`:

1. Move `apps/backend/app/services/notification/dispatcher.py` into `packages/domain/notification/`
2. Update `scheduler_worker` job imports to call `packages.domain.notification.run_scheduled_checks` directly (no backend path needed)
3. Remove the lazy-import wrapper from `packages/domain/notification/service.py`
4. Run `pytest packages/domain/notification/ -v` and `pytest apps/scheduler_worker/ -v` — both must pass
5. Remove the Python path requirement for `apps/backend` in scheduler_worker deployment

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
