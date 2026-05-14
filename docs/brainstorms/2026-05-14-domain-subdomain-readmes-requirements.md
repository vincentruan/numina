---
title: Domain Subdomain READMEs
date: 2026-05-14
status: active
origin: docs/ideation/2026-05-14-server-module-docs-ideation.md (Idea #3)
---

# Requirements: Domain Subdomain READMEs

## Problem Frame

`server/packages/domain/` has five subdomains, each with a 1-line README that names one function or class but documents nothing else. The top-level `packages/domain/README.md` and `CLAUDE.md` are solid (created 2026-05-14), but subdomain-level calling conventions, consumer context, and Phase 2 coupling constraints are completely absent.

Two subdomains (`snapshot`, `notification`) are Phase 2 stubs that lazy-import from `apps/backend` and raise `RuntimeError` if `apps/backend` is not in the Python path. This constraint is invisible from the current READMEs. Any agent or developer running these in an isolated context will get a cryptic failure.

## Scope

Expand the 5 existing subdomain READMEs in place. No new files. No CLAUDE.md per subdomain.

**In scope:**
- `server/packages/domain/audit/README.md`
- `server/packages/domain/device/README.md`
- `server/packages/domain/exchange_rate/README.md`
- `server/packages/domain/notification/README.md`
- `server/packages/domain/snapshot/README.md`

**Out of scope:**
- Per-subdomain CLAUDE.md files
- Changes to `packages/domain/README.md` or `packages/domain/CLAUDE.md`
- Any code changes

## Requirements

### R1 — Purpose statement
Each README must open with one sentence describing what business concern the subdomain owns.

### R2 — Public API table
Each README must include a table of public functions/classes with columns: Name, Signature summary, What it does.

### R3 — Consumers
Each README must name which app(s) call into the subdomain: `backend`, `scheduler_worker`, or both.

### R4 — Calling conventions
Each README must document any non-obvious calling convention:
- `audit`: dual-mode write — `db` provided (caller's session, no commit) vs. `db=None` (own session, commits internally)
- `exchange_rate`: in-memory cache with 4h TTL; `fetch_and_store_rates` clears the cache on success
- `device`, `notification`, `snapshot`: standard `Session` parameter, caller manages lifecycle

### R5 — Phase 2 coupling warning
`notification/README.md` and `snapshot/README.md` must include a prominent warning that the service is a Phase 2 stub: it lazy-imports from `apps/backend.app.services.*` and requires `apps/backend` to be present in the Python path. Calling it without `apps/backend` raises `RuntimeError`.

### R6 — Link to parent
Each README must link back to `../README.md` (the top-level domain README) so readers can navigate to the subdomain map.

## Success Criteria

- All 5 subdomain READMEs expanded from 1-line placeholders to structured documents
- Phase 2 coupling constraint is visible without reading source code
- Public API is discoverable without opening `service.py`
- No content duplicated between subdomain README and top-level `packages/domain/README.md`

## Key Decisions

- **No per-subdomain CLAUDE.md** — the top-level `packages/domain/CLAUDE.md` already covers the import direction rule and cross-subdomain isolation. Subdomain-level CLAUDE.md files would duplicate those invariants with no additional value.
- **Phase 2 warning in README, not inline comment** — inline comments in service.py already exist (`# PHASE2_COUPLING`). The README surfaces the constraint to readers who never open the source.
- **Consumers listed explicitly** — `notification` and `snapshot` are only called by `scheduler_worker`; `audit` and `exchange_rate` are called by both `backend` and `scheduler_worker`. This matters for understanding deployment coupling.
