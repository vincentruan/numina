---
title: "docs: Expand domain subdomain READMEs"
type: docs
status: active
date: 2026-05-14
origin: docs/brainstorms/2026-05-14-domain-subdomain-readmes-requirements.md
---

# docs: Expand domain subdomain READMEs

## Overview

Replace the 5 one-line subdomain READMEs under `server/packages/domain/` with structured documents covering purpose, public API, consumers, calling conventions, and Phase 2 coupling warnings where applicable.

## Problem Frame

Each subdomain has a 1-line README that names one symbol but documents nothing else. Two subdomains (`snapshot`, `notification`) are Phase 2 stubs that lazy-import from `apps/backend` and raise `RuntimeError` if `apps/backend` is absent from the Python path — a constraint invisible from the current READMEs. The top-level `packages/domain/README.md` and `CLAUDE.md` are already solid; the gap is at the subdomain level.

(see origin: docs/brainstorms/2026-05-14-domain-subdomain-readmes-requirements.md)

## Requirements Trace

- R1. Purpose statement — one sentence per subdomain
- R2. Public API table — Name, Signature summary, What it does
- R3. Consumers — which app(s) call into the subdomain
- R4. Calling conventions — non-obvious session/cache behavior documented
- R5. Phase 2 coupling warning — prominent in `notification` and `snapshot`
- R6. Link to parent — each README links back to `../README.md`

## Scope Boundaries

- No per-subdomain CLAUDE.md files — top-level `packages/domain/CLAUDE.md` already covers import direction and cross-subdomain isolation
- No changes to `packages/domain/README.md` or `packages/domain/CLAUDE.md`
- No code changes

## Context & Research

### Relevant Code and Patterns

- `server/packages/domain/audit/service.py` — `write_audit_log` (dual-mode: caller session or own session), `purge_old_audit_logs` (own session, scheduler-only)
- `server/packages/domain/device/service.py` — `cleanup_expired_device_sessions`, `delete_old_revoked_sessions` (both take `Session`, caller manages lifecycle)
- `server/packages/domain/exchange_rate/service.py` — `ExchangeRateService` class with `get_rate`, `fetch_and_store_rates`, `convert`; in-memory cache with 4h TTL; cache cleared on successful fetch
- `server/packages/domain/notification/service.py` — Phase 2 stub; `run_scheduled_checks` lazy-imports from `apps.backend.app.services.notification.dispatcher`
- `server/packages/domain/snapshot/service.py` — Phase 2 stub; `auto_generate_daily_snapshots` lazy-imports from `apps.backend.app.services.snapshot`
- `server/packages/domain/README.md` — existing top-level subdomain map (do not duplicate)
- `server/packages/domain/audit/README.md` — pattern to replace (1-line placeholder)

### Consumer map (verified from source)

| Subdomain | backend | scheduler_worker |
|-----------|---------|-----------------|
| audit | ✓ (write_audit_log, purge_old_audit_logs re-exported) | ✓ (purge_old_audit_logs) |
| device | — | ✓ |
| exchange_rate | ✓ (ExchangeRateService.get_rate, convert) | ✓ (fetch_and_store_rates) |
| notification | — | ✓ |
| snapshot | — | ✓ |

### Patterns to follow

- `server/packages/core/README.md` — purpose statement + exports table format established in previous session
- `server/packages/security/README.md` — same template

## Key Technical Decisions

- **Phase 2 stub warning as a dedicated section, not inline prose** — `notification` and `snapshot` READMEs get a `## ⚠️ Phase 2 Stub (Extraction Deferred to Phase 3)` section so it is visually distinct and not buried in the API table, and the temporary nature is explicit
- **`audit` dual-mode documented in Calling Conventions, not API table** — the signature difference (`db: Session | None = None`) is subtle; prose explanation is clearer than a table cell
- **`exchange_rate` cache behavior in Calling Conventions** — the 4h TTL and cache-clear-on-fetch are non-obvious and affect scheduler job design

## Implementation Units

All 5 units are independent and can be executed in any order.

---

- [x] **Unit 1: audit subdomain README**

**Goal:** Replace 1-line placeholder with structured README covering audit log writes and purge.

**Requirements:** R1, R2, R3, R4, R6

**Dependencies:** None

**Files:**
- Modify: `server/packages/domain/audit/README.md`

**Approach:**
- Purpose: owns security audit log writes and scheduled purge
- Public API table: `write_audit_log` (module-level function), `purge_old_audit_logs` (module-level function)
- Consumers: `backend` (both functions), `scheduler_worker` (purge only)
- Calling conventions: dual-mode write — when `db` is provided, entry is added to caller's session with `flush()` but no commit; when `db=None`, the function opens its own session, commits, and closes it. Callers that pass `db` must commit themselves.
- Link to `../README.md`

**Test expectation:** none — documentation file, no behavioral change

**Verification:** README renders correctly; dual-mode calling convention is unambiguous without reading service.py

---

- [x] **Unit 2: device subdomain README**

**Goal:** Replace 1-line placeholder with structured README covering device session cleanup.

**Requirements:** R1, R2, R3, R4, R6

**Dependencies:** None

**Files:**
- Modify: `server/packages/domain/device/README.md`

**Approach:**
- Purpose: owns device session lifecycle — expiry marking and hard deletion
- Public API table: `cleanup_expired_device_sessions` (marks expired sessions revoked), `delete_old_revoked_sessions` (hard-deletes revoked sessions older than 7 days)
- Consumers: `scheduler_worker` only
- Calling conventions: both functions take a `Session`; each function calls `db.commit()` internally — the caller creates and closes the session but does NOT commit (the service commits on the caller's behalf)
- Link to `../README.md`

**Test expectation:** none — documentation file, no behavioral change

**Verification:** README renders correctly; consumer and session ownership are clear

---

- [x] **Unit 3: exchange_rate subdomain README**

**Goal:** Replace 1-line placeholder with structured README covering exchange rate fetching, storage, and conversion.

**Requirements:** R1, R2, R3, R4, R6

**Dependencies:** None

**Files:**
- Modify: `server/packages/domain/exchange_rate/README.md`

**Approach:**
- Purpose: owns exchange rate fetching from external API, persistence, and CNY-based currency conversion
- Public API table: `ExchangeRateService.get_rate`, `ExchangeRateService.fetch_and_store_rates`, `ExchangeRateService.convert` (all classmethods)
- Consumers: `backend` (get_rate, convert), `scheduler_worker` (fetch_and_store_rates)
- Calling conventions: in-memory class-level cache with 4h TTL; `fetch_and_store_rates` clears the cache on success; `get_rate` falls back to 1:1 if no DB row exists (logs a warning); all methods take a `Session` parameter
- Link to `../README.md`

**Test expectation:** none — documentation file, no behavioral change

**Verification:** README renders correctly; cache behavior and fallback are documented without reading source

---

- [x] **Unit 4: notification subdomain README**

**Goal:** Replace 1-line placeholder with structured README that prominently surfaces the Phase 2 coupling constraint.

**Requirements:** R1, R2, R3, R4, R5, R6

**Dependencies:** None

**Files:**
- Modify: `server/packages/domain/notification/README.md`

**Approach:**
- Purpose: owns scheduled notification dispatch (reminders, alerts)
- Public API table: `run_scheduled_checks(db: Session) -> None`
- Consumers: `scheduler_worker` only
- Phase 2 coupling section (prominent, visually distinct): this function is a stub that lazy-imports `apps.backend.app.services.notification.dispatcher.run_scheduled_checks`; requires `apps/backend` in the Python path; raises `RuntimeError` if the import fails; full extraction to this package is deferred to Phase 3
- Calling conventions: standard `Session` parameter, caller manages lifecycle
- Link to `../README.md`

**Test expectation:** none — documentation file, no behavioral change

**Verification:** Phase 2 warning is visible without scrolling past the API table; RuntimeError consequence is explicit

---

- [x] **Unit 5: snapshot subdomain README**

**Goal:** Replace 1-line placeholder with structured README that prominently surfaces the Phase 2 coupling constraint.

**Requirements:** R1, R2, R3, R4, R5, R6

**Dependencies:** None

**Files:**
- Modify: `server/packages/domain/snapshot/README.md`

**Approach:**
- Purpose: owns daily asset snapshot generation for all families
- Public API table: `auto_generate_daily_snapshots(db: Session) -> None`
- Consumers: `scheduler_worker` only
- Phase 2 coupling section (prominent, visually distinct): this function is a stub that lazy-imports `apps.backend.app.services.snapshot.auto_generate_daily_snapshots`; requires `apps/backend` in the Python path; raises `RuntimeError` if the import fails; full extraction to this package is deferred to Phase 3
- Calling conventions: standard `Session` parameter, caller manages lifecycle
- Link to `../README.md`

**Test expectation:** none — documentation file, no behavioral change

**Verification:** Phase 2 warning is visible without scrolling past the API table; RuntimeError consequence is explicit

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Phase 2 coupling description becomes stale when Phase 3 extracts the logic | Warning section is clearly labeled "Phase 2" — easy to find and remove when extraction happens |
| `device` service calls `db.commit()` internally, which may surprise callers who expect to manage commits themselves | Document this explicitly in calling conventions |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-05-14-domain-subdomain-readmes-requirements.md](docs/brainstorms/2026-05-14-domain-subdomain-readmes-requirements.md)
- Source verified: `server/packages/domain/*/service.py` (all 5 files read)
- Consumer map verified: `server/apps/backend/app/services/audit_log.py`, `server/apps/backend/app/services/exchange_rate.py`, `server/apps/scheduler_worker/jobs/__init__.py`
- Pattern reference: `server/packages/core/README.md`, `server/packages/security/README.md`
