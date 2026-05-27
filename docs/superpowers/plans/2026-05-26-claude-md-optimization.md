# CLAUDE.md Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Invoke the `claude-md-management:claude-md-improver` skill on all 13 CLAUDE.md files to improve development principle guidance, structure, and cross-reference integrity.

**Architecture:** Dependency-first processing order (root → packages → apps) with parallel execution opportunities for independent modules. Use skill invocation rather than manual editing to ensure consistency.

**Tech Stack:** Markdown only — no code changes. Uses `claude-md-management:claude-md-improver` skill.

---

## File Dependency Graph

```
Root CLAUDE.md (foundation — all others reference it)
    │
    ├── server/packages/* (shared packages — referenced by apps)
    │   ├── core/CLAUDE.md
    │   ├── db/CLAUDE.md
    │   ├── domain/CLAUDE.md
    │   ├── security/CLAUDE.md
    │   └── storage/CLAUDE.md
    │       │
    │       └── server/apps/* (apps that use packages)
    │           ├── backend/CLAUDE.md
    │           ├── agent/CLAUDE.md
    │           └── scheduler_worker/CLAUDE.md
    │
    ├── frontend/apps/main/CLAUDE.md (referenced by child and packages)
    │       │
    │       ├── frontend/apps/child/CLAUDE.md
    │       └── frontend/packages/CLAUDE.md
    │
    └── site/CLAUDE.md (independent)
```

## Current State Assessment

| File | Lines | Sections | Quality | Key Gaps |
|------|-------|----------|---------|----------|
| Root CLAUDE.md | 129 | 8 | Good | Missing scheduler_worker, frontend/packages, server packages in module table |
| server/apps/backend/CLAUDE.md | 156 | 12 | Excellent | Comprehensive, well-structured |
| server/apps/agent/CLAUDE.md | 294 | 15 | Excellent | Comprehensive, DeerFlow guardrails detailed |
| server/apps/scheduler_worker/CLAUDE.md | 92 | 7 | Good | Focused, patterns clear |
| server/packages/core/CLAUDE.md | 42 | 6 | Minimal | Could add more context |
| server/packages/db/CLAUDE.md | 44 | 6 | Minimal | Could add more context |
| server/packages/domain/CLAUDE.md | 41 | 6 | Minimal | Could add more context |
| server/packages/security/CLAUDE.md | 42 | 6 | Minimal | Could add more context |
| server/packages/storage/CLAUDE.md | 41 | 6 | Minimal | Could add more context |
| frontend/apps/main/CLAUDE.md | 122 | 9 | Excellent | Design system, mobile-first, i18n rules |
| frontend/apps/child/CLAUDE.md | 132 | 10 | Excellent | Design system, i18n sections clear |
| frontend/packages/CLAUDE.md | 40 | 5 | Minimal | Could expand inherited conventions |
| site/CLAUDE.md | 166 | 11 | Excellent | Design principles, anti-patterns detailed |

---

## Phase 1: Foundation

### Task 1: Optimize root CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill on root CLAUDE.md**

Run skill: `claude-md-management:claude-md-improver` targeting `CLAUDE.md`

- [ ] **Step 2: Verify skill invocation completed successfully**

Run: `cat CLAUDE.md | wc -l`
Expected: File exists and is readable

- [ ] **Step 3: Verify module table completeness**

Run: `grep -E "scheduler_worker|frontend/packages|server/packages" CLAUDE.md`
Expected: All three sections present in module documentation table

- [ ] **Step 4: Verify cross-references**

Run: `find . -name "CLAUDE.md" | wc -l`
Expected: Count matches number of entries in module table (13 files)

---

### Task 2: Verify root CLAUDE.md cross-references and module table completeness

**Files:**
- Verify: `CLAUDE.md`

- [ ] **Step 1: Check scheduler_worker in module table**

Run: `grep "scheduler_worker" CLAUDE.md`
Expected: Match found

- [ ] **Step 2: Check frontend/packages in module table**

Run: `grep "frontend/packages" CLAUDE.md`
Expected: Match found

- [ ] **Step 3: Check all 5 server packages in module table**

Run: `grep -E "packages/(core|db|domain|security|storage)" CLAUDE.md`
Expected: 5 matches

- [ ] **Step 4: Validate all CLAUDE.md links resolve**

Run: `find . -name "CLAUDE.md" -type f`
Expected: 13 files found, all referenced in table

---

## Checkpoint: Foundation

- [ ] Root CLAUDE.md has complete module table (13 entries)
- [ ] All cross-references are valid
- [ ] Behavioral guidelines retained
- [ ] Project overview intact

---

## Phase 2: Server Packages (Parallel Execution)

### Task 3: Optimize server/packages/core/CLAUDE.md

**Files:**
- Modify: `server/packages/core/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/packages/core/CLAUDE.md`

- [ ] **Step 2: Verify import direction section exists**

Run: `grep -i "import" server/packages/core/CLAUDE.md`
Expected: Import direction rule documented

- [ ] **Step 3: Verify singleton pattern documented**

Run: `grep -i "singleton\|settings" server/packages/core/CLAUDE.md`
Expected: Singleton pattern for `settings` mentioned

- [ ] **Step 4: Verify quality commands standardized**

Run: `grep -E "pytest|ruff|mypy" server/packages/core/CLAUDE.md`
Expected: Quality commands present

---

### Task 4: Optimize server/packages/db/CLAUDE.md

**Files:**
- Modify: `server/packages/db/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/packages/db/CLAUDE.md`

- [ ] **Step 2: Verify import direction section exists**

Run: `grep -i "import" server/packages/db/CLAUDE.md`
Expected: Import direction rule documented

- [ ] **Step 3: Verify SessionLocal singleton documented**

Run: `grep "SessionLocal" server/packages/db/CLAUDE.md`
Expected: SessionLocal singleton rule mentioned

- [ ] **Step 4: Verify session cleanup pattern documented**

Run: `grep -i "cleanup\|session" server/packages/db/CLAUDE.md`
Expected: Session cleanup pattern present

---

### Task 5: Optimize server/packages/domain/CLAUDE.md

**Files:**
- Modify: `server/packages/domain/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/packages/domain/CLAUDE.md`

- [ ] **Step 2: Verify import direction section exists**

Run: `grep -i "import" server/packages/domain/CLAUDE.md`
Expected: Import direction rule documented

- [ ] **Step 3: Verify no cross-subdomain imports rule**

Run: `grep -i "cross.*subdomain\|subdomain" server/packages/domain/CLAUDE.md`
Expected: No cross-subdomain imports rule present

- [ ] **Step 4: Verify session parameter pattern documented**

Run: `grep -i "session" server/packages/domain/CLAUDE.md`
Expected: Session parameter pattern present

---

### Task 6: Optimize server/packages/security/CLAUDE.md

**Files:**
- Modify: `server/packages/security/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/packages/security/CLAUDE.md`

- [ ] **Step 2: Verify import direction section exists**

Run: `grep -i "import" server/packages/security/CLAUDE.md`
Expected: Import direction rule documented

- [ ] **Step 3: Verify JTI revocation interface documented**

Run: `grep "revoke_jti" server/packages/security/CLAUDE.md`
Expected: JTI revocation interface mentioned

- [ ] **Step 4: Verify auth context separation documented**

Run: `grep -i "auth.*context\|context" server/packages/security/CLAUDE.md`
Expected: Auth context separation present

---

### Task 7: Optimize server/packages/storage/CLAUDE.md

**Files:**
- Modify: `server/packages/storage/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/packages/storage/CLAUDE.md`

- [ ] **Step 2: Verify import direction section exists**

Run: `grep -i "import" server/packages/storage/CLAUDE.md`
Expected: Import direction rule documented

- [ ] **Step 3: Verify factory pattern documented**

Run: `grep "get_backend_for_type" server/packages/storage/CLAUDE.md`
Expected: Factory pattern for backends mentioned

- [ ] **Step 4: Verify StorageError handling documented**

Run: `grep "StorageError" server/packages/storage/CLAUDE.md`
Expected: StorageError handling pattern present

---

## Checkpoint: Server Packages

- [ ] All 5 server packages have consistent structure
- [ ] Import direction rules are clear in each
- [ ] Quality commands are standardized
- [ ] Module-specific patterns documented

---

## Phase 3: Server Apps (Parallel Execution)

### Task 8: Optimize server/apps/backend/CLAUDE.md

**Files:**
- Modify: `server/apps/backend/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/apps/backend/CLAUDE.md`

- [ ] **Step 2: Verify Snowflake ID serialization section**

Run: `grep -i "snowflake\|SnowflakeBase" server/apps/backend/CLAUDE.md`
Expected: SnowflakeBase pattern documented

- [ ] **Step 3: Verify common pitfalls documented**

Run: `grep -i "pitfall\|failure" server/apps/backend/CLAUDE.md`
Expected: Failure patterns section present

- [ ] **Step 4: Verify file is readable**

Run: `cat server/apps/backend/CLAUDE.md | wc -l`
Expected: File exists with content

---

### Task 9: Optimize server/apps/agent/CLAUDE.md

**Files:**
- Modify: `server/apps/agent/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/apps/agent/CLAUDE.md`

- [ ] **Step 2: Verify DeerFlow guardrails section**

Run: `grep -i "deerflow\|guardrail" server/apps/agent/CLAUDE.md`
Expected: DeerFlow Framework Guardrails section exists

- [ ] **Step 3: Verify prohibited abstractions listed**

Run: `grep -i "prohibited\|abstraction" server/apps/agent/CLAUDE.md`
Expected: All prohibited abstractions listed

- [ ] **Step 4: Verify gotchas section present**

Run: `grep -i "gotcha\|watch" server/apps/agent/CLAUDE.md`
Expected: Gotchas section exists

---

### Task 10: Optimize server/apps/scheduler_worker/CLAUDE.md

**Files:**
- Modify: `server/apps/scheduler_worker/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `server/apps/scheduler_worker/CLAUDE.md`

- [ ] **Step 2: Verify key invariants documented**

Run: `grep "max_instances" server/apps/scheduler_worker/CLAUDE.md`
Expected: `max_instances=1` mentioned

- [ ] **Step 3: Verify lazy import pattern documented**

Run: `grep -i "lazy.*import" server/apps/scheduler_worker/CLAUDE.md`
Expected: Lazy import pattern present

- [ ] **Step 4: Verify watch out section present**

Run: `grep -i "watch.*out\|warning" server/apps/scheduler_worker/CLAUDE.md`
Expected: Watch Out section exists

---

## Checkpoint: Server Apps

- [ ] Backend has complete Snowflake ID serialization section
- [ ] Agent has complete DeerFlow guardrails
- [ ] Scheduler worker patterns are clear
- [ ] All app files follow standardized template

---

## Phase 4: Frontend Foundation

### Task 11: Optimize frontend/apps/main/CLAUDE.md

**Files:**
- Modify: `frontend/apps/main/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `frontend/apps/main/CLAUDE.md`

- [ ] **Step 2: Verify design system reference**

Run: `grep "DESIGN.md" frontend/apps/main/CLAUDE.md`
Expected: DESIGN.md referenced

- [ ] **Step 3: Verify mobile-first section**

Run: `grep -i "mobile.*first\|mobile-first" frontend/apps/main/CLAUDE.md`
Expected: Mobile-First Priority section exists

- [ ] **Step 4: Verify emoji convention table complete**

Run: `grep -E "✅|❌|⚠️|🗑️" frontend/apps/main/CLAUDE.md`
Expected: Emoji convention table present

---

## Checkpoint: Frontend Foundation

- [ ] Main app has complete design system reference
- [ ] i18n rules and emoji conventions are clear
- [ ] Mobile-first priority documented

---

## Phase 5: Frontend Dependent (Parallel Execution)

### Task 12: Optimize frontend/apps/child/CLAUDE.md

**Files:**
- Modify: `frontend/apps/child/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `frontend/apps/child/CLAUDE.md`

- [ ] **Step 2: Verify design system reference**

Run: `grep "DESIGN.md" frontend/apps/child/CLAUDE.md`
Expected: DESIGN.md referenced

- [ ] **Step 3: Verify i18n key sections table**

Run: `grep -i "i18n" frontend/apps/child/CLAUDE.md`
Expected: i18n key sections table present

- [ ] **Step 4: Verify cross-reference to main app**

Run: `grep "main.*CLAUDE\|apps/main" frontend/apps/child/CLAUDE.md`
Expected: Main app CLAUDE.md referenced

---

### Task 13: Optimize frontend/packages/CLAUDE.md

**Files:**
- Modify: `frontend/packages/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `frontend/packages/CLAUDE.md`

- [ ] **Step 2: Verify inherited conventions documented**

Run: `grep -i "inherit\|convention" frontend/packages/CLAUDE.md`
Expected: Inherited conventions clear

- [ ] **Step 3: Verify packages table complete**

Run: `grep -E "shared\|packages" frontend/packages/CLAUDE.md`
Expected: Packages table lists all shared packages

- [ ] **Step 4: Verify cross-reference to main app**

Run: `grep "main.*CLAUDE\|apps/main" frontend/packages/CLAUDE.md`
Expected: Main app CLAUDE.md referenced

---

## Checkpoint: Frontend Dependent

- [ ] Child app design system matches main app conventions
- [ ] Packages has clear inherited conventions
- [ ] Cross-references valid

---

## Phase 6: Independent

### Task 14: Optimize site/CLAUDE.md

**Files:**
- Modify: `site/CLAUDE.md`

- [ ] **Step 1: Invoke claude-md-improver skill**

Run skill: `claude-md-management:claude-md-improver` targeting `site/CLAUDE.md`

- [ ] **Step 2: Verify design principles anti-patterns**

Run: `grep -i "ai.*slop\|anti.*pattern" site/CLAUDE.md`
Expected: Design Principles — Avoiding 'AI Slop' Aesthetic section exists

- [ ] **Step 3: Verify content guidelines**

Run: `grep -i "overview\|project" site/CLAUDE.md`
Expected: Content guidelines for overview and project pages documented

- [ ] **Step 4: Verify what NOT to do section**

Run: `grep -i "not.*do\|don't" site/CLAUDE.md`
Expected: What NOT to Do section exists

---

## Checkpoint: Complete

- [ ] All 13 CLAUDE.md files optimized
- [ ] Cross-references validated
- [ ] Module tables complete
- [ ] Consistency across hierarchy confirmed

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Skill invocation fails on large file | Medium | Process file in sections if needed |
| Cross-reference breakage | High | Validate references after each phase |
| Inconsistent changes across parallel tasks | Medium | Use single skill invocation per file, avoid manual edits |
| Module table incompleteness persists | Low | Explicit verification step in Task 2 |

---

## Open Questions

- Should we standardize section ordering across all files? (Current: varies by module type)
- Should minimal package CLAUDE.md files expand to match app-level comprehensiveness? (Current: minimal-focused strategy)
- Should we add "Common Pitfalls" sections to all server packages? (Current: only backend has detailed pitfalls)

---

## Summary

Total tasks: 14
Phases: 6
Parallel execution opportunities: Phase 2 (5 tasks), Phase 3 (3 tasks), Phase 5 (2 tasks)
Estimated total files touched: 13 CLAUDE.md files