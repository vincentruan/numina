---
date: 2026-05-31
topic: auth-security-hardening-r6-r11
source: docs/brainstorms/2026-05-31-auth-security-hardening-requirements.md
status: planning
priority: P1 (R6) → P2 (R7, R8) → P3 (R9, R10) → optional (R11)
---

# Auth Security Hardening — R6–R11 Implementation Plan

## Overview

R1–R5 are complete. This plan covers the six residual hardening items identified
during code review. Each task is scoped to be completable in a single session and
has explicit acceptance criteria and a paired test task.

---

## Dependency Map

```
R6 (concurrent refresh fix)   — no deps, implement first
R7 (password strength)        — no deps, can run in parallel with R6
R8 (audit log query API)      — no deps, can run in parallel with R7
R9 (Retry-After header)       — depends on understanding AppError → JSONResponse flow (done)
R10 (invite-code rate limit)  — pattern established by R4; no hard deps
R11 (tamper detection)        — optional; R8 should land first so the log is queryable
```

---

## R6 — Concurrent Refresh Race Condition Fix

**Priority: P1**
**Files:** `server/packages/security/revoke_jti.py`, `server/packages/db/models/revoked_token.py`, `server/apps/backend/app/services/auth.py`

### Background

`refresh_token()` in `auth.py` currently:
1. Calls `_verify_token()` (checks revocation)
2. Calls `revoke_jti()` (writes revocation)
3. Issues new token pair

Between steps 1 and 2 there is a window where a second concurrent request with the
same refresh token passes the revocation check before the first request has written
the revocation record. The fix uses SQLite's `INSERT OR IGNORE` + affected-rows
check to make the revocation atomic.

The `RevokedToken.jti` column already has `unique=True` in the model
(`server/packages/db/models/revoked_token.py` line 15), so the UNIQUE constraint
exists at the ORM level. Verify it is present in the migration before proceeding.

### Task R6-1 — Verify UNIQUE constraint exists in migration

- Check `server/apps/backend/alembic/versions/` for the migration that created
  `revoked_tokens` and confirm `jti` has a UNIQUE constraint in the DDL.
- If missing, generate a new migration:
  `uv run alembic revision --autogenerate -m "add unique constraint to revoked_tokens.jti"`
- Acceptance: `PRAGMA index_list('revoked_tokens')` shows a unique index on `jti`.

### Task R6-2 — Add `revoke_jti_atomic()` to `revoke_jti.py`

Add a new function alongside the existing `revoke_jti()`:

```python
def revoke_jti_atomic(jti: str, ttl_seconds: float) -> bool:
    """Atomically revoke a JTI using INSERT OR IGNORE.

    Returns True if this call won the race (row inserted),
    False if another request already revoked this JTI.
    """
```

Implementation notes:
- Use `text("INSERT OR IGNORE INTO revoked_tokens (jti, revoked_at, expires_at) VALUES (:jti, :revoked_at, :expires_at)")`
  with `db.execute()` and check `result.rowcount == 1`.
- Open and close its own `SessionLocal()` session (same pattern as `revoke_jti()`).
- Do NOT modify the existing `revoke_jti()` — it is used by other callers and
  changing its signature would break them.
- Acceptance: function exists, passes lint (`uv run ruff check packages/security/`),
  passes mypy (`uv run mypy packages/security/ --explicit-package-bases`).

### Task R6-3 — Reorder `refresh_token()` to revoke-before-issue

In `server/apps/backend/app/services/auth.py`, change `refresh_token()`:

Current order:
1. `_verify_token()` — checks revocation
2. Issue new tokens
3. `revoke_jti()` — revoke old JTI

New order:
1. `_verify_token()` — checks revocation (keep as-is)
2. `revoke_jti_atomic(old_jti, ...)` — atomically revoke old JTI
3. If `revoke_jti_atomic` returns `False` → raise `AppError(ErrorCode.AUTH_REFRESH_FAILED)`
4. Issue new token pair (only reached if revocation succeeded)

The import path for `revoke_jti_atomic` follows the existing pattern:
`from apps.backend.app.auth.revoke_jti import revoke_jti_atomic`

Note: `apps/backend/app/auth/revoke_jti.py` is a re-export shim — check whether
it re-exports from `packages/security/revoke_jti.py` and add `revoke_jti_atomic`
to that re-export.

- Acceptance: `refresh_token()` raises 401 on the second concurrent call with the
  same refresh token.

### Task R6-4 — Test: concurrent refresh returns 401 on second call

File: `server/tests/backend/test_jti_revocation.py` (add to existing file)

```python
def test_concurrent_refresh_second_call_rejected(client, auth_headers):
    """Second refresh with the same token is rejected even if called concurrently."""
    old_refresh = auth_headers["_refresh_token"]

    # First call succeeds
    resp1 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp1.status_code == 200

    # Second call with the same old token must be rejected
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp2.status_code == 401
```

Also add a unit test for `revoke_jti_atomic()` that verifies the second call
returns `False` when the JTI is already revoked.

- Run: `uv run pytest server/tests/backend/test_jti_revocation.py -v`
- Acceptance: all tests pass.

---

## R7 — Password Strength Validation

**Priority: P2**
**Files:** `server/apps/backend/app/schemas/auth.py`, `server/apps/backend/app/services/auth.py`

### Background

Neither `register()` nor `change_password()` enforce password strength. The fix
adds a shared Pydantic validator so both paths reject weak passwords at the schema
layer (422 response), before any bcrypt work.

The existing test `test_change_password_weak_new_password` in
`test_auth_security.py` already asserts 422 for a short password — it will start
passing once R7 is implemented.

### Task R7-1 — Add `validate_password_strength()` validator to auth schemas

In `server/apps/backend/app/schemas/auth.py`:

- Add a module-level helper `_check_password_strength(v: str) -> str` that raises
  `ValueError` with a Chinese message if:
  - `len(v) < 8` → `"密码长度不能少于8位"`
- Apply it as a `@field_validator("password")` on `RegisterRequest` and as a
  `@field_validator("new_password")` on `ChangePasswordRequest` (or whatever the
  schema is named — check the file before editing).
- Acceptance: `RegisterRequest(password="weak")` raises `ValidationError`;
  `RegisterRequest(password="StrongPass1")` does not.

### Task R7-2 — Add "same as old password" check in `change_password()`

In `server/apps/backend/app/services/auth.py`, inside `change_password()`:

After verifying `old_password` is correct, add:
```python
if verify_password(new_password, user.password_hash):
    raise AppError(ErrorCode.AUTH_PASSWORD_INCORRECT)  # reuse existing code, or add new one
```

Consider whether a dedicated `AUTH_PASSWORD_SAME_AS_OLD` error code is warranted.
Given the self-hosted family context, reusing `AUTH_PASSWORD_INCORRECT` with a
distinct Chinese message is acceptable. Add the check and update the zh-CN locale
if a new code is added.

- Acceptance: `change_password(db, user, old, new)` raises when `new == old`.

### Task R7-3 — Test: password strength validation

Add to `server/tests/backend/test_auth_security.py`:

```python
# R7 — password strength
def test_register_rejects_short_password(client):
    """Registration with < 8 char password returns 422."""
    resp = client.post("/api/v1/auth/register", json={
        "username": "weakpwuser",
        "display_name": "Weak",
        "password": "short",
        "family_name": "Test",
        "family_invitation_code": "AUTO-WEAK",
    })
    assert resp.status_code == 422

def test_change_password_rejects_same_as_old(client, auth_headers):
    """Changing to the same password returns 400."""
    resp = client.post(
        "/api/v1/auth/me/password",
        json={"old_password": "TestPass123", "new_password": "TestPass123"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
```

The existing `test_change_password_weak_new_password` test (already in the file,
currently failing) should pass after R7-1 lands.

- Run: `uv run pytest server/tests/backend/test_auth_security.py -v -k "password"`
- Acceptance: all password-related tests pass including the pre-existing weak-password test.

---

## R8 — Audit Log Query Endpoint

**Priority: P2**
**Files:** `server/apps/backend/app/routers/` (new file), `server/apps/backend/app/schemas/` (new schema), `server/apps/backend/app/main.py`

### Background

`security_audit_logs` table exists and is written to. R5.5 noted the missing query
endpoint. The endpoint is owner-only (uses `require_owner` dep from
`apps/backend/app/auth/deps.py`).

### Task R8-1 — Add `AuditLogResponse` schema

In `server/apps/backend/app/schemas/audit_log.py` (new file):

```python
from datetime import datetime
from pydantic import ConfigDict
from apps.backend.app.schemas.base import SnowflakeBase

class AuditLogResponse(SnowflakeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    user_id: int | None
    family_id: int | None
    ip_address: str | None
    user_agent: str | None
    outcome: str
    detail: str | None
    created_at: datetime

class AuditLogListResponse(SnowflakeBase):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
```

`SnowflakeBase` handles `id`, `user_id`, `family_id` → string serialization
automatically. Do not add manual `str()` calls.

- Acceptance: schema imports cleanly, mypy passes.

### Task R8-2 — Add `GET /admin/audit-logs` router

Create `server/apps/backend/app/routers/admin_audit_logs.py`:

```python
router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    event_type: str | None = Query(None),
    user_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
```

Implementation notes:
- Filter by `family_id == user.family_id` always (tenant isolation).
- Apply optional filters: `event_type`, `user_id`, `created_at >= date_from`,
  `created_at <= date_to`.
- Pagination: `offset = (page - 1) * page_size`, `limit = page_size`.
- Return `total` from a `COUNT(*)` query with the same filters (no pagination).
- Order by `created_at DESC`.
- Use `""` not `"/"` on the decorator (root CLAUDE.md URL style rule).

Register in `server/apps/backend/app/main.py`:
```python
from apps.backend.app.routers import admin_audit_logs
app.include_router(admin_audit_logs.router, prefix="/api/v1")
```

- Acceptance: `GET /api/v1/admin/audit-logs` returns 200 for owner, 403 for member.

### Task R8-3 — Test: audit log query endpoint

Create `server/tests/backend/test_admin_audit_logs.py`:

```python
def test_owner_can_list_audit_logs(client, auth_headers):
    """Owner gets 200 with items list."""
    resp = client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data

def test_member_cannot_list_audit_logs(client, member_headers):
    """Member gets 403."""
    resp = client.get("/api/v1/admin/audit-logs", headers=member_headers)
    assert resp.status_code == 403

def test_audit_log_pagination(client, auth_headers):
    """page and page_size params are respected."""
    resp = client.get("/api/v1/admin/audit-logs?page=1&page_size=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) <= 5

def test_audit_log_filter_by_event_type(client, auth_headers):
    """event_type filter returns only matching rows."""
    resp = client.get(
        "/api/v1/admin/audit-logs?event_type=login_success",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    for item in resp.json()["data"]["items"]:
        assert item["event_type"] == "login_success"

def test_audit_log_user_id_serialized_as_string(client, auth_headers):
    """user_id in response is a string (SnowflakeBase serialization)."""
    resp = client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    for item in items:
        if item["user_id"] is not None:
            assert isinstance(item["user_id"], str)
```

Note: `member_headers` fixture may need to be added to the shared conftest if it
does not already exist. Check `server/tests/backend/` for an existing conftest
before creating one.

- Run: `uv run pytest server/tests/backend/test_admin_audit_logs.py -v`
- Acceptance: all tests pass.

---

## R9 — Rate Limit Retry-After Header

**Priority: P3**
**Files:** `server/apps/backend/app/error_handlers.py`, `server/apps/backend/app/errors/exceptions.py`

### Background

`AppError(ErrorCode.AUTH_RATE_LIMITED)` is raised by the rate-limit helpers in
`auth.py`. The `app_error_handler` in `error_handlers.py` converts it to a
`JSONResponse` with status 429 but no `Retry-After` header. Clients cannot
implement smart backoff without this header.

The TTL information is available at the call site (e.g. `ttl_seconds=60` for
refresh, `ttl_seconds=3600` for password change) but is not currently threaded
through to the error handler.

### Task R9-1 — Add `retry_after` field to `AppError`

In `server/apps/backend/app/errors/exceptions.py`, add an optional `retry_after`
parameter:

```python
class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        details: dict | None = None,
        retry_after: int | None = None,   # seconds
    ):
        self.code = code
        self.details = details
        self.retry_after = retry_after
```

- Acceptance: `AppError(ErrorCode.AUTH_RATE_LIMITED, retry_after=60)` stores the value.

### Task R9-2 — Emit `Retry-After` header in `app_error_handler`

In `server/apps/backend/app/error_handlers.py`, update `app_error_handler`:

```python
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    ...
    headers = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=ERROR_META[exc.code],
        content=_error_envelope(...),
        headers=headers,
    )
```

- Acceptance: 429 responses include `Retry-After` header when `retry_after` is set.

### Task R9-3 — Pass `retry_after` from rate-limit helpers

In `server/apps/backend/app/services/auth.py`, update the three rate-limit helpers
to pass `retry_after` when raising:

- `_check_refresh_rate_limit`: `raise AppError(ErrorCode.AUTH_RATE_LIMITED, retry_after=60)`
- `_check_password_change_rate_limit`: `raise AppError(ErrorCode.AUTH_RATE_LIMITED, retry_after=3600)`
- `_check_rate_limit` (login): `raise AppError(ErrorCode.AUTH_RATE_LIMITED, retry_after=lockout_seconds)`
- `_check_register_rate_limit`: `raise AppError(ErrorCode.AUTH_RATE_LIMITED, retry_after=3600)`

Use the cache TTL (`cache.get_ttl(key)`) where available for a more precise value;
fall back to the configured window constant.

- Acceptance: 429 responses from these endpoints include `Retry-After`.

### Task R9-4 — Test: Retry-After header present on 429

Add to `server/tests/backend/test_auth_security.py`:

```python
def test_refresh_rate_limit_includes_retry_after(client, auth_headers):
    """429 from refresh rate limit includes Retry-After header."""
    from jose import jwt
    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service
    from apps.backend.app.services.cache.factory import get_rate_limit_cache

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    cache = get_rate_limit_cache()
    key = f"refresh_attempts:{user_id}"
    cache.set(key, auth_service._REFRESH_RATE_LIMIT_PER_MINUTE, ttl_seconds=60)

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": auth_headers["_refresh_token"]})
    assert resp.status_code == 429
    assert "retry-after" in {h.lower() for h in resp.headers}
    assert int(resp.headers["retry-after"]) > 0
```

- Run: `uv run pytest server/tests/backend/test_auth_security.py -v -k "retry_after"`
- Acceptance: test passes.

---

## R10 — Invite Code Rate Limiting

**Priority: P3**
**Files:** `server/apps/backend/app/routers/family.py`, `server/apps/backend/app/services/auth.py` (or a new `family.py` service)

### Background

`POST /family/invite-code` in `family.py` calls `family_service.regenerate_invite_code()`
with no rate limiting. The pattern for adding per-user rate limiting is established
by `_check_refresh_rate_limit` and `_check_password_change_rate_limit` in `auth.py`.

### Task R10-1 — Add `_check_invite_code_rate_limit()` helper

Add to `server/apps/backend/app/services/auth.py` (or to a new
`server/apps/backend/app/services/family.py` if one exists — check first):

```python
_INVITE_CODE_RATE_LIMIT_PER_HOUR = 5

def _check_invite_code_rate_limit(user_id: str) -> None:
    """Limit invite code regeneration to 5 per hour per user."""
    try:
        from apps.backend.app.services.cache.factory import get_rate_limit_cache
        cache = get_rate_limit_cache()
        key = f"invite_code_attempts:{user_id}"
        count = cache.get(key)
        if count is not None and int(count) >= _INVITE_CODE_RATE_LIMIT_PER_HOUR:
            raise AppError(ErrorCode.AUTH_RATE_LIMITED, retry_after=3600)
        new_count = cache.increment(key)
        if new_count == 1:
            cache.set(key, 1, ttl_seconds=3600)
    except AppError:
        raise
    except Exception:
        pass
```

- Acceptance: function exists, lint and mypy pass.

### Task R10-2 — Call rate limit check in `regenerate_invite_code` router

In `server/apps/backend/app/routers/family.py`, update `regenerate_invite_code`:

```python
@router.post("/invite-code")
def regenerate_invite_code(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if user.role != 'owner':
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    _check_invite_code_rate_limit(str(user.id))   # add this line
    family = family_service.regenerate_invite_code(db, user)
    return {"invite_code": family.invite_code}
```

Import `_check_invite_code_rate_limit` from wherever it was placed in R10-1.

Also write an audit log entry on rate-limit hit (follow the pattern in
`_check_refresh_rate_limit` which calls `_log_security_event`).

- Acceptance: 6th call within an hour returns 429.

### Task R10-3 — Test: invite code rate limiting

Add to `server/tests/backend/test_family.py` (or create
`server/tests/backend/test_invite_code_rate_limit.py`):

```python
def test_invite_code_rate_limit(client, auth_headers):
    """6th invite code regeneration within an hour returns 429."""
    from jose import jwt
    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services.cache.factory import get_rate_limit_cache
    from apps.backend.app.services.auth import _INVITE_CODE_RATE_LIMIT_PER_HOUR

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    cache = get_rate_limit_cache()
    key = f"invite_code_attempts:{user_id}"
    cache.set(key, _INVITE_CODE_RATE_LIMIT_PER_HOUR, ttl_seconds=3600)

    resp = client.post("/api/v1/family/invite-code", headers=auth_headers)
    assert resp.status_code == 429
```

- Run: `uv run pytest server/tests/backend/ -v -k "invite_code"`
- Acceptance: test passes.

---

## R11 — Audit Log Tamper Detection (Optional)

**Priority: optional**
**Files:** `server/packages/domain/audit/service.py`, `server/packages/db/models/security_audit_log.py`

This item is optional and should only be implemented after R8 is live (so the log
is queryable before adding integrity features).

### Task R11-1 — Log purge execution as an audit event (minimum viable)

In `server/packages/domain/audit/service.py`, update `purge_old_audit_logs()` to
write a self-audit entry after the purge:

```python
write_audit_log(
    event_type="audit_log_purge",
    outcome="success",
    detail=f"purged {count} entries older than {retention_days} days",
)
```

This prevents silent deletion — every purge is itself recorded. The entry is
written in a new session after the purge commits, so it survives even if the
purge count is 0.

- Acceptance: after `purge_old_audit_logs()` runs, a row with
  `event_type="audit_log_purge"` exists in the table.

### Task R11-2 — Evaluate chain hashing (deferred decision)

Chain hashing (each row stores `SHA256(prev_hash + row_data)`) requires:
- A new `prev_hash` column on `security_audit_logs`
- An Alembic migration
- Sequential INSERT (cannot be parallelized)
- A separate verification endpoint or CLI command

Given the self-hosted single-writer context, the complexity is justified only if
the threat model includes an attacker with direct SQLite file access who also
wants to cover their tracks. Recommend deferring until R8 is in production and
the audit log is actively used.

If implemented, the verification logic belongs in
`server/packages/domain/audit/service.py` as `verify_audit_log_integrity(db)`.

### Task R11-3 — Webhook export (deferred decision)

Periodic export to an external webhook (e.g. ntfy, Slack, custom endpoint) would
provide off-device tamper evidence. This is a scheduler_worker job, not a backend
endpoint. Defer until the notification channel infrastructure (already present in
`packages/domain/notification/`) is evaluated for reuse.

---

## Execution Order

| Step | Task(s) | Can parallelize? |
|------|---------|-----------------|
| 1 | R6-1 (verify migration) | — |
| 2 | R6-2 (revoke_jti_atomic), R7-1 (schema validator), R8-1 (schema) | yes |
| 3 | R6-3 (reorder refresh_token), R7-2 (same-as-old check), R8-2 (router) | yes |
| 4 | R6-4 (tests), R7-3 (tests), R8-3 (tests) | yes |
| 5 | R9-1, R9-2, R9-3 (Retry-After) | sequential within R9 |
| 6 | R9-4 (tests), R10-1, R10-2 | yes |
| 7 | R10-3 (tests) | — |
| 8 | R11-1 (purge audit) | — |
| 9 | R11-2, R11-3 (evaluate/defer) | — |

---

## Quality Gates (per task)

Run from `server/` after each task:

```bash
uv run ruff check apps/backend/ packages/security/ packages/domain/
uv run mypy apps/backend/app/
uv run pytest server/tests/backend/ -v -k "<relevant keyword>"
```

No task is complete until all three pass.

---

## Key Constraints (from CLAUDE.md)

- `packages/security/` must not import from `apps/` — `revoke_jti_atomic` stays in `packages/security/revoke_jti.py`
- All response schemas with IDs inherit from `SnowflakeBase` — `AuditLogResponse` must do this
- Router root-path decorators use `""` not `"/"` — `@router.get("")` not `@router.get("/")`
- Auth rate-limit errors return 429 via `ErrorCode.AUTH_RATE_LIMITED` → `ERROR_META` mapping (already set)
- Domain services receive a `Session` parameter — `purge_old_audit_logs` is the documented exception
