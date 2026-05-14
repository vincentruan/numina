---
title: Centralized Cross-Cutting Invariants
date: 2026-05-14
status: active
origin: docs/ideation/2026-05-14-server-module-docs-ideation.md (Idea #4)
---

# Requirements: Centralized Cross-Cutting Invariants

## Problem Frame

Four invariants cause silent bugs when unknown:

1. `redirect_slashes=False` — router decorators must use `""` not `"/"` on root paths
2. Snowflake ID serialization — IDs must be strings in API responses
3. Auth return codes — `register`, `login`, `join-family` return 200, not 201
4. Import direction rule — packages never import apps, apps never import sibling apps

These currently live only in the root `CLAUDE.md`. A module-level agent that loads only its own CLAUDE.md misses all four. The ideation doc proposed a `server/INVARIANTS.md` pulled into every module via `@-import` syntax.

**Critical finding:** The `@path/to/import` directive is not verified to work in CLAUDE.md files. Claude Code's `@file` syntax works in prompts, not in CLAUDE.md file bodies. If the mechanism doesn't work, invariants silently disappear — worse than the current state.

## Scope

Ensure all four invariants are reachable from every app-level CLAUDE.md without relying on unverified `@-import` mechanics.

**In scope:**
- `server/apps/agent/CLAUDE.md` — currently missing all four invariants
- `server/apps/scheduler_worker/CLAUDE.md` — verify coverage
- `server/apps/backend/CLAUDE.md` — already has Snowflake + auth codes; verify redirect_slashes and import direction

**Out of scope:**
- Package-level CLAUDE.md files — import direction already documented there (done in previous session)
- Any code changes
- Creating `server/INVARIANTS.md` unless @-import is confirmed to work

## Key Decision: Inline Copy vs. @-import

Two approaches:

**A — Inline copy (Recommended):** Add the missing invariants directly to each app CLAUDE.md that lacks them. Guaranteed to work. Slightly more maintenance surface (4 files instead of 1), but the invariants change rarely.

**B — @-import via INVARIANTS.md:** Create `server/INVARIANTS.md` and reference it with `@server/INVARIANTS.md` in each module CLAUDE.md. Elegant single-source-of-truth, but the mechanism is unverified. If it silently fails, agents miss the invariants with no error.

Decision: **Approach A** unless the user confirms @-import works in their Claude Code version.

## Requirements

### R1 — redirect_slashes invariant in all app CLAUDE.md files
Each app CLAUDE.md (`backend`, `agent`, `scheduler_worker`) must document: router root-path decorators use `""` not `"/"`, because `redirect_slashes=False` is set in `main.py`.

### R2 — Snowflake ID invariant in all app CLAUDE.md files
Each app CLAUDE.md must document: all IDs must be serialized as strings in API responses; JS loses precision on integers > 2⁵³.

### R3 — Auth return codes in backend CLAUDE.md
`backend/CLAUDE.md` already has this. Verify it's present; no change needed if so.

### R4 — Import direction in all app CLAUDE.md files
Each app CLAUDE.md must document: apps never import sibling apps; packages never import apps.

### R5 — No duplication of invariants already present
Do not re-add invariants that are already documented in a module's CLAUDE.md. Audit first, add only what's missing.

## Success Criteria

- An agent loading only `server/apps/agent/CLAUDE.md` can see all four invariants
- An agent loading only `server/apps/backend/CLAUDE.md` can see all four invariants
- An agent loading only `server/apps/scheduler_worker/CLAUDE.md` can see all four invariants
- No invariant is duplicated within a single CLAUDE.md file

## Notes

- `backend/CLAUDE.md` already has Snowflake IDs (detailed) and auth return codes. Needs redirect_slashes and import direction added.
- `agent/CLAUDE.md` has none of the four. Needs all four added (brief — agent doesn't define API routes or response schemas, so Snowflake and auth codes are low-risk, but still worth a one-liner for completeness).
- `scheduler_worker/CLAUDE.md` needs verification before writing.
