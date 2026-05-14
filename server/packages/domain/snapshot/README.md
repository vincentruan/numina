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

## Phase 3 Removal Checklist

When extracting snapshot logic from `apps/backend`:

1. Move `apps/backend/app/services/snapshot.py` into `packages/domain/snapshot/`
2. Update `scheduler_worker` job imports to call `packages.domain.snapshot.auto_generate_daily_snapshots` directly (no backend path needed)
3. Remove the lazy-import wrapper from `packages/domain/snapshot/service.py`
4. Run `pytest packages/domain/snapshot/ -v` and `pytest apps/scheduler_worker/ -v` — both must pass
5. Remove the Python path requirement for `apps/backend` in scheduler_worker deployment

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
