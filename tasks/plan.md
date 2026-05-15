# Implementation Plan: CLAUDE.md Optimization Across Project

## Overview
Invoke the `claude-md-management:claude-md-improver` skill on all 13 CLAUDE.md files in the Numina project to improve development principle guidance, following the dependency graph to ensure consistency across the hierarchy.

## Architecture Decisions
- **Dependency-first order**: Process CLAUDE.md files from root → packages → apps to maintain cross-reference integrity
- **Parallel execution**: Independent packages/apps can be optimized simultaneously after their dependencies are complete
- **Skill invocation**: Use the `claude-md-management:claude-md-improver` skill on each file, which will analyze structure, completeness, and consistency

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
| server/packages/core/CLAUDE.md | 42 | 6 | Minimal | Focused but could add more context |
| server/packages/db/CLAUDE.md | 44 | 6 | Minimal | Focused but could add more context |
| server/packages/domain/CLAUDE.md | 41 | 6 | Minimal | Focused but could add more context |
| server/packages/security/CLAUDE.md | 42 | 6 | Minimal | Focused but could add more context |
| server/packages/storage/CLAUDE.md | 41 | 6 | Minimal | Focused but could add more context |
| frontend/apps/main/CLAUDE.md | 122 | 9 | Excellent | Design system, mobile-first, i18n rules |
| frontend/apps/child/CLAUDE.md | 132 | 10 | Excellent | Design system, i18n sections clear |
| frontend/packages/CLAUDE.md | 40 | 5 | Minimal | Inherited conventions, could expand |
| site/CLAUDE.md | 166 | 11 | Excellent | Design principles, anti-patterns detailed |

## Task List

### Phase 1: Foundation
- [ ] Task 1: Optimize root CLAUDE.md
- [ ] Task 2: Verify root CLAUDE.md cross-references and module table completeness

### Checkpoint: Foundation
- [ ] Root CLAUDE.md has complete module table
- [ ] All cross-references are valid

### Phase 2: Server Packages (Parallel Execution)
- [ ] Task 3: Optimize server/packages/core/CLAUDE.md
- [ ] Task 4: Optimize server/packages/db/CLAUDE.md
- [ ] Task 5: Optimize server/packages/domain/CLAUDE.md
- [ ] Task 6: Optimize server/packages/security/CLAUDE.md
- [ ] Task 7: Optimize server/packages/storage/CLAUDE.md

### Checkpoint: Server Packages
- [ ] All server packages have consistent structure
- [ ] Import direction rules are clear
- [ ] Quality commands are standardized

### Phase 3: Server Apps (Parallel Execution)
- [ ] Task 8: Optimize server/apps/backend/CLAUDE.md
- [ ] Task 9: Optimize server/apps/agent/CLAUDE.md
- [ ] Task 10: Optimize server/apps/scheduler_worker/CLAUDE.md

### Checkpoint: Server Apps
- [ ] Backend has complete Snowflake ID serialization section
- [ ] Agent has complete DeerFlow guardrails
- [ ] Scheduler worker patterns are clear

### Phase 4: Frontend Foundation
- [ ] Task 11: Optimize frontend/apps/main/CLAUDE.md

### Checkpoint: Frontend Foundation
- [ ] Main app has complete design system reference
- [ ] i18n rules and emoji conventions are clear

### Phase 5: Frontend Dependent (Parallel Execution)
- [ ] Task 12: Optimize frontend/apps/child/CLAUDE.md
- [ ] Task 13: Optimize frontend/packages/CLAUDE.md

### Checkpoint: Frontend Dependent
- [ ] Child app design system matches main app conventions
- [ ] Packages has clear inherited conventions

### Phase 6: Independent
- [ ] Task 14: Optimize site/CLAUDE.md

### Checkpoint: Complete
- [ ] All 13 CLAUDE.md files optimized
- [ ] Cross-references validated
- [ ] Module tables complete
- [ ] Consistency across hierarchy confirmed

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Skill invocation fails on large file | Medium | Process file in sections if needed |
| Cross-reference breakage | High | Validate references after each phase |
| Inconsistent changes across parallel tasks | Medium | Use single skill invocation per file, avoid manual edits |
| Module table incompleteness persists | Low | Explicit verification step in Task 2 |

## Open Questions
- Should we standardize section ordering across all files? (Current: varies by module type)
- Should minimal package CLAUDE.md files expand to match app-level comprehensiveness? (Current: minimal-focused strategy)
- Should we add "Common Pitfalls" sections to all server packages? (Current: only backend has detailed pitfalls)