# packages/domain/device

Owns device session lifecycle — marking expired sessions as revoked and hard-deleting old revoked sessions.

## Public API

| Name | Signature | What it does |
|------|-----------|--------------|
| `cleanup_expired_device_sessions` | `(db: Session) -> int` | Marks all sessions past their `expires_at` as revoked. Returns count updated. |
| `delete_old_revoked_sessions` | `(db: Session) -> int` | Hard-deletes revoked sessions with `last_seen_at` older than 7 days. Returns count deleted. |

## Consumers

- `apps/scheduler_worker` — calls both functions on scheduled jobs

## Calling Conventions

Both functions take a `Session` parameter. Each function calls `db.commit()` internally — the caller creates and closes the session but does **not** commit (the service commits on the caller's behalf).

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
