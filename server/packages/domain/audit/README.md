# packages/domain/audit

Owns security audit log writes and scheduled purge of old entries.

## Public API

| Name | Signature | What it does |
|------|-----------|--------------|
| `write_audit_log` | `(event_type, outcome, user_id?, family_id?, ip_address?, user_agent?, detail?, db?) -> None` | Appends a row to `security_audit_logs`. Fails silently on error. |
| `purge_old_audit_logs` | `(retention_days=90) -> int` | Deletes audit log entries older than `retention_days`. Returns count deleted. |

## Consumers

- `apps/backend` — calls both `write_audit_log` and `purge_old_audit_logs` (re-exported via `app/services/audit_log.py`)
- `apps/scheduler_worker` — calls `purge_old_audit_logs` on a scheduled job

## Calling Conventions

`write_audit_log` has two modes depending on whether `db` is provided:

- **`db` provided** — entry is added to the caller's existing session with `flush()`. No commit, no session close. The caller is responsible for committing.
- **`db=None` (default)** — the function opens its own `SessionLocal()`, commits, and closes it. Use this when calling outside a request context (e.g., from middleware or background tasks).

`purge_old_audit_logs` always opens its own session internally. Do not pass a session.

## Links

- [packages/domain README](../README.md) — subdomain map and import rules
