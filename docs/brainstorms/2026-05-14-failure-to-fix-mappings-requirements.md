---
title: Failure-to-Fix Mappings in App CLAUDE.md Files
date: 2026-05-14
status: active
origin: docs/ideation/2026-05-14-server-module-docs-ideation.md (Idea #5)
---

# Requirements: Failure-to-Fix Mappings in App CLAUDE.md Files

## Problem Frame

The four cross-cutting invariants are only useful when reachable from the failure, not from a reading session. An agent that "fixes" `@router.get("")` to `@router.get("/")` because the empty string looks wrong will cause a 307 redirect — but nothing in the module CLAUDE.md connects that symptom to the rule.

The ideation doc proposed two mechanisms:
1. Inline `# CLAUDE: not a bug — see CLAUDE.md §Invariants` comments in production code
2. Failure-to-fix format in CLAUDE.md: "If you see X → your code has Y, fix it by doing Z"

**Critical finding:** The project style in root `CLAUDE.md` explicitly discourages comments: "Default to writing no comments. Only add one when the WHY is non-obvious." Adding `# CLAUDE:` comments to production code conflicts with this policy and requires touching many files for uncertain gain — the inline comment only helps if an agent reads the file before "fixing" it, which is not guaranteed.

The failure-to-fix format in CLAUDE.md is independently valuable and has no downside. It makes invariants actionable at the moment of failure without touching production code.

## Scope

Add a "Common Mistakes" or "Failure Patterns" section to app-level CLAUDE.md files that documents each invariant as a symptom → cause → fix mapping.

**In scope:**
- `server/apps/backend/CLAUDE.md` — add failure-to-fix section for redirect_slashes, Snowflake IDs, auth return codes
- `server/apps/agent/CLAUDE.md` — add failure-to-fix section for the invariants relevant to agent (import direction, auth token)

**Out of scope:**
- Inline `# CLAUDE:` comments in production `.py` files — conflicts with project comment style
- Package-level CLAUDE.md files — already have "Don't Do" sections that serve the same purpose
- `scheduler_worker/CLAUDE.md` — already has a "Watch Out" section and "Don't Do" section covering its failure patterns

## Requirements

### R1 — Failure-to-fix format
Each entry must follow: **Symptom** (what the agent or developer observes) → **Cause** (which invariant was violated) → **Fix** (exact corrective action).

### R2 — backend failure patterns
`backend/CLAUDE.md` must document:
- 307 redirect on POST/GET → trailing slash on router decorator → change `@router.post("/")` to `@router.post("")`
- JS precision loss on IDs → plain `BaseModel` used instead of `SnowflakeBase` → inherit from `SnowflakeBase`
- 201 returned from auth endpoint → wrong status code assumption → auth endpoints return 200 explicitly

### R3 — agent failure patterns
`agent/CLAUDE.md` must document the invariants relevant to the agent service. The agent doesn't define public API routes or response schemas, so redirect_slashes and Snowflake IDs are low-risk. Focus on:
- Import direction: agent must not import from `apps/backend` or `apps/scheduler_worker` directly — use the backend HTTP client (`core/backend_client.py`) instead
- The agent already has a detailed "Gotchas" section — failure patterns should be added there or as a new "Common Mistakes" subsection, not as a duplicate section

### R4 — No duplication with existing sections
Do not repeat content already covered in "Key Invariants", "Common Pitfalls", or "Watch Out" sections. Failure-to-fix entries complement those sections by adding the symptom trigger — they don't replace the rule statement.

### R5 — No inline comments in .py files
Do not add `# CLAUDE:` or similar annotation comments to production Python files. The project style prohibits comments unless the WHY is non-obvious and not expressible through naming.

## Success Criteria

- An agent that encounters a 307 redirect can find the fix in `backend/CLAUDE.md` without reading `main.py`
- An agent that sees JS precision loss on IDs can find the fix without reading `app/schemas/base.py`
- No production `.py` files are modified
- No content is duplicated within a single CLAUDE.md

## Key Decision

The inline `# CLAUDE:` comment mechanism from the ideation doc is **rejected** — it conflicts with project comment style and requires touching production code. The failure-to-fix format in CLAUDE.md is **adopted** as the sole mechanism. This is a narrower scope than the original idea but has no downside and no maintenance cost beyond the documentation files themselves.
