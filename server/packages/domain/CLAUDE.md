# domain/CLAUDE.md

Module-specific guidance for the business logic layer.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Key Invariants

1. **Import direction** — `packages/domain` must never import from `apps/`. Dependency flow is one-way: `apps/` → `packages/`. Violating this creates circular imports.
2. **No cross-subdomain imports** — subpackages (`audit`, `device`, `exchange_rate`, `notification`, `snapshot`) must not import from each other. Cross-subdomain calls go through the app layer, not directly between domain services.
3. **Domain services receive a `Session` parameter** — they never create their own `SessionLocal()`. The caller (app router or scheduler job) is responsible for session lifecycle. Exception: `audit.service.purge_old_audit_logs` is permitted to create its own `SessionLocal()` because it is called by the scheduler worker outside a request context where no session is passed in.

## Don't Do

- **Don't import across subdomains** — `audit` must not import from `device`, `exchange_rate`, etc. Route cross-domain logic through the app layer.
- **Don't create `SessionLocal()` inside a domain service** — accept a `Session` parameter instead. The one exception (`audit.service.purge_old_audit_logs`) is already documented and must not be replicated.

## Subpackages

| Subpackage | Key exports | Purpose |
|------------|-------------|---------|
| `audit` | `write_audit_log`, `purge_old_audit_logs` | Security/audit log write + retention purge |
| `device` | `cleanup_expired_device_sessions`, `cleanup_expired_revoked_tokens` | Device session lifecycle, JWT revocation cleanup |
| `exchange_rate` | `ExchangeRateService` | Fetch + cache foreign-exchange rates |
| `notification` | `run_scheduled_checks` and channel/reminder dispatch | Reminder evaluation + notification channel dispatch (`reminder_job` calls this) |
| `snapshot` | `auto_generate_daily_snapshots` | Per-family net-worth snapshot generation |

Reminders are owned by the `notification` subpackage (not a separate `reminder/` subpackage). The `reminder` routers in `apps/backend` and the `reminder_daily` scheduler job both dispatch into `notification.service.run_scheduled_checks`.

## Patterns

### Domain service signature

```python
# ✅ Correct — accept Session, never create one
from sqlalchemy.orm import Session

def my_service_function(db: Session, ...) -> ...:
    ...

# ❌ Wrong — domain services must not create their own session
def my_service_function(...) -> ...:
    db = SessionLocal()  # violates invariant
```

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, subpackage inventory
