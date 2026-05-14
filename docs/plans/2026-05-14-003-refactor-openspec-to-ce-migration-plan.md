---
title: "refactor: Migrate OpenSpec to CE Compound Solution Format"
type: refactor
status: active
date: 2026-05-14
origin: docs/brainstorms/2026-04-02-openspec-to-ce-migration-requirements.md
---

# refactor: Migrate OpenSpec to CE Compound Solution Format

## Overview

The project previously used OpenSpec for spec-driven development. Two security-domain specs were already converted to CE compound solution format as a PoC (`security-audit.md`, `security-protection.md`). This plan completes the migration by:

1. Creating the missing `logging-config.md` CE document from three logging-domain OpenSpec specs — expanding the migration scope beyond the initial security-domain PoC
2. Fixing broken/stale references in existing CE docs and `ARCHITECTURE.md`
3. Removing all OpenSpec tooling artifacts (skills, workflows, spec directory)

The brainstorm origin document scoped the PoC to the security domain only and explicitly stated "do not delete the openspec directory." This plan supersedes both constraints: it extends migration to the logging domain and deletes the openspec directory after migration, with rationale documented in Key Technical Decisions.

## Problem Frame

Three logging-domain OpenSpec specs remain unmigrated. Four `.agent/skills/` directories and four `.agent/workflows/` files reference the `openspec` CLI tool, which is no longer the project's SDD workflow. The `docs/ARCHITECTURE.md` directory tree still lists `openspec/` as a top-level entry (stale since the Phase 2 monorepo consolidation). Two existing CE solution docs have `## Related` links pointing to openspec paths that will become dead links once the directory is removed. `security-audit.md` Guidance §6 contains two factual errors: a 7-day retention value that conflicts with the code default (30 days), and a prescription for `TimedRotatingFileHandler` only that conflicts with the implementation's support for both size and time rotation modes.

(see origin: `docs/brainstorms/2026-04-02-openspec-to-ce-migration-requirements.md`)

## Requirements Trace

### Spec Conversion

- R1. Convert remaining OpenSpec specs to CE knowledge track format
- R2. Merge related specs by domain to reduce document fragmentation
- R3. Preserve semantic completeness of original specs — no information loss
- R4. Source Requirement titles → Guidance subsection headings
- R5. SHALL statements → indicative guidance statements
- R6. WHEN/THEN scenarios → descriptive Examples bullets
- R7. Multiple scenarios merged under the same source Requirement's Examples
- R8. Use CE knowledge track template (`problem_type: best_practice`)
- R9. Output path: `docs/solutions/best-practices/`
- R10. YAML frontmatter: `module`, `problem_type`, `component`, `severity`, `tags`

### Documentation Updates

- R11. All openspec paths in existing CE docs updated or removed
- R12. `ARCHITECTURE.md` directory tree updated to remove stale `openspec/` entry

### Tooling Cleanup (supersedes brainstorm "do not delete" constraint)

- R13. Delete all OpenSpec agent skills and workflows from `.agent/`
- R14. Delete `server/apps/backend/openspec/` source directory after migration

## Scope Boundaries

- Only the logging domain specs are migrated in this plan (`architecture`, `logging-config`, `security-logging`) — this is a deliberate scope expansion beyond the brainstorm's security-domain PoC
- `security-logging/spec.md` log-rotation content merges into `logging-config.md`; its security-event-logging content is already covered by `security-audit.md`
- `ARCHITECTURE.md` edit is scoped to removing the `openspec/` line only — the broader stale tree (pre-monorepo paths) is not corrected here

### Deferred to Separate Tasks

- CE docs for `rate-limiting`, `cache-layer`, `file-upload-security` specs: no CE equivalent exists yet; Related section links are replaced with visible prose notes (see Unit 2 and Unit 3)
- Correcting the full `ARCHITECTURE.md` directory tree to reflect post-Phase-2 monorepo layout: separate documentation task

## Context & Research

### Relevant Code and Patterns

- `docs/solutions/best-practices/security-audit.md` — target frontmatter schema and body structure (Context → Guidance → Why This Matters → When to Apply → Examples → Related)
- `docs/solutions/best-practices/security-protection.md` — same; also the file needing Related section fix
- `server/packages/core/logging.py` — actual implementation; `retention_days` defaults to **30**, `backup_count` defaults to **10**; `archive_old_logs()` compresses files older than `compress_after_days` (default 7 days) and is **not** called automatically by `setup_logging()` — it is a standalone utility
- `server/apps/backend/app/main.py` lines 137–143 — where `setup_logging()` is called with settings values
- `server/apps/backend/app/core/logging_config.py` — re-export shim pointing to `server/packages/core/logging.py`
- `.agent/skills/openspec-*/SKILL.md` — four skill files to delete
- `.agent/workflows/opsx-*.md` — four workflow files to delete (discovered during planning; not in original brainstorm scope)

### Institutional Learnings

- `docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md` — grep-before-delete pattern: run `grep -r "openspec"` across Python, YAML, TOML, JSON, TS/Vue, and Markdown before any deletion
- `docs/solutions/workflow-issues/server-monorepo-consolidation-phase2-2026-05-14.md` — authoritative record of post-Phase-2 directory structure; `ARCHITECTURE.md` updates must be consistent with it

### Retention Discrepancy Resolution

`security-logging/spec.md` states 30-day retention. `security-audit.md` Guidance §6 states 7-day retention and prescribes `TimedRotatingFileHandler` only. The actual code (`server/packages/core/logging.py`): `retention_days` defaults to 30; both `RotatingFileHandler` (size-based, default) and `TimedRotatingFileHandler` (time-based) are supported. The new `logging-config.md` will canonicalize 30 days and document both rotation modes. `security-audit.md` Guidance §6 will be fully corrected: remove the 7-day value, remove the `TimedRotatingFileHandler`-only prescription, and defer to `logging-config.md` for the canonical rotation and retention policy.

## Key Technical Decisions

- **Merge all three logging specs into one CE doc** (`logging-config.md`): `architecture/spec.md` defines the module structure and directory layout; `logging-config/spec.md` defines the full config system; `security-logging/spec.md` adds the "use unified config" and rotation requirements for the security logger. All three are tightly coupled — splitting them would create cross-reference noise.
- **Delete `server/apps/backend/openspec/` entirely** (supersedes brainstorm "do not delete" constraint): The brainstorm's constraint was a PoC-phase caution. Git history preserves the content permanently. Keeping the directory after migration creates a misleading dual-source-of-truth. The `changes/archive/` subtree contains historical design artifacts (proposal.md, design.md, tasks.md) that are not replicated in the live specs — the implementer must review these before deletion to confirm no requirements are missed (see Unit 1 and Unit 6).
- **Delete `.agent/workflows/opsx-*.md` alongside skills**: The four workflow files are thin wrappers that invoke the corresponding skills. Deleting skills without deleting workflows leaves broken invocation paths.
- **Replace broken Related links with visible prose notes** (not HTML comments): For `file-upload-security`, `rate-limiting`, `cache-layer` — no CE doc exists yet. A visible note in the Related section ("CE doc pending for X") is discoverable by human readers; an HTML comment is invisible in rendered markdown and to the `learnings-researcher` agent.
- **Guidance section ordering criterion**: Sections should follow the reader's mental model — understand the system before encountering configuration details. Order: (1) module structure and directory layout, (2) rotation modes, (3) archival, (4) auto-cleanup, (5) config keys, (6) security logger integration. Config keys come after the behaviors they control, not before.

## Open Questions

### Resolved During Planning

- **Retention days — 30 or 7?**: 30 days for all logs. Verified against `server/packages/core/logging.py` line 25. `security-audit.md` §6 will be fully corrected (retention value + handler type prescription).
- **Security logs vs. app logs — different retention?**: No. The code uses a single `LOG_RETENTION_DAYS` setting for all logs. The 7-day value in `security-audit.md` §6 was a spec error, not an intentional distinction.
- **Delete openspec directory?**: Yes. Git history preserves content. The brainstorm "do not delete" constraint is superseded by R14.
- **`.agent/workflows/` also needs cleanup?**: Yes. Four `opsx-*.md` workflow files discovered; they must be deleted alongside the skills.
- **Related section broken links for non-migrated specs?**: Replace with visible prose notes (not HTML comments) so the gap is surfaced to readers.
- **`archive_old_logs()` — auto-called or manual?**: Manual only. Not invoked by `setup_logging()`. Guidance §4 must reflect this.

### Deferred to Implementation

- Whether `security-audit.md` §6 needs additional corrections beyond retention value and handler type: implementer should read the full section after applying the two known fixes

## Implementation Units

- [ ] **Unit 1: Create `logging-config.md` CE document**

**Goal:** Produce a complete CE knowledge track document covering the unified logging config system, merging content from all three remaining OpenSpec specs.

**Requirements:** R1, R2, R3, R4, R5, R6, R7, R8, R9, R10

**Dependencies:** None

**Files:**
- Create: `docs/solutions/best-practices/logging-config.md`

**Approach:**
- Before writing, read all three live specs **and** the archived change specs under `server/apps/backend/openspec/changes/archive/` to confirm no requirements are missed. The archived `2026-04-02-update-specs-with-security-review-fixes` change contains a `security-logging/spec.md` with design history that differs from the live spec.
- Use the full frontmatter schema from `security-audit.md` as the template: `title`, `date`, `category: best-practices`, `module: backend`, `problem_type: best_practice`, `component: logging`, `severity: medium`, `tags: [logging, log-rotation, log-config, log-archival, log-cleanup]`
- Body sections: Context → Guidance → Why This Matters → When to Apply → Examples → Related
- Guidance subsections in reader-oriented order (understand system before config details):
  1. Unified logging config module at `app/core/logging_config.py` (re-export shim; actual impl in `server/packages/core/logging.py`)
  2. Log directory structure (`logs/app.log`, `logs/security.log`, `logs/archive/*.log.gz`)
  3. Log rotation — size-based (`LOG_MAX_BYTES`, default 10 MB, uses `RotatingFileHandler`) and time-based (midnight, uses `TimedRotatingFileHandler`); size is the default mode
  4. Log archival — `archive_old_logs()` compresses rotated files older than `compress_after_days` (default 7 days); this is a **standalone utility, not called automatically by `setup_logging()`** — must be invoked explicitly
  5. Auto-cleanup on startup — `cleanup_old_logs()` deletes files older than `LOG_RETENTION_DAYS` (default **30 days**); called by `setup_logging()`
  6. Config keys in `config.py`: `LOG_LEVEL`, `LOG_DIR`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`, `LOG_ROTATION_MODE`, `LOG_FORMAT`, `LOG_RETENTION_DAYS`
  7. Security logger uses unified config (not standalone) — references `security-audit.md` for security event details
- Convert all WHEN/THEN scenarios to descriptive Examples bullets (R6)
- Related section: link to `security-audit.md` and `security-protection.md`; note that source OpenSpec specs are preserved in git history

**Patterns to follow:**
- `docs/solutions/best-practices/security-audit.md` — full body structure reference
- `docs/solutions/best-practices/security-protection.md` — frontmatter schema reference

**Test scenarios:**
- Test expectation: none — this is a documentation-only unit with no behavioral change

**Verification:**
- File exists at `docs/solutions/best-practices/logging-config.md`
- YAML frontmatter is valid and includes all required fields
- All source Requirements from the three live specs are traceable to a Guidance subsection
- Guidance §4 (archival) states `archive_old_logs()` is a standalone utility, not auto-called
- Retention days stated as 30 throughout (no "7 days" anywhere)
- `grep -r "logging" docs/solutions/best-practices/logging-config.md` returns results (file is discoverable)

---

- [ ] **Unit 2: Fix `security-audit.md` — Related section and Guidance §6 full correction**

**Goal:** Remove the dead openspec link, fully correct Guidance §6 (retention value + handler type prescription), and add a link to the new `logging-config.md`.

**Requirements:** R3, R11

**Dependencies:** Unit 1 (Related section link to `logging-config.md` requires the file to exist). The Guidance §6 correction has no dependency on Unit 1 and can be applied independently if needed.

**Files:**
- Modify: `docs/solutions/best-practices/security-audit.md`

**Approach:**
- In `## Related`:
  - Replace `openspec/specs/security-logging/spec.md` link with `./logging-config.md`
  - Replace `openspec/specs/file-upload-security/spec.md` link with a visible prose note: "CE doc pending for file-upload-security"
- In Guidance §6 (安全日志实施日志轮转) — **full correction, not just retention days**:
  - Remove the "保留最近 7 天" (7-day retention) statement; replace with: 30 days default, configurable via `LOG_RETENTION_DAYS` (see `logging-config.md`)
  - Remove the `TimedRotatingFileHandler`-only prescription; replace with: both size-based (`RotatingFileHandler`) and time-based (`TimedRotatingFileHandler`) rotation are supported; the security logger uses whichever mode is configured via `LOG_ROTATION_MODE`
  - After applying these two fixes, read the full §6 in context and apply any additional corrections needed

**Test scenarios:**
- Test expectation: none — documentation-only change

**Verification:**
- No `openspec/` paths remain in the file
- Guidance §6 no longer states "7 days" or "TimedRotatingFileHandler" as the only option
- Related section links resolve to existing files
- "CE doc pending for file-upload-security" is visible in rendered markdown

---

- [ ] **Unit 3: Fix stale openspec references in `security-protection.md` and `ARCHITECTURE.md`**

**Goal:** Remove dead openspec links from `security-protection.md` Related section and remove the stale `openspec/` entry from `ARCHITECTURE.md`.

**Requirements:** R11, R12

**Dependencies:** None

**Files:**
- Modify: `docs/solutions/best-practices/security-protection.md`
- Modify: `docs/ARCHITECTURE.md`

**Approach:**
- In `security-protection.md` `## Related`:
  - Replace `openspec/specs/rate-limiting/spec.md` link with a visible prose note: "CE doc pending for rate-limiting"
  - Replace `openspec/specs/cache-layer/spec.md` link with a visible prose note: "CE doc pending for cache-layer"
- In `docs/ARCHITECTURE.md`:
  - Remove the line `├── openspec/                # OpenSpec 变更管理` (around line 225)
  - Do not touch any other lines in the tree — the broader stale layout is out of scope for this plan

**Test scenarios:**
- Test expectation: none — documentation-only change

**Verification:**
- `grep -n "openspec" docs/solutions/best-practices/security-protection.md` returns zero results
- `grep -n "openspec" docs/ARCHITECTURE.md` returns zero results
- "CE doc pending" notes are visible in rendered markdown for both deferred domains

---

- [ ] **Unit 4: Delete OpenSpec agent skills and workflows**

**Goal:** Remove all OpenSpec tooling from `.agent/` so no broken skill invocations remain.

**Requirements:** R13

**Dependencies:** None

**Files:**
- Delete: `.agent/skills/openspec-apply-change/` (directory)
- Delete: `.agent/skills/openspec-archive-change/` (directory)
- Delete: `.agent/skills/openspec-explore/` (directory)
- Delete: `.agent/skills/openspec-propose/` (directory)
- Delete: `.agent/workflows/opsx-apply.md`
- Delete: `.agent/workflows/opsx-archive.md`
- Delete: `.agent/workflows/opsx-explore.md`
- Delete: `.agent/workflows/opsx-propose.md`

**Approach:**
- Before deleting, run a full-repo sweep to confirm no other file references these by name:
  `grep -r "openspec\|opsx" . --include="*.md" --include="*.yaml" --include="*.toml" --include="*.json"` (excluding the files being deleted)
- Any hits outside `.agent/skills/openspec*` and `.agent/workflows/opsx*` must be resolved before deletion
- Delete all 8 items

**Test scenarios:**
- Test expectation: none — tooling removal with no behavioral change to application code

**Verification:**
- `find .agent/ -name "*openspec*" -o -name "*opsx*"` returns zero results
- Full-repo grep for `openspec|opsx` returns only the brainstorm doc, this plan, and `security-audit.md`/`security-protection.md` pending notes (all intentionally preserved)

---

- [ ] **Unit 5: Delete `server/apps/backend/openspec/` directory**

**Goal:** Remove the OpenSpec spec directory now that all content has been migrated to CE format or is preserved in git history.

**Requirements:** R14

**Dependencies:** Unit 1 (content migrated before source destroyed), Unit 2 (Related links in `security-audit.md` updated), Unit 3 (Related links in `security-protection.md` updated — so the final grep sweep returns only the expected files)

**Files:**
- Delete: `server/apps/backend/openspec/` (entire directory tree, including `changes/archive/`)

**Approach:**
- Before deleting, review `server/apps/backend/openspec/changes/archive/` to confirm no requirements in the archived change specs were missed in Unit 1. Pay particular attention to `2026-04-02-update-specs-with-security-review-fixes/specs/security-logging/spec.md` (contains design history that differs from the live spec).
- Run the grep-before-delete sweep (per `docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md`):
  - `grep -r "openspec" server/ --include="*.py"`
  - `grep -r "openspec" . --include="*.yaml" --include="*.toml" --include="*.json"`
  - `grep -r "openspec" frontend/ --include="*.ts" --include="*.vue"`
  - `grep -r "openspec" . --include="*.md"` (must return only: brainstorm doc, this plan — no CE solution docs)
- All sweeps must return zero results (or only the two intentionally preserved docs) before proceeding
- Delete the directory

**Test scenarios:**
- Test expectation: none — directory deletion with no application code impact

**Verification:**
- `find server/apps/backend/openspec -type f` returns "No such file or directory"
- `grep -rn "openspec" . --include="*.md" --include="*.py" --include="*.ts" --include="*.vue" --include="*.yaml" --include="*.toml"` returns only:
  - `docs/brainstorms/2026-04-02-openspec-to-ce-migration-requirements.md` (preserved as decision record)
  - `docs/plans/2026-05-14-003-refactor-openspec-to-ce-migration-plan.md` (this file)

## System-Wide Impact

- **Interaction graph:** No application code, middleware, or API routes are affected. All changes are documentation and tooling files.
- **Error propagation:** N/A — no runtime behavior changes.
- **State lifecycle risks:** None. The openspec CLI is not a declared dependency in any `pyproject.toml` or `package.json`; removing the skill/workflow files does not affect builds or tests.
- **API surface parity:** N/A.
- **Integration coverage:** N/A.
- **Unchanged invariants:** All existing CE solution documents in `docs/solutions/` remain valid. The `learnings-researcher` agent's discovery path (`docs/solutions/best-practices/`) is unchanged — the new `logging-config.md` is additive.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `logging-config.md` omits a source Requirement from one of the three live specs | Read all three specs in full before writing; cross-check each source Requirement heading against the new Guidance subsections |
| `changes/archive/` subtree contains requirements not in the live specs | Explicitly review archived change specs before writing Unit 1 and before deleting in Unit 5 |
| Guidance §4 misrepresents `archive_old_logs()` as auto-called | Unit 1 Approach explicitly states it is a standalone utility; verify in Unit 1 verification step |
| Retention discrepancy reintroduced (7 days vs 30 days) | Canonical value is 30 days (verified in code). Both `logging-config.md` and the corrected `security-audit.md` §6 must state 30 days |
| `security-audit.md` §6 handler type error survives | Unit 2 Approach explicitly requires removing the `TimedRotatingFileHandler`-only prescription |
| `.agent/workflows/opsx-*.md` missed in deletion | Explicitly listed in Unit 4; verified by `find .agent/ -name "*opsx*"` post-deletion |
| `ARCHITECTURE.md` edit accidentally removes adjacent lines | Scope is one line only; verify with `git diff` before committing |
| Unit 5 pre-deletion grep misses `.md` files | Sweep now explicitly includes `--include="*.md"` |
| Unit 6 runs before Units 2+3 complete, causing false-clean grep | Unit 5 explicitly depends on Units 1, 2, and 3 |
| Brainstorm doc becomes misleading after deletion | Intentionally preserved as decision history; the "do not delete" constraint it contains is superseded by R14 |

## Documentation / Operational Notes

- The brainstorm doc `docs/brainstorms/2026-04-02-openspec-to-ce-migration-requirements.md` is preserved as-is — it is a decision record, not a living guide.
- After this migration, `docs/solutions/best-practices/` is the canonical location for all project best-practice knowledge. The `learnings-researcher` agent discovers documents there automatically.
- The `openspec` CLI tool was never a declared dependency; no environment setup changes are needed.
- Three CE docs remain pending for non-migrated specs (`rate-limiting`, `cache-layer`, `file-upload-security`). Visible prose notes in the Related sections of `security-protection.md` and `security-audit.md` mark these gaps.

## Sources & References

- **Origin document:** [`docs/brainstorms/2026-04-02-openspec-to-ce-migration-requirements.md`](../brainstorms/2026-04-02-openspec-to-ce-migration-requirements.md)
- Source specs: `server/apps/backend/openspec/specs/architecture/spec.md`, `server/apps/backend/openspec/specs/logging-config/spec.md`, `server/apps/backend/openspec/specs/security-logging/spec.md`
- Archived change specs: `server/apps/backend/openspec/changes/archive/2026-04-02-update-specs-with-security-review-fixes/` (review before Unit 1 and Unit 5)
- CE pattern reference: `docs/solutions/best-practices/security-audit.md`, `docs/solutions/best-practices/security-protection.md`
- Actual logging implementation: `server/packages/core/logging.py`
- Grep-before-delete pattern: `docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md`
