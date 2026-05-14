# packages/domain/snapshot

Owns daily asset snapshot generation — computing and persisting net worth snapshots for all families.

## Public API

| Name | Signature | What it does |
|------|-----------|--------------|
| `auto_generate_daily_snapshots` | `(db: Session) -> None` | Generates today's snapshots for all families. Called by `scheduler_worker`. |

## Consumers

- `apps/scheduler_worker` — calls `auto_generate_daily_snapshots` on a scheduled job

## Calling Conventions

Standard `Session` parameter. The caller creates and manages the session lifecycle.

## ⚠️ Phase 2 Stub (Extraction Deferred to Phase 3)

`auto_generate_daily_snapshots` is a **Phase 2 stub**. It does not contain snapshot logic directly — it lazy-imports the real implementation from `apps/backend`:

```
apps.backend.app.services.snapshot.auto_generate_daily_snapshots
```

**Requirement:** `apps/backend` must be present in the Python path when this function is called. If the import fails, the function raises `RuntimeError` with a descriptive message.

This coupling will be removed in Phase 3 when the snapshot logic is fully extracted into this package.

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
