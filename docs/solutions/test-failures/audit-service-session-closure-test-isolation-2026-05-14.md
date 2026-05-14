---
title: Audit Service Session Closure Breaks Test Isolation
date: 2026-05-14
category: test-failures
module: packages/domain/audit
problem_type: test_failure
component: testing_framework
symptoms:
  - Tests failing with ResourceClosedError: This transaction is closed
  - SQLAlchemy session thread-safety warnings in test output
root_cause: test_isolation
resolution_type: code_fix
severity: medium
tags:
  - sqlalchemy
  - session-management
  - test-isolation
  - audit-log
---

# Audit Service Session Closure Breaks Test Isolation

## Problem

`write_audit_log()` called `db.close()` in its `finally` block unconditionally. In tests where `SessionLocal` is patched to return a shared in-memory SQLite session, this closed the caller's session, causing subsequent operations on that session to raise `ResourceClosedError`.

## Symptoms

- `sqlalchemy.exc.ResourceClosedError: This transaction is closed` raised intermittently during test runs
- Failures appear in tests that exercise code paths calling `write_audit_log()` (auth flows, AI-gated endpoints)
- Error is non-deterministic — only surfaces when the patched session is reused across multiple operations in the same request lifecycle

## What Didn't Work

No failed investigation attempts were documented for this issue. The root cause was identified directly from the error message and the test fixture setup: the shared session object was being closed by `write_audit_log`'s `finally` block, which is correct behavior in production but destructive in tests where `SessionLocal()` returns the same object every time.

## Solution

Modified `write_audit_log()` in `packages/domain/audit/service.py` to accept an optional `db: Session | None = None` parameter with two execution paths:

**Before:**
```python
def write_audit_log(...) -> None:
    db = SessionLocal()
    try:
        entry = SecurityAuditLog(...)
        db.add(entry)
        db.commit()
    finally:
        db.close()
```

**After:**
```python
def write_audit_log(
    event_type: str,
    outcome: str,
    user_id: str | None = None,
    family_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    detail: str | None = None,
    db: Session | None = None,
) -> None:
    """Append a row to security_audit_logs. Fails silently.

    When db is provided, the entry is added to the caller's session (no commit/close).
    When db is None, a new session is created, committed, and closed.
    """
    if not settings.ENABLE_SECURITY_LOGGING:
        return
    try:
        from packages.db.models.security_audit_log import SecurityAuditLog

        if db is not None:
            entry = SecurityAuditLog(
                event_type=event_type,
                user_id=user_id,
                family_id=family_id,
                ip_address=ip_address,
                user_agent=user_agent,
                outcome=outcome,
                detail=detail,
            )
            db.add(entry)
            db.flush()
        else:
            own_db = SessionLocal()
            try:
                entry = SecurityAuditLog(
                    event_type=event_type,
                    user_id=user_id,
                    family_id=family_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    outcome=outcome,
                    detail=detail,
                )
                own_db.add(entry)
                own_db.commit()
            finally:
                own_db.close()
    except Exception as exc:
        logger.warning(f"[audit_log] failed to write event={event_type}: {exc}")
```

Updated 5 call sites to pass the request-scoped `db` session:

- `backend/app/services/auth.py` — 4 calls (`login_failed`, `login_success`, `token_refresh`, `password_change`)
- `backend/app/auth/ai_deps.py` — 1 call (`agent_request` in `verify_agent_token`)

## Why This Works

The root cause is **test isolation**: the test fixture patches `SessionLocal` to return a single shared session object. When `write_audit_log` called `db.close()` on what it believed was its own private session, it actually closed the shared test session. Any subsequent SQLAlchemy operation on that session raised `ResourceClosedError` because the underlying connection was gone.

By passing the caller's existing session into `write_audit_log`, the function participates in the caller's transaction rather than managing its own. `db.flush()` writes the audit entry to the database buffer without committing or closing — the caller retains full ownership of the session lifecycle. In production, this also has the benefit of making the audit log write atomic with the surrounding transaction: if the outer operation rolls back, the audit entry rolls back with it.

**Decision: `flush()` not `commit()` when using caller's session**

Using `flush()` writes the row to the DB within the current transaction without committing it. This keeps the audit entry atomic with the surrounding operation — if the caller's transaction rolls back, the audit entry rolls back too. This is the correct behavior for call sites like `login()` where the audit log and the auth response are part of the same logical unit.

## Prevention

### 1. Never close a session you did not open

Functions that accept a `db: Session` parameter must never call `db.close()` or `db.commit()`. Only the owner of the session (the dependency injector or the function that called `SessionLocal()`) should close it.

```python
# Correct — caller owns the session
def write_audit_log(action: str, db: Session) -> None:
    db.add(AuditLog(action=action))
    db.flush()  # not commit(), not close()

# Correct — function owns the session
def write_audit_log_standalone(action: str) -> None:
    db = SessionLocal()
    try:
        db.add(AuditLog(action=action))
        db.commit()
    finally:
        db.close()
```

### 2. Use the optional-session pattern for dual-mode functions

The `db: Session | None = None` signature is the standard pattern for service functions that need to work both as standalone utilities and as participants in a caller's transaction. Apply it to any function that previously owned its own session but is now called from request handlers.

### 3. Add fixture-level session health checks

Add a fixture-level check to catch premature session closure early:

```python
@pytest.fixture(autouse=True)
def assert_session_open(db_session):
    yield
    # Verify the shared session was not closed by application code
    assert db_session.is_active, "Test session was closed by application code — check for rogue db.close() calls"
```

### 4. Code review checklist item

When reviewing any function that accepts a `Session` parameter, verify it does not call `db.close()` or `db.commit()`. These calls belong exclusively to the session owner.

## Related Issues

- [deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md](../integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md) — Shares patterns around resource lifecycle management and silent failures masked by exception handling