---
title: "docs: Add failure-to-fix mappings to app CLAUDE.md files"
type: docs
status: active
date: 2026-05-14
origin: docs/brainstorms/2026-05-14-failure-to-fix-mappings-requirements.md
---

# docs: Add failure-to-fix mappings to app CLAUDE.md files

## Overview

Add symptom → cause → fix entries to `server/apps/backend/CLAUDE.md` and `server/apps/agent/CLAUDE.md`. `server/apps/scheduler_worker/CLAUDE.md` already has a "Watch Out" section covering its failure patterns — no changes needed.

## Problem Frame

Invariants documented as rules are only useful during a reading session. An agent that encounters a 307 redirect or JS precision loss on IDs has no path from symptom to fix without reading production source files. The failure-to-fix format closes this gap by adding actionable entries directly in the module CLAUDE.md.

Inline `# CLAUDE:` comments in `.py` files are rejected — they conflict with the project's "no comments unless WHY is non-obvious" style and require touching production code.

(see origin: docs/brainstorms/2026-05-14-failure-to-fix-mappings-requirements.md)

## Requirements Trace

- R1. Failure-to-fix format: Symptom → Cause → Fix
- R2. backend: 307 redirect pattern + JS precision loss / SnowflakeBase pattern
- R3. agent: import direction failure pattern added to Gotchas
- R4. No duplication with existing "Common Pitfalls" content (auth return codes already covered)
- R5. No `.py` files modified

## Scope Boundaries

- Documentation only — no Python source changes
- `scheduler_worker/CLAUDE.md` not touched
- Auth return codes (200 vs 201) already in backend "Common Pitfalls" — do not duplicate

## Context & Research

### Relevant Code and Patterns

- `server/apps/backend/CLAUDE.md` — "Common Pitfalls" subsection under "Snowflake ID Serialization" already covers auth codes, TokenResponse, DELETE archives; new entries go in a new `### Failure Patterns` subsection appended after "Common Pitfalls"
- `server/apps/agent/CLAUDE.md` — "Gotchas" section (bullet list); new entry appended there
- `server/apps/scheduler_worker/CLAUDE.md` — "Watch Out" section as pattern reference for failure-to-fix style

## Key Technical Decisions

- **Placement in backend**: new `### Failure Patterns` subsection appended after the existing `### Common Pitfalls` block under `## Patterns` — keeps all pitfall/failure content co-located
- **Placement in agent**: append to existing `## Gotchas` bullet list — no new section; consistent with existing style
- **No inline comments**: CLAUDE.md-only approach; project style prohibits comments unless WHY is non-obvious

## Implementation Units

Both units are independent and can be executed in any order.

---

- [x] **Unit 1: backend/CLAUDE.md — add Failure Patterns subsection**

**Goal:** Add two failure-to-fix entries for the 307 redirect and JS precision loss patterns.

**Requirements:** R1, R2, R4, R5

**Files:**
- Modify: `server/apps/backend/CLAUDE.md`

**Approach:**
- Append a new `### Failure Patterns` subsection immediately after the existing `### Common Pitfalls` block under `## Patterns`
- Entry 1 — 307 redirect:
  - Symptom: POST or GET returns `307 Temporary Redirect`
  - Cause: Router decorator has trailing slash (`@router.post("/")`) — FastAPI redirects because `redirect_slashes=False` is set in `app/main.py`
  - Fix: Change to `@router.post("")` (empty string)
- Entry 2 — JS precision loss on IDs:
  - Symptom: Frontend receives `NaN` or rounded integer where an ID should appear; `JSON.parse()` loses precision
  - Cause: Response schema inherits from plain `BaseModel` — IDs serialized as JSON integers, exceeding JS safe integer range (2⁵³)
  - Fix: Inherit from `SnowflakeBase` (`apps.backend.app.schemas.base`); IDs serialized as strings automatically

**Patterns to follow:** `server/apps/scheduler_worker/CLAUDE.md` Watch Out section style

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- "Failure Patterns" subsection exists after "Common Pitfalls"
- 307 entry present with symptom/cause/fix
- Precision loss entry present with symptom/cause/fix and `SnowflakeBase` named
- Auth return codes not duplicated

---

- [x] **Unit 2: agent/CLAUDE.md — add import direction failure to Gotchas**

**Goal:** Add one failure-to-fix entry for direct `apps/backend` imports to the existing Gotchas section.

**Requirements:** R1, R3, R5

**Files:**
- Modify: `server/apps/agent/CLAUDE.md`

**Approach:**
- Append one bullet to the existing `## Gotchas` list (after the existing 7 bullets)
- Entry — direct import from `apps/backend`:
  - Symptom: `ImportError` or `ModuleNotFoundError` on `apps.backend.*`; or tests pass locally but fail in CI because backend package not installed in agent virtualenv
  - Cause: Violates import direction rule — agent must not import from `apps/backend` or `apps/scheduler_worker` directly
  - Fix: Use `core/backend_client.py` for all backend data access (wraps httpx calls to backend HTTP API)

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- Gotchas list has a new bullet mentioning `apps/backend` import and `core/backend_client.py`
- No new top-level section added
- Existing 7 Gotchas bullets unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Failure patterns overlap with invariants added by plan 006 | Different format (symptom→fix vs. rule statement) — complementary, not duplicate |
| "Failure Patterns" subsection name conflicts with existing section names | Verified: no existing section with that name in backend CLAUDE.md |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-05-14-failure-to-fix-mappings-requirements.md](docs/brainstorms/2026-05-14-failure-to-fix-mappings-requirements.md)
- Pattern reference: `server/apps/scheduler_worker/CLAUDE.md` (Watch Out section)
- Verified current state: `server/apps/backend/CLAUDE.md`, `server/apps/agent/CLAUDE.md`
