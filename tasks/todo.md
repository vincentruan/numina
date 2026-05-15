# Task List: CLAUDE.md Optimization

## Phase 1: Foundation

### Task 1: Optimize root CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on the root CLAUDE.md file to improve structure, completeness, and cross-reference integrity.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Root CLAUDE.md retains all behavioral guidelines
- [ ] Module documentation table includes all 13 modules
- [ ] Cross-references to child CLAUDE.md files are valid

**Verification:**
- [ ] File exists and is readable
- [ ] No broken markdown links
- [ ] Module table has 13 entries (backend, frontend/main, frontend/child, agent, scheduler_worker, site, frontend/packages, server/packages/core, db, domain, security, storage)

**Dependencies:** None

**Files likely touched:**
- `CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 2: Verify root CLAUDE.md cross-references and module table completeness
**Description:** Manually verify that root CLAUDE.md has complete module table and all cross-references are valid.

**Acceptance criteria:**
- [ ] Module table includes scheduler_worker
- [ ] Module table includes frontend/packages
- [ ] Module table includes all 5 server packages (core, db, domain, security, storage)
- [ ] All `[CLAUDE.md](path)` links resolve to existing files

**Verification:**
- [ ] grep for "scheduler_worker" in root CLAUDE.md succeeds
- [ ] grep for "frontend/packages" in root CLAUDE.md succeeds
- [ ] All 5 server packages appear in module table
- [ ] Bash validation: `find . -name "CLAUDE.md" | wc -l` matches table count

**Dependencies:** Task 1

**Files likely touched:**
- `CLAUDE.md`

**Estimated scope:** Small: 1 file

---

## Phase 2: Server Packages (Parallel Execution)

### Task 3: Optimize server/packages/core/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on core package CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Import direction rule is clear
- [ ] Singleton pattern for `settings` is documented
- [ ] Quality commands are standardized

**Verification:**
- [ ] File exists and is readable
- [ ] "Import direction" section exists
- [ ] Quality commands match server/ standard format

**Dependencies:** Task 1

**Files likely touched:**
- `server/packages/core/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 4: Optimize server/packages/db/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on db package CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Import direction rule is clear
- [ ] SessionLocal singleton rule is documented
- [ ] Session cleanup pattern is documented

**Verification:**
- [ ] File exists and is readable
- [ ] "Import direction" section exists
- [ ] `SessionLocal` is mentioned

**Dependencies:** Task 1

**Files likely touched:**
- `server/packages/db/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 5: Optimize server/packages/domain/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on domain package CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Import direction rule is clear
- [ ] No cross-subdomain imports rule is documented
- [ ] Session parameter pattern is documented

**Verification:**
- [ ] File exists and is readable
- [ ] "Import direction" section exists
- [ ] "No cross-subdomain imports" section exists

**Dependencies:** Task 1

**Files likely touched:**
- `server/packages/domain/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 6: Optimize server/packages/security/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on security package CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Import direction rule is clear
- [ ] JTI revocation interface is documented
- [ ] Auth context separation is documented

**Verification:**
- [ ] File exists and is readable
- [ ] "Import direction" section exists
- [ ] `revoke_jti` is mentioned

**Dependencies:** Task 1

**Files likely touched:**
- `server/packages/security/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 7: Optimize server/packages/storage/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on storage package CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Import direction rule is clear
- [ ] Factory pattern for backends is documented
- [ ] StorageError handling pattern is documented

**Verification:**
- [ ] File exists and is readable
- [ ] "Import direction" section exists
- [ ] `get_backend_for_type` is mentioned

**Dependencies:** Task 1

**Files likely touched:**
- `server/packages/storage/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

## Phase 3: Server Apps (Parallel Execution)

### Task 8: Optimize server/apps/backend/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on backend app CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Snowflake ID serialization section is complete and clear
- [ ] All common pitfalls are documented
- [ ] Failure patterns section is present

**Verification:**
- [ ] File exists and is readable
- [ ] SnowflakeBase pattern is documented
- [ ] "Failure Patterns" section exists

**Dependencies:** Tasks 3-7

**Files likely touched:**
- `server/apps/backend/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 9: Optimize server/apps/agent/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on agent app CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] DeerFlow guardrails section is complete
- [ ] All prohibited abstractions are listed
- [ ] Gotchas section is present

**Verification:**
- [ ] File exists and is readable
- [ ] "DeerFlow Framework Guardrails" section exists
- [ ] "Gotchas" section exists

**Dependencies:** Tasks 3-7

**Files likely touched:**
- `server/apps/agent/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 10: Optimize server/apps/scheduler_worker/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on scheduler_worker app CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Key invariants (max_instances, coalesce, replace_existing) are documented
- [ ] Lazy import pattern is documented
- [ ] "Watch Out" section is present

**Verification:**
- [ ] File exists and is readable
- [ ] `max_instances=1` is mentioned
- [ ] "Watch Out" section exists

**Dependencies:** Tasks 3-7

**Files likely touched:**
- `server/apps/scheduler_worker/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

## Phase 4: Frontend Foundation

### Task 11: Optimize frontend/apps/main/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on frontend main app CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Design system reference is clear
- [ ] Mobile-first priority section is present
- [ ] Emoji convention table is complete

**Verification:**
- [ ] File exists and is readable
- [ ] DESIGN.md is referenced
- [ ] "Mobile-First Priority" section exists

**Dependencies:** Task 1

**Files likely touched:**
- `frontend/apps/main/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

## Phase 5: Frontend Dependent (Parallel Execution)

### Task 12: Optimize frontend/apps/child/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on frontend child app CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Design system (DESIGN.md) reference is present
- [ ] i18n key sections table is complete
- [ ] Cross-reference to main app CLAUDE.md is valid

**Verification:**
- [ ] File exists and is readable
- [ ] DESIGN.md is referenced
- [ ] Main app CLAUDE.md is referenced

**Dependencies:** Task 11

**Files likely touched:**
- `frontend/apps/child/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

### Task 13: Optimize frontend/packages/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on frontend packages CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Inherited conventions are clear
- [ ] Packages table is complete
- [ ] Cross-reference to main app CLAUDE.md is valid

**Verification:**
- [ ] File exists and is readable
- [ ] Main app CLAUDE.md is referenced
- [ ] Packages table lists all shared packages

**Dependencies:** Task 11

**Files likely touched:**
- `frontend/packages/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

## Phase 6: Independent

### Task 14: Optimize site/CLAUDE.md
**Description:** Invoke `claude-md-management:claude-md-improver` skill on site module CLAUDE.md.

**Acceptance criteria:**
- [ ] Skill invocation completes successfully
- [ ] Design principles anti-patterns are clear
- [ ] Content guidelines for overview and project pages are documented
- [ ] What NOT to do section is present

**Verification:**
- [ ] File exists and is readable
- [ ] "Design Principles — Avoiding 'AI Slop' Aesthetic" section exists
- [ ] "What NOT to Do" section exists

**Dependencies:** Task 1

**Files likely touched:**
- `site/CLAUDE.md`

**Estimated scope:** Small: 1 file

---

## Summary

Total tasks: 14
Phases: 6
Parallel execution opportunities: Phase 2 (5 tasks), Phase 3 (3 tasks), Phase 5 (2 tasks)
Estimated total files touched: 13 CLAUDE.md files