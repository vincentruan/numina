---
date: 2026-05-14
topic: server-module-docs
focus: After Python monorepo restructure, add READMEs and CLAUDE.md files for server/apps/scheduler_worker and server/packages/*
mode: repo-grounded
---

# Ideation: Server Module Documentation After Phase 2 Restructure

## Grounding Context

**Codebase context:** Numina is a Python 3.12+ FastAPI monorepo restructured into `server/apps/{backend,agent,scheduler_worker}` and `server/packages/{core,db,domain,security,storage}`.

- `backend` and `agent` have solid CLAUDE.md + README files
- `scheduler_worker` has a 1-line README and no CLAUDE.md
- All five packages have 1-line READMEs and no CLAUDE.md
- Key invariants that cause bugs when unknown: `redirect_slashes=False` (use `""` not `"/"` on router decorators), Snowflake ID serialization (IDs as strings in JSON), auth endpoints return 200 not 201, import direction rule (packages never import apps, apps never import sibling apps)
- Quality commands run from `server/` using `uv run`; post-Phase-2 paths are canonical
- `packages/domain` contains 5 subdomains: audit, device, exchange_rate, notification, snapshot — completely undocumented
- `scheduler_worker` runs 7 APScheduler jobs with no guidance on adding/modifying/testing them
- CLAUDE.md supports `@path/to/import` syntax to reference other files without duplicating content
- Empirical finding: CLAUDE.md presence reduces agent runtime ~28.6% and token consumption ~16.6%; human-written focused files outperform LLM-generated ones

## Ranked Ideas

### 1. scheduler_worker Full Documentation Treatment
**Description:** Create a complete CLAUDE.md and expand the README for `server/apps/scheduler_worker`. The CLAUDE.md covers: quality commands (`uv run` from `server/`), the APScheduler job registration pattern, a step-by-step "add a new job" recipe, which domain packages each job is allowed to import, and how to test a job in isolation. The README replaces the 1-line placeholder with a job inventory table (job name, trigger type, domain packages called, what it produces).
**Rationale:** This is the highest-friction gap in the codebase. scheduler_worker has 7 jobs, zero guidance, and is the module most likely to receive new jobs as the product grows. Any agent or developer touching it today must reverse-engineer everything from source.
**Downsides:** Requires reading the actual job source to write accurately — can't be templated. Will need updating when jobs are added or removed.
**Confidence:** 95%
**Complexity:** Low
**Status:** Explored

### 2. packages/* CLAUDE.md Files (Import-Contract Framing)
**Description:** Add a CLAUDE.md to each of the five packages (`core`, `db`, `domain`, `security`, `storage`). Each file leads with a "Don't Do" section (the import direction rule: packages never import apps, apps never import sibling apps), then lists what the package exports and what calling code must never bypass. Framed as a contract manifest, not a narrative guide.
**Rationale:** The import direction rule is the single architectural invariant most likely to be silently violated — it's invisible until you get a circular import at runtime. Putting it in every package CLAUDE.md makes it impossible to miss. The prohibition-led structure matches how agents scan: top-to-bottom, stopping at the first relevant rule.
**Downsides:** Five files to write and maintain. Content for `core`, `db`, `security`, `storage` will be thin (these are small packages) — risk of padding to fill space.
**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

### 3. packages/domain Subdomain Reference
**Description:** Replace the 1-line `packages/domain` README with a structured document: a table mapping each of the 5 subdomains (audit, device, exchange_rate, notification, snapshot) to what business logic it owns, what it exports, and which app(s) consume it. Add a CLAUDE.md covering what belongs in domain vs. what belongs in an app, and the rule against cross-subdomain imports.
**Rationale:** `packages/domain` is the largest shared package and the one most likely to receive new business logic. It's completely undocumented. Without a map, agents probe the filesystem to understand scope, burning tokens and risking cross-subdomain coupling or wrong-layer placement.
**Downsides:** The subdomain boundaries may not be perfectly clean in the current code — documenting them forces a decision about where the lines are, which could surface latent design debt.
**Confidence:** 88%
**Complexity:** Low–Medium
**Status:** Unexplored

### 4. Centralized Invariants via @-import
**Description:** Create a single `server/INVARIANTS.md` containing the four cross-cutting invariants: `redirect_slashes=False`, Snowflake ID serialization, auth return codes (200 not 201), and the import direction rule. Every module CLAUDE.md uses `@path/to/import` to pull it in rather than repeating or omitting it.
**Rationale:** These invariants currently live only in the root CLAUDE.md. A module-level agent that doesn't load the root file misses them. A shared file pulled via @-import makes the invariants ambient — they travel with whatever module context is loaded. One edit keeps all 8 module files current.
**Downsides:** Adds an indirection layer. If @-import isn't supported in all contexts where CLAUDE.md files are read, the invariants silently disappear. Requires discipline to not duplicate the invariants inline "just to be safe."
**Confidence:** 82%
**Complexity:** Low
**Status:** Unexplored

### 5. Inline `# CLAUDE:` Comments + Failure-to-Fix Mapping
**Description:** At each point in the codebase where an invariant looks wrong but is intentional (empty-string route decorators, IDs serialized as strings, `200` on register), add a `# CLAUDE: not a bug — see CLAUDE.md §Invariants` comment. In the corresponding CLAUDE.md, document each invariant as a failure-to-fix mapping: "If you see a 307 redirect on POST → your router decorator has a trailing slash, change `@router.post('/')` to `@router.post('')`."
**Rationale:** The invariants are only useful when reachable from the failure, not from a reading session. An inline comment creates a speed bump before an agent "fixes" the empty string to a slash. The failure-to-fix format in CLAUDE.md makes the rule actionable at the moment it's needed.
**Downsides:** Adds comments to production code, which the project style discourages by default. Requires identifying all the "looks wrong but isn't" sites — incomplete coverage is worse than none.
**Confidence:** 75%
**Complexity:** Medium
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Post-Phase-2 delta section in each CLAUDE.md | Decays fast; once engineers internalize new paths, it's noise |
| 2 | Audience-split README (operators) vs CLAUDE.md (developers) | Good principle but already implicit in the existing template |
| 3 | Automated staleness check via CI | High implementation cost for uncertain value; staleness heuristics are fragile |
| 4 | Import direction rule as a pytest/ruff test | Good idea but out of scope — code change, not documentation |
| 5 | Expiring invariant annotations (`# valid-until:`) | Adds maintenance overhead; keeping docs short is the right fix |
| 6 | Packages self-document via typed `__init__.py` only | Doesn't replace CLAUDE.md for invariants and gotchas |
| 7 | Delete package READMEs entirely | Deletion worse than 1-line; a proper README is the right fix |
| 8 | Write 1000 lines then compress | Process suggestion, not an idea |
| 9 | Diff-driven README from git log | Git log describes the restructure, not the module's purpose |
| 10 | Pre-flight checklist header in each CLAUDE.md | Duplicates what Quality Commands section already does |
| 11 | packages/core and packages/db shared utilities catalog | Covered by the packages/* CLAUDE.md idea |
| 12 | agent CLAUDE.md DeerFlow gotchas section | Minor extension of existing file, not a distinct idea |
| 13 | Root CLAUDE.md post-Phase-2 path update | Maintenance task, not an idea |
| 14 | Cross-reference index in root CLAUDE.md module table | Derivative — falls out naturally when package CLAUDE.md files exist |
| 15 | Quality commands cheat sheet in every app CLAUDE.md | Already present in backend and agent; covered by scheduler_worker idea |
| 16 | Consumer-written package docs | Interesting framing but same output as import-contract idea |
| 17 | Subdomain-granularity CLAUDE.md (one per subdomain) | Merged into packages/domain subdomain reference idea |
| 18 | Prohibition-led package docs | Merged into packages/* CLAUDE.md import-contract framing |
| 19 | Satellite @-import chains | Merged into centralized invariants via @-import idea |
| 20 | "Your First Change" walkthrough | Merged into scheduler_worker full documentation treatment |
