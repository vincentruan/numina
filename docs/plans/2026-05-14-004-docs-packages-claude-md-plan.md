---
title: "docs: packages/* CLAUDE.md and README treatment"
type: feat
status: active
date: 2026-05-14
origin: docs/brainstorms/2026-05-14-packages-claude-md-requirements.md
---

# docs: packages/* CLAUDE.md and README Treatment

## Overview

Add a `CLAUDE.md` and expand the `README.md` for each of the five `server/packages/` directories (`core`, `db`, `domain`, `security`, `storage`). No Python source files are modified. This is documentation only.

## Problem Frame

All five packages have 1-line READMEs and no CLAUDE.md files. The import direction rule — packages never import from `apps/` — lives only in the root `CLAUDE.md`. An agent loading only a single package's context misses this constraint entirely. Each package also lacks a statement of what it exports and what calling code must not bypass.

## Requirements Trace

- R1. Replace (or create for `domain`) each README with a purpose statement and exports table.
- R2. Exports table documents primary public symbols only — not internal helpers.
- R4. Create a `CLAUDE.md` per package: Quality Commands → Tooling → Key Invariants → Don't Do → Links.
- R5. Quality Commands uses exact `uv run` invocations from `server/`, with `--explicit-package-bases` on mypy.
- R6. Key Invariants documents the import direction rule in every package.
- R7. Don't Do prohibits `apps/` imports, bypassing the public interface, and running commands from the package directory.
- R8. Per-package invariants documented (see per-package notes in origin doc).
- R9. Links section references root `CLAUDE.md` and module README.

## Scope Boundaries

- Documentation only — no Python source changes.
- `packages/domain` README contains purpose + top-level exports table only; full subdomain inventory is deferred to idea #3 (`packages/domain Subdomain Reference`).
- No centralized `server/INVARIANTS.md` — that is idea #4 and a separate decision.

### Deferred to Separate Tasks

- Full `packages/domain` subdomain inventory table: idea #3 in `docs/ideation/2026-05-14-server-module-docs-ideation.md`
- Centralized invariants via `@-import`: idea #4 in the same ideation doc

## Context & Research

### Relevant Code and Patterns

- `server/apps/scheduler_worker/CLAUDE.md` — the template to follow exactly (Quality Commands → Tooling → Key Invariants → Don't Do → Watch Out → Patterns → Links). Packages omit Watch Out and Patterns since they have no job registration or async patterns.
- `server/apps/scheduler_worker/README.md` — README pattern: purpose paragraph + table + (for apps) dev commands. Packages omit dev commands from README (live in CLAUDE.md only).
- `server/apps/backend/CLAUDE.md`, `server/apps/agent/CLAUDE.md` — additional CLAUDE.md reference examples.

### Public Symbols Per Package (sourced from source files)

**`packages/core`:** `Settings` (class), `settings` (singleton instance), `get_logger` (function), `setup_logging` (function), `next_id` (function, from `snowflake.py` — the public Snowflake ID generator)

**`packages/db`:** `SessionLocal` (session factory), `Base` (ORM base class), `get_db` (FastAPI dependency), `engine` (SQLAlchemy engine)

**`packages/domain`:** Five subpackages — `audit`, `device`, `exchange_rate`, `notification`, `snapshot` — each exposing a `service.py`. Top-level exports are the service modules themselves.

**`packages/security`:** `revoke_jti`, `revoke_all_user_tokens`, `cleanup_expired_revoked_tokens` (from `revoke_jti.py` — the only public functions; `_is_jti_revoked` and `_is_token_revoked_for_user` are private); `frontend_auth` subpackage (FastAPI auth dependencies); `service_auth` subpackage (agent JWT auth via `agent_jwt.py`)

**`packages/storage`:** `StorageBackend` (abstract base class), `StorageError` / `StorageRateLimitError` / `StorageConflictError` (exception hierarchy), `get_backend_for_type`, `get_local_backend` (factory functions)

## Key Technical Decisions

- **Dev commands in CLAUDE.md only, not README** — avoids duplicating 10 near-identical blocks. If the `uv run` invocation pattern changes, only 5 files need updating. (see origin: Key Decisions)
- **Import direction rule repeated in every package CLAUDE.md** — makes the rule ambient regardless of which file an agent loads. (see origin: Key Decisions)
- **`--explicit-package-bases` on mypy** — required for namespace collision avoidance in the monorepo, same reason as scheduler_worker. Every Quality Commands section must include this flag: `uv run mypy packages/<name>/ --explicit-package-bases`. (see origin: Key Decisions, R5)
- **`packages/domain` README is a create, not a replace** — it has no README currently. (see origin: Dependencies / Assumptions)

## Output Structure

    server/packages/
    ├── core/
    │   ├── README.md          (replace 1-line)
    │   └── CLAUDE.md          (create)
    ├── db/
    │   ├── README.md          (replace 1-line)
    │   └── CLAUDE.md          (create)
    ├── domain/
    │   ├── README.md          (create — does not exist)
    │   └── CLAUDE.md          (create)
    ├── security/
    │   ├── README.md          (replace 1-line)
    │   └── CLAUDE.md          (create)
    └── storage/
        ├── README.md          (replace 1-line)
        └── CLAUDE.md          (create)

## Implementation Units

All 5 units are independent — implement in any order or in parallel.

- [ ] **Unit 1: packages/core**

**Goal:** Replace 1-line README with purpose + exports table; create CLAUDE.md with settings singleton and logger invariants.

**Requirements:** R1, R2, R4, R5, R6, R7, R8, R9

**Dependencies:** None

**Files:**
- Modify: `server/packages/core/README.md`
- Create: `server/packages/core/CLAUDE.md`

**Approach:**
- README: one-paragraph purpose (config singleton + structured logging), exports table with `Settings`, `settings`, `get_logger`, `setup_logging`, `next_id`.
- CLAUDE.md Key Invariants: (1) import direction rule; (2) `settings` is a singleton — import the instance, never instantiate `Settings()` directly; (3) `get_logger(__name__)` is the only approved logger — never use `logging.getLogger()` directly.
- CLAUDE.md Don't Do: import from `apps/`, instantiate `Settings()`, call `logging.getLogger()`, run commands from `packages/core/`.
- Relative link to root CLAUDE.md: `../../../CLAUDE.md` (resolves from `server/packages/core/`).

**Patterns to follow:** `server/apps/scheduler_worker/CLAUDE.md` — section order and prose style.

**Test scenarios:**
Test expectation: none — documentation only, no behavioral change.

**Verification:**
- CLAUDE.md sections appear in order: Quality Commands → Tooling → Key Invariants → Don't Do → Links.
- `uv run mypy packages/core/ --explicit-package-bases` appears in Quality Commands.
- Relative link `../../../CLAUDE.md` resolves to repo root `CLAUDE.md`.
- Exports table lists `settings` (instance), `Settings` (class), `get_logger`, `setup_logging`, `next_id`.

---

- [ ] **Unit 2: packages/db**

**Goal:** Replace 1-line README with purpose + exports table; create CLAUDE.md with SessionLocal exclusivity and session lifecycle invariants.

**Requirements:** R1, R2, R4, R5, R6, R7, R8, R9

**Dependencies:** None

**Files:**
- Modify: `server/packages/db/README.md`
- Create: `server/packages/db/CLAUDE.md`

**Approach:**
- README: one-paragraph purpose (SQLAlchemy engine, session factory, ORM base, shared models), exports table with `SessionLocal`, `Base`, `get_db`, `engine`, and note that `models/` subpackage contains all ORM model classes.
- CLAUDE.md Key Invariants: (1) import direction rule; (2) `SessionLocal` is the only approved session factory — never create a new `sessionmaker()` elsewhere; (3) `Base` is the only approved ORM base class — all models must inherit from it; (4) always close sessions in a `finally` block or use a context manager.
- CLAUDE.md Don't Do: import from `apps/`, create a new `sessionmaker()`, subclass a different ORM base, leave a session open outside a `finally` block, run commands from `packages/db/`.
- Relative link to root CLAUDE.md: `../../../CLAUDE.md`.

**Patterns to follow:** `server/apps/scheduler_worker/CLAUDE.md`

**Test scenarios:**
Test expectation: none — documentation only, no behavioral change.

**Verification:**
- Exports table lists `SessionLocal`, `Base`, `get_db`, `engine`.
- Session lifecycle invariant (finally block) is in Key Invariants, not just Don't Do.
- `uv run mypy packages/db/ --explicit-package-bases` appears in Quality Commands.

---

- [ ] **Unit 3: packages/domain**

**Goal:** Create README (does not exist) with purpose + top-level exports table; create CLAUDE.md with cross-subdomain isolation and session management invariants.

**Requirements:** R1, R2, R4, R5, R6, R7, R8, R9

**Dependencies:** None

**Files:**
- Create: `server/packages/domain/README.md`
- Create: `server/packages/domain/CLAUDE.md`

**Approach:**
- README: one-paragraph purpose (five business-logic subdomains: audit, device, exchange_rate, notification, snapshot), exports table with exactly 5 rows — one per subpackage — listing the subpackage name and its `service.py` as the entry point. No service-level function inventory (that belongs in idea #3). Note that each subdomain has its own README for details.
- CLAUDE.md Key Invariants: (1) import direction rule; (2) subpackages must not import from each other — cross-subdomain calls go through the app layer; (3) domain services receive a `Session` parameter — they never create their own `SessionLocal()`. Exception: `audit.service.purge_old_audit_logs` is permitted because it is called by the scheduler worker outside a request context.
- CLAUDE.md Don't Do: import from `apps/`, import across subdomains directly, create `SessionLocal()` inside a domain service (except the documented exception), run commands from `packages/domain/`.
- This CLAUDE.md does NOT include a subdomain inventory table — that belongs in idea #3.
- Relative link to root CLAUDE.md: `../../../CLAUDE.md`.

**Patterns to follow:** `server/apps/scheduler_worker/CLAUDE.md`

**Test scenarios:**
Test expectation: none — documentation only, no behavioral change.

**Verification:**
- README is created (file did not exist before).
- Exports table has exactly 5 rows (one per subpackage) with no service-level function inventory.
- `audit.service.purge_old_audit_logs` session exception is documented with its reason in Key Invariants.
- No subdomain inventory table in either file.

---

- [ ] **Unit 4: packages/security**

**Goal:** Replace 1-line README with purpose + exports table; create CLAUDE.md with JTI revocation interface and auth context separation invariants.

**Requirements:** R1, R2, R4, R5, R6, R7, R8, R9

**Dependencies:** None

**Files:**
- Modify: `server/packages/security/README.md`
- Create: `server/packages/security/CLAUDE.md`

**Approach:**
- README: one-paragraph purpose (JWT revocation, frontend auth middleware, service-to-service auth), exports table with `revoke_jti`, `revoke_all_user_tokens`, `cleanup_expired_revoked_tokens` (from `revoke_jti.py`), `frontend_auth` subpackage (FastAPI auth dependencies), `service_auth` subpackage (agent JWT via `agent_jwt.py`).
- CLAUDE.md Key Invariants: (1) import direction rule; (2) `revoke_jti`, `revoke_all_user_tokens`, and `cleanup_expired_revoked_tokens` are the only approved JTI revocation interface — never query `RevokedToken` directly from app code, and never call the private `_is_jti_revoked` or `_is_token_revoked_for_user` functions; (3) `frontend_auth` and `service_auth` are separate auth contexts — do not mix their middleware or dependencies.
- CLAUDE.md Don't Do: import from `apps/`, query `RevokedToken` directly, mix `frontend_auth` and `service_auth` middleware, run commands from `packages/security/`.
- Relative link to root CLAUDE.md: `../../../CLAUDE.md`.

**Patterns to follow:** `server/apps/scheduler_worker/CLAUDE.md`

**Test scenarios:**
Test expectation: none — documentation only, no behavioral change.

**Verification:**
- Exports table covers both `revoke_jti.py` functions and both auth subpackages.
- Auth context separation invariant is in Key Invariants.
- `uv run mypy packages/security/ --explicit-package-bases` appears in Quality Commands.

---

- [ ] **Unit 5: packages/storage**

**Goal:** Replace 1-line README with purpose + exports table; create CLAUDE.md with backend factory and error boundary invariants.

**Requirements:** R1, R2, R4, R5, R6, R7, R8, R9

**Dependencies:** None

**Files:**
- Modify: `server/packages/storage/README.md`
- Create: `server/packages/storage/CLAUDE.md`

**Approach:**
- README: one-paragraph purpose (pluggable storage backends: local, GitHub, WebDAV; factory pattern; crypto utilities), exports table with `StorageBackend` (abstract base), `StorageError` / `StorageRateLimitError` / `StorageConflictError` (exception hierarchy), `get_backend_for_type`, `get_local_backend` (factory functions).
- CLAUDE.md Key Invariants: (1) import direction rule; (2) always obtain a backend via `get_backend_for_type()` or `get_local_backend()` — never instantiate backend classes directly; (3) catch `StorageError` (and subclasses) at the app boundary — never let storage exceptions propagate to API responses unwrapped.
- CLAUDE.md Don't Do: import from `apps/`, instantiate `LocalStorageBackend` or other backends directly, let `StorageError` propagate unwrapped to API responses, run commands from `packages/storage/`.
- Relative link to root CLAUDE.md: `../../../CLAUDE.md`.

**Patterns to follow:** `server/apps/scheduler_worker/CLAUDE.md`

**Test scenarios:**
Test expectation: none — documentation only, no behavioral change.

**Verification:**
- Exports table lists the full exception hierarchy (`StorageError`, `StorageRateLimitError`, `StorageConflictError`).
- Backend factory invariant and error boundary invariant are both in Key Invariants.
- `uv run mypy packages/storage/ --explicit-package-bases` appears in Quality Commands.

## System-Wide Impact

- **Unchanged invariants:** No Python source files are modified. All existing imports, APIs, and runtime behavior are unchanged.
- **Interaction graph:** None — documentation files are not imported or executed.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Exports table becomes stale as packages evolve | Tables document the interface at time of writing; staleness is acceptable — the table is a guide, not a contract enforced by tooling |
| `packages/domain` README scope creep into subdomain details | Scope boundary is explicit: purpose + top-level exports only; subdomain inventory deferred to idea #3 |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-05-14-packages-claude-md-requirements.md](docs/brainstorms/2026-05-14-packages-claude-md-requirements.md)
- Pattern reference: `server/apps/scheduler_worker/CLAUDE.md`
- Ideation source: `docs/ideation/2026-05-14-server-module-docs-ideation.md` (idea #2)
