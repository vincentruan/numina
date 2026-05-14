---
title: "docs: Consolidate duplicate invariant and pattern documentation"
type: docs
status: active
date: 2026-05-14
---

# docs: Consolidate duplicate invariant and pattern documentation

## Overview

Remove documentation duplication across root and module CLAUDE.md files. The recent documentation work (plans 006-007) added cross-cutting invariants and failure patterns to app-level CLAUDE.md files, but these now overlap with content in the root CLAUDE.md and create maintenance burden.

## Problem Frame

Code review identified 4 duplication/overlap issues:

1. **redirect_slashes rule triplication** — appears in root CLAUDE.md, backend Key Invariants, backend Failure Patterns, and agent Cross-Cutting Invariants
2. **Pydantic v2 pattern duplication** — appears in root CLAUDE.md, backend Key Invariants, and backend Patterns section
3. **Snowflake ID overlap** — root CLAUDE.md mentions the rule, backend has a full dedicated section with Failure Patterns entry; potential reader confusion about which to follow
4. **Section naming inconsistency** — "Key Invariants", "Cross-Cutting Invariants", "Common Pitfalls", "Failure Patterns", "Don't Do", "Watch Out" — different names for similar invariant/pitfall content across modules

These create maintenance risk: an update to one copy may miss the others. They also create reader confusion — an agent scanning multiple CLAUDE.md files sees the same rule in 3+ places and doesn't know which is authoritative.

## Requirements Trace

- R1. Eliminate redirect_slashes triplication — one canonical location, other locations reference it
- R2. Eliminate Pydantic v2 duplication — one canonical location, module docs reference it
- R3. Clarify Snowflake ID authority — root states rule, backend has full pattern section, failure patterns reference backend section
- R4. Standardize section naming — consistent terminology across modules for similar content types

## Scope Boundaries

- Documentation only — no Python source changes
- Root CLAUDE.md remains canonical for cross-cutting rules
- Module CLAUDE.md files keep local guidance but reference root for shared rules
- scheduler_worker/CLAUDE.md not modified (already clean, uses "Watch Out" appropriately)

## Context & Research

### Current Duplication Map

**redirect_slashes=False:**
- Root CLAUDE.md line ~34 (URL Style section)
- backend/CLAUDE.md line 34 (Key Invariants)
- backend/CLAUDE.md line 157 (Failure Patterns)
- agent/CLAUDE.md line 36 (Cross-Cutting Invariants)

**Pydantic v2:**
- Root CLAUDE.md line 33 (Key Invariants)
- backend/CLAUDE.md line 33 (Key Invariants)
- backend/CLAUDE.md line 89 (Patterns section)

**Snowflake IDs:**
- Root CLAUDE.md mentions the rule
- backend/CLAUDE.md lines 46-86 (full "Snowflake ID Serialization" section)
- backend/CLAUDE.md line 162 (Failure Patterns entry)

**Section naming:**
- backend: "Key Invariants", "Snowflake ID Serialization", "Common Pitfalls", "Failure Patterns"
- agent: "Key Invariants (Risk Control)", "Cross-Cutting Invariants", "Gotchas"
- scheduler_worker: "Key Invariants", "Don't Do", "Watch Out"
- packages/domain: "Key Invariants", "Don't Do"

## Key Technical Decisions

- **Canonical hierarchy**: root CLAUDE.md > module CLAUDE.md. Root owns cross-cutting rules; modules own module-specific guidance and reference root for shared rules
- **Reference syntax**: use markdown links: `See root [CLAUDE.md](../../../CLAUDE.md) §[section-name] for [rule description]`
- **Backend keeps full Snowflake section**: backend is the primary user of Snowflake IDs, so the detailed pattern section stays there; root and agent reference it
- **Pydantic v2**: root states the rule; backend Patterns section shows the examples (no duplication, just expansion)
- **Section naming**: keep module-specific names (agent's "Key Invariants (Risk Control)" is distinct from backend's "Key Invariants"), but consolidate invariant/pitfall content within each module so similar content groups together

## Implementation Units

---

- [ ] **Unit 1: Remove redirect_slashes duplication in backend**

**Goal:** Remove redirect_slashes from backend Key Invariants and Failure Patterns; add reference to root CLAUDE.md instead.

**Requirements:** R1

**Files:**
- Modify: `server/apps/backend/CLAUDE.md`

**Approach:**
- Remove the redirect_slashes bullet from Key Invariants (line 34)
- Remove the "307 redirect" entry from Failure Patterns (lines 155-158)
- Add a bullet to Common Pitfalls: "Router decorators use `""` not `"/"` — see root [CLAUDE.md](../../../CLAUDE.md) §URL Style"
- Verification: grep shows only one mention (the Common Pitfalls reference)

**Patterns to follow:** None

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- redirect_slashes appears exactly once in backend/CLAUDE.md (as a reference link)
- No 307 redirect entry in Failure Patterns

---

- [ ] **Unit 2: Remove redirect_slashes duplication in agent**

**Goal:** Remove redirect_slashes from agent Cross-Cutting Invariants; add reference to root CLAUDE.md.

**Requirements:** R1

**Files:**
- Modify: `server/apps/agent/CLAUDE.md`

**Approach:**
- Remove the redirect_slashes bullet (line 36) from Cross-Cutting Invariants
- Replace with: "1. **Router decorator style** — see root [CLAUDE.md](../CLAUDE.md) §URL Style for the `redirect_slashes=False` rule"
- Verification: grep shows only one mention (the Cross-Cutting Invariants reference)

**Patterns to follow:** None

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- redirect_slashes appears exactly once in agent/CLAUDE.md (as a reference link)

---

- [ ] **Unit 3: Remove Pydantic v2 duplication in backend**

**Goal:** Remove Pydantic v2 bullet from backend Key Invariants; keep Patterns section as the canonical example location.

**Requirements:** R2

**Files:**
- Modify: `server/apps/backend/CLAUDE.md`

**Approach:**
- Remove "Pydantic v2 only" bullet from Key Invariants (line 33)
- Add reference: "1. **Pydantic v2** — see root [CLAUDE.md](../../../CLAUDE.md) §Key Invariants for rule; see §Patterns below for examples"
- Verification: Key Invariants has no Pydantic v2 bullet; Patterns section unchanged

**Patterns to follow:** None

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- Pydantic v2 appears in Key Invariants only as a reference link
- Patterns section still has the full example code

---

- [ ] **Unit 4: Clarify Snowflake ID authority in backend**

**Goal:** Keep backend Snowflake ID Serialization section; add reference in root that backend has the full pattern.

**Requirements:** R3

**Files:**
- Modify: `CLAUDE.md` (root)
- Modify: `server/apps/backend/CLAUDE.md`

**Approach:**
- In root CLAUDE.md, find the Snowflake ID mention (Bigint Serialization section)
- Add sentence: "See `server/apps/backend/CLAUDE.md` §Snowflake ID Serialization for the full pattern and `SnowflakeBase` usage."
- In backend, verify Failure Patterns entry references the Snowflake ID Serialization section (it already does: line 163)
- No removal — backend's full section is valuable and stays

**Patterns to follow:** None

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- Root CLAUDE.md has one Snowflake mention plus reference link to backend
- Backend Snowflake section unchanged (lines 46-86)
- Backend Failure Patterns entry unchanged (already references SnowflakeBase)

---

- [ ] **Unit 5: Standardize section naming guidance**

**Goal:** Document the naming convention for future CLAUDE.md files.

**Requirements:** R4

**Files:**
- Create: `docs/solutions/claude-md-section-naming.md`

**Approach:**
- Create a solution doc that captures the naming convention:
  - **Key Invariants** — module-specific invariants (not cross-cutting)
  - **Cross-Cutting Invariants** — when a module needs to know rules from root (use sparingly, prefer reference links)
  - **Common Pitfalls** — usage mistakes (backend-style)
  - **Gotchas** — implementation-specific quirks (agent-style)
  - **Watch Out** — runtime/env-specific warnings (scheduler_worker-style)
  - **Failure Patterns** — symptom→cause→fix format (backend-style)
  - **Don't Do** — import direction and other hard rules (scheduler_worker and packages style)
- Keep existing names in-place — do not rename existing sections
- This doc guides future module CLAUDE.md files

**Patterns to follow:** `docs/solutions/best-practices/redis-fail-fast-strategy.md` for solution doc format

**Test expectation:** none — documentation file, no behavioral change

**Verification:**
- Solution doc exists with clear naming guidance
- No existing sections renamed (backward compatibility)

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Reference links break if root section names change | Use stable section names (§URL Style, §Key Invariants) |
| Agent misses redirect_slashes rule if it skips root CLAUDE.md | Agent Cross-Cutting Invariants still has a one-line reference pointing to root |
| Pydantic v2 examples removed from backend Patterns section | Approach explicitly keeps Patterns section, removes only Key Invariants bullet |

## Documentation / Operational Notes

- After consolidation, root CLAUDE.md owns: redirect_slashes, Pydantic v2 rule, Snowflake ID rule statement
- Backend CLAUDE.md owns: full Snowflake pattern section, Pydantic v2 examples, backend-specific pitfalls
- Agent CLAUDE.md owns: agent-specific invariants (PII, policy, audit, DeerFlow) plus references to root for cross-cutting rules
- Future module CLAUDE.md files should follow the reference pattern rather than copying cross-cutting rules

## Sources & References

- Origin: Code review findings from plans 006-007 implementation
- Current state: `server/apps/backend/CLAUDE.md`, `server/apps/agent/CLAUDE.md`, `CLAUDE.md`