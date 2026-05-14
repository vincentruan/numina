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

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
