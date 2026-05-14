---
title: "docs: Add missing cross-cutting invariants to app CLAUDE.md files"
type: docs
status: active
date: 2026-05-14
origin: docs/brainstorms/2026-05-14-centralized-invariants-requirements.md
---

# docs: Add missing cross-cutting invariants to app CLAUDE.md files

## Overview

Add the two missing cross-cutting invariants to `server/apps/backend/CLAUDE.md` and add all four invariants to `server/apps/agent/CLAUDE.md`. `server/apps/scheduler_worker/CLAUDE.md` already has the import direction rule and has no routes or response schemas — no changes needed there.

## Problem Frame

The root `CLAUDE.md` documents four invariants that cause silent bugs when unknown. An agent loading only a single app's CLAUDE.md currently misses some or all of them. The `@-import` mechanism is unverified, so the chosen approach is inline copy — guaranteed to work, low maintenance burden since these invariants change rarely.

(see origin: docs/brainstorms/2026-05-14-centralized-invariants-requirements.md)

## Gap Analysis

| Invariant | backend | agent | scheduler_worker |
|---|---|---|---|
| `redirect_slashes=False` | missing | missing | N/A (no routes) |
| Snowflake ID serialization | present (detailed) | missing | N/A (no response schemas) |
| Auth return codes | present | missing | N/A (no auth endpoints) |
| Import direction | missing | missing | present |

## Requirements Trace

- R1. `redirect_slashes=False` in backend and agent CLAUDE.md
- R2. Snowflake ID invariant in agent CLAUDE.md (backend already has it)
- R3. Auth return codes in agent CLAUDE.md (backend already has it)
- R4. Import direction in backend and agent CLAUDE.md
- R5. No duplication of invariants already present

## Scope Boundaries

- Documentation only — no Python source changes
- `scheduler_worker/CLAUDE.md` not touched
- No `server/INVARIANTS.md` created — @-import mechanism unverified

## Context & Research

### Relevant Code and Patterns

- `server/apps/backend/CLAUDE.md` — Key Invariants section (alembic, pydantic v2); Snowflake ID Serialization section; Common Pitfalls (auth return codes already present)
- `server/apps/agent/CLAUDE.md` — Key Invariants (Risk Control) section; no cross-cutting invariants present
- `server/apps/scheduler_worker/CLAUDE.md` — Don't Do section has import direction rule (pattern to follow)
- Root `CLAUDE.md` — canonical invariant text for all four

## Key Technical Decisions

- **Inline copy over @-import**: @-import mechanism unverified; inline copy is guaranteed to work and these invariants change rarely
- **agent gets a new "Cross-Cutting Invariants" section**: distinct from "Key Invariants (Risk Control)" which has a specific agent-safety meaning; placed between that section and "DeerFlow Framework Guardrails"
- **backend appends to existing Key Invariants**: consistent with existing section structure; placed before Snowflake ID Serialization heading

## Implementation Units

Both units are independent and can be executed in any order.

---

- [x] **Unit 1: backend/CLAUDE.md — add redirect_slashes and import direction**

**Goal:** Add the two missing invariants to the existing Key Invariants section.

**Requirements:** R1, R4, R5

**Files:**
- Modify: `server/apps/backend/CLAUDE.md`

**Approach:**
- Append two bullets to the existing Key Invariants section (after the alembic and pydantic v2 bullets, before the Snowflake ID Serialization heading)
- `redirect_slashes=False` bullet: state the rule, name `app/main.py` as where it's set, show `@router.get("")` (correct) vs `@router.get("/")` (wrong) — mirrors the root CLAUDE.md code example style
- Import direction bullet: "Apps never import sibling apps. Use `packages/` for shared logic. Never `from apps.agent import ...` or `from apps.scheduler_worker import ...` inside backend code."

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- `redirect_slashes=False` appears in Key Invariants
- Import direction appears in Key Invariants
- Neither duplicates existing content
- Snowflake ID Serialization section unchanged

---

- [x] **Unit 2: agent/CLAUDE.md — add all four cross-cutting invariants**

**Goal:** Add a new "Cross-Cutting Invariants" section with all four invariants framed for the agent context.

**Requirements:** R1, R2, R3, R4

**Files:**
- Modify: `server/apps/agent/CLAUDE.md`

**Approach:**
- Insert a new `## Cross-Cutting Invariants` section immediately after `## Key Invariants (Risk Control)` and before `## DeerFlow Framework Guardrails`
- Keep entries brief — the agent has one router (`routers/cache.py`), no response schemas with IDs, and no auth endpoints; Snowflake and auth codes are low-risk but worth a one-liner
- `redirect_slashes=False`: applies to `routers/cache.py`; same rule as backend
- Snowflake IDs: if IDs ever appear in agent API responses, use `SnowflakeBase`; reference `server/apps/backend/CLAUDE.md` for the full pattern
- Auth return codes: agent uses `X-Agent-Token` not JWT auth endpoints; note the rule for if auth-style endpoints are added
- Import direction: **most critical for agent** — must never import from `apps/backend` or `apps/scheduler_worker`; all backend data access goes through `core/backend_client.py` (HTTP)

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- "Cross-Cutting Invariants" section exists between "Key Invariants (Risk Control)" and "DeerFlow Framework Guardrails"
- All four invariants present
- `core/backend_client.py` named in import direction bullet
- Existing "Key Invariants (Risk Control)" section unchanged

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Invariant text drifts from root CLAUDE.md over time | Acceptable — these change rarely; inline copy is a deliberate trade-off against unverified @-import |
| Agent section framing too brief to be actionable | Import direction names `core/backend_client.py` explicitly — the actionable constraint |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-05-14-centralized-invariants-requirements.md](docs/brainstorms/2026-05-14-centralized-invariants-requirements.md)
- Canonical invariant text: root `CLAUDE.md`
- Pattern reference: `server/apps/scheduler_worker/CLAUDE.md` (Don't Do section)
- Verified current state: `server/apps/backend/CLAUDE.md`, `server/apps/agent/CLAUDE.md`
