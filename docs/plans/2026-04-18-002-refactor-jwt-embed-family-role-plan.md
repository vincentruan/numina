---
title: refactor: JWT embed family_id and role — eliminate DB query per request
type: refactor
status: completed
date: 2026-04-18
origin: docs/ideation/2026-04-17-performance-caching-ideation.md (idea #6)
---

# refactor: JWT embed family_id and role — eliminate DB query per request

## Overview

Every authenticated request currently queries the `users` table in `get_current_user` to fetch `family_id` and `role`. JWT payload already contains `fid` (family_id) for adult tokens and `role` for child tokens, but `_verify_token` discards these and returns only `user_id`. This refactor reads `fid` and `role` directly from JWT, reducing each authenticated request's DB workload from a full user query to a minimal existence check.

## Problem Frame

Family-scoped multi-tenant app with JWT auth. Current flow per authenticated request:

1. `_verify_token` decodes JWT, extracts only `sub` (user_id)
2. `get_current_user` queries DB: `db.query(User).filter(User.id == user_id, User.is_active == True).first()`
3. User object used for `user.family_id` and `user.role` in downstream logic

Ideation #6 noted: embedding `family_id` and `role` in JWT eliminates the DB query. Trade-off: role changes take up to 15 minutes (access token TTL) to propagate — acceptable for family app scenario.

**Current JWT payload structure (from auth service):**
- Adult tokens: `{"sub": user.id, "fid": user.family_id}` — fid already embedded, role missing
- Child tokens: `{"sub": child.id, "role": "child"}` — role already embedded

## Requirements Trace

- R1. Every authenticated request reads `family_id` and `role` from JWT payload, not from DB
- R2. Minimal DB query: only verify user exists and `is_active` (security: revoked users must not authenticate)
- R3. Adult tokens embed `role` in payload (currently missing)
- R4. Role change propagation latency ≤ 15 minutes (access token TTL) — accepted trade-off

## Scope Boundaries

- NOT: Changing JWT structure beyond adding `role` field to adult tokens and `fid` field to child tokens (see Unit 2 modification to child token creation)
- NOT: Eliminating all DB queries (existence check + family_id retrieval for child auth remains)
- NOT: Modifying refresh token validation logic (follows same pattern as access) — but refresh token paths that CREATE new access tokens will pass role in payload (Unit 5)

## Context & Research

### Relevant Code and Patterns

- `backend/app/auth/deps.py`: `create_access_token`, `_verify_token`, `get_current_user`
- `backend/app/services/auth.py`: Token creation at login/register/refresh (lines 286-287, 315-316, 355-356)
- Current pattern: `_verify_token` returns `str | None` (user_id only)

### Key Technical Decisions

- **Decision: Minimal existence check required.** Cannot skip DB entirely — must verify user still exists and `is_active`. Security concern: deleted/deactivated users with valid tokens must be rejected.
- **Decision: Return payload dict from `_verify_token`.** Change return type from `str | None` to `dict | None` with keys `sub`, `fid`, `role`. Returns dict instead of constructing fake User object to reduce coupling. Payload provides `id`, `family_id`, `role` — sufficient for 95% of endpoints. Rare endpoints needing full User can query explicitly.
- **Decision: Adult tokens add `role` field.** Current adult tokens only have `fid`. Add `role: "owner" | "member"` at token creation to match child token pattern.
- **Decision: Access tokens will NOT embed `token_version`.** Consistent with current design — force-logout relies on refresh token validation checking token_version mismatch. Access token holders remain valid until TTL expires (15 min max). This trade-off is acceptable: (a) force-logout immediately blocks refresh operations, (b) access tokens have short TTL limiting exposure window.
- **Decision: Preserve all existing revocation checks.** `_verify_token` keeps JTI revocation (`_is_jti_revoked`), per-user iat-based revocation (`_is_token_revoked_for_user`). Only return type changes from `str` to `dict`. All security checks unchanged.

## Implementation Units

- [x] **Unit 1: Modify `_verify_token` to return full payload**

**Goal:** Extract and return `sub`, `fid`, `role` from JWT instead of just user_id

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `backend/app/auth/deps.py` (function `_verify_token`)
- Test: `backend/tests/test_auth.py`

**Approach:**
- Change `_verify_token` signature: return `dict | None` with keys `sub`, `fid`, `role`
- Add default handling: `fid` defaults to `None` (child tokens lack fid), `role` defaults to `"member"` (backward compat)
- **SECURITY: Keep existing revocation checks unchanged** — JTI check (line 133), iat-based per-user revocation (line 135), type validation. Only return type changes.
- Update callers: `get_current_user`, `get_current_user_from_cookie`, `get_current_child_user`, `get_refresh_token_from_cookie` (line 249), `get_child_refresh_token_from_cookie` (line 328)
- Also update: `auth.py` refresh_token function (line 326) which calls `_verify_token(refresh_tok, 'refresh')`

**Patterns to follow:**
- Existing `_verify_token` structure (try/except JWTError, payload.get pattern)

**Test scenarios:**
- Happy path: valid adult token returns payload with sub, fid, role
- Happy path: valid child token returns payload with sub, role="child", fid (now embedded via Unit 2)
- Error path: expired token returns None
- Error path: invalid signature returns None
- Edge case: token missing fid field returns payload with fid=None (backward compat for old tokens)
- Edge case: revoked JTI returns None
- Edge case: token with iat <= user_revocation_times[user_id] returns None (per-user iat revocation preserved)

**Verification:**
- All existing auth tests pass (no regression)
- Token decode returns expected payload fields

---

- [x] **Unit 2: Add `role` to adult token payload**

**Goal:** Adult access/refresh tokens embed `role` alongside existing `fid`

**Requirements:** R3

**Dependencies:** Unit 1 (payload structure)

**Files:**
- Modify: `backend/app/services/auth.py` (register, login, refresh, join_family)
- Modify: `backend/app/auth/deps.py` (create_access_token, create_refresh_token — no change needed, payload passed as-is)

**Approach:**
- At token creation in auth_service: pass `{"sub": user.id, "fid": user.family_id, "role": user.role}`
- Existing locations: lines 286-287, 315-316, 355-356, 380-381
- **CRITICAL: Child tokens MUST also embed `fid`.** Child tokens currently only have `{sub, role}` (auth.py:488-489). Child endpoints (milestones.py:34, coins.py:68) require `family_id` for data scoping. Modify child token creation to include `fid: child.family_id` at auth.py:488-489 and 544. This extends scope boundary slightly but is necessary for plan viability.
- No change to child tokens role (already have role="child")

**Patterns to follow:**
- Existing `create_access_token({"sub": ..., "fid": ...})` pattern

**Test scenarios:**
- Happy path: owner user token contains role="owner"
- Happy path: member user token contains role="member"
- Integration: decoded adult token payload matches user.role

**Verification:**
- Token creation includes role field for adult users
- Child tokens unchanged

---

- [x] **Unit 3: Refactor `get_current_user` to use embedded payload**

**Goal:** Eliminate full User query, use minimal existence check + token payload

**Requirements:** R1, R2

**Dependencies:** Unit 1, Unit 2

**Files:**
- Modify: `backend/app/auth/deps.py` (get_current_user, get_current_user_from_cookie)

**Approach:**
- `_verify_token` returns payload dict
- Minimal DB check: `db.query(User.id).filter(User.id == payload["sub"], User.is_active == True).first() is not None` — scalar check, not object load. SQLAlchemy Query objects don't have `.exists()` method; use `.first() is not None` pattern.
- **CRITICAL: Family_id verification.** For adult endpoints, minimal check must also verify `payload["fid"]` matches current DB family_id to prevent cross-family data access after user removal. Query: `db.query(User.family_id).filter(User.id == payload["sub"], User.is_active == True).first()` returns `(family_id,)` tuple. Assert: `returned_family_id == payload["fid"]` or return 401 if mismatch.
- Construct minimal User-like object with `id`, `family_id` (from payload), `role` (from payload)
- OR: Return payload dict and let callers use directly (less coupling)
- Keep `_assert_not_child` check using payload role
- **SECURITY: Preserve Bearer precedence over Cookie.** If Bearer token provided, payload from Bearer is used (ignoring Cookie). This prevents session hijacking vulnerability documented in existing code (lines 183-192).

**Patterns to follow:**
- Existing `get_current_user` security checks (Bearer precedence over Cookie)

**Test scenarios:**
- Happy path: valid token authenticates without User object query
- Error path: deleted user (not in DB) returns 401
- Error path: deactivated user (is_active=False) returns 401
- Edge case: Bearer token precedence over Cookie preserved
- Integration: authenticated request uses payload.family_id for scoping

**Verification:**
- DB query count reduced per authenticated request (profile or logging)
- All downstream endpoints work with payload-based user

---

- [x] **Unit 4: Update child auth paths**

**Goal:** Child token verification uses embedded role, minimal DB check

**Requirements:** R1, R2

**Dependencies:** Unit 1

**Files:**
- Modify: `backend/app/auth/deps.py` (get_current_child_user, child refresh functions)

**Approach:**
- Same pattern as Unit 3: payload dict + minimal existence check
- Child tokens now have fid embedded (Unit 2 change), so payload provides family_id
- **SECURITY: Minimal existence check MUST include role='child' filter and family_id verification.** Preserves adult/child endpoint isolation — prevents adult tokens from accessing child endpoints. Query: `db.query(User.family_id).filter(User.id == payload["sub"], User.is_active == True, User.role == "child").first()` returns `(family_id,)` tuple. Verify: `returned_family_id == payload["fid"]` to prevent cross-family child endpoint access after removal.

**Test scenarios:**
- Happy path: child token authenticates, role="child" from payload
- Error path: adult token on child endpoint returns 401
- Error path: deleted child user returns 401

**Verification:**
- Child authentication works with payload-based logic

---

- [x] **Unit 5: Update refresh token paths**

**Goal:** Refresh operations preserve role in new access token

**Requirements:** R3

**Dependencies:** Unit 2

**Files:**
- Modify: `backend/app/services/auth.py` (refresh, child_refresh)

**Approach:**
- When creating new access token during refresh, include role from user or refresh token
- Existing refresh logic already reads user from DB (necessary for token_version check)
- Ensure new access token has role embedded
- **Verify: refresh_token service (line 355-356 in auth.py) passes role from user object to create_access_token payload: `{"sub": user.id, "fid": user.family_id, "role": user.role}`**

**Test scenarios:**
- Happy path: refreshed access token contains role
- Integration: role persists across token refresh cycle

**Verification:**
- Refreshed tokens have same payload structure as initial tokens

## System-Wide Impact

- **Interaction graph:** All authenticated endpoints depend on `get_current_user` / `get_current_child_user` — will receive payload dict instead of full User object
- **API surface parity:** No change — endpoints receive user info (via payload), same family_id and role values
- **Unchanged invariants:** Bearer precedence over Cookie, child blocking on adult endpoints, revocation checks

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Downstream code expects full User object | Payload provides `id`, `family_id`, `role` — most endpoints only need these. If full User needed, endpoint can query (rare) |
| Role change latency (15 min max) | Accepted trade-off per ideation. Family app scenario tolerates brief delay |
| Backward compat: existing tokens lack role | `_verify_token` defaults role to "member". Tokens issued before this refactor still work |

## Security Threat Model

This plan accepts role/family_id propagation latency up to 15 minutes (access token TTL). Explicit threat analysis:

| Threat | Window | Mitigation | Acceptance rationale |
|--------|--------|------------|----------------------|
| **Privilege retention after demotion** (owner→member) | 15 min | Role demotion operations should call `revoke_all_user_tokens()` for immediate invalidation | Owner demotion is rare in family app context; if needed, explicit token revocation is available |
| **Cross-family data access after removal** | 15 min | Minimal existence check verifies `payload["fid"]` matches current DB `User.family_id`. Mismatch → 401 | Family removal is low-frequency; DB family_id verification provides defense-in-depth |
| **Stale role for owner-only endpoints** | 15 min | Owner-only endpoints (`require_owner`) check role from payload. Stale owner token grants access until TTL expires | Acceptable for family app; owner-to-member demotion should trigger token revocation if immediate revocation needed |
| **Backward compat owner downgrade** | Until refresh | Pre-refactor owner tokens default to role="member". Owners temporarily lose owner privileges until natural refresh | Security-safe (downgrade, not escalation); functional impact only; recommend post-deployment refresh for owners |

**Force-logout behavior preserved:** Refresh token validation checks `token_version` mismatch, blocking refresh immediately. Access tokens remain valid for TTL (15 min) — consistent with current design.

## Documentation / Operational Notes

- No new env vars or config
- No migration needed (JWT payload is opaque to DB)
- Deployment: works immediately, existing tokens gracefully handled

## Sources & References

- **Origin document:** docs/ideation/2026-04-17-performance-caching-ideation.md (idea #6)
- Related code: backend/app/auth/deps.py (auth dependency injection)