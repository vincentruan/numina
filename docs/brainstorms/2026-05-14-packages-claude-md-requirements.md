---
date: 2026-05-14
topic: packages-claude-md
---

# packages/* Documentation Treatment

## Problem Frame

All five `server/packages/` directories (`core`, `db`, `domain`, `security`, `storage`) have 1-line READMEs and no CLAUDE.md files. The import direction rule — packages never import apps, apps never import sibling apps — lives only in the root `CLAUDE.md`. An agent or developer working inside any single package loads no context about this constraint and is likely to violate it silently. Each package also lacks a clear statement of what it exports and what calling code must not bypass.

## Requirements

**For each of the 5 packages (`core`, `db`, `domain`, `security`, `storage`):**

Note: `packages/domain` has no README currently — its README must be created, not replaced. All other packages have 1-line READMEs that are replaced.

### README Requirements

- R1. Replace (or create for `domain`) the README with a structured document containing: a one-paragraph purpose statement and an exports table (symbol name, type, what it does). No dev commands section — those live in CLAUDE.md only (see R5).
- R2. The exports table documents the primary public symbols — functions, classes, constants — that calling code is expected to import. It does not list internal helpers or private symbols. The table documents (not defines) the public interface.

### CLAUDE.md Requirements

- R4. Create a `CLAUDE.md` in each package following the project's standard module template: Quality Commands → Tooling → Key Invariants → Don't Do → Links.
- R5. Quality Commands section lists the exact `uv run` commands for lint, format, typecheck, and test scoped to the package, run from `server/`. The mypy command must include `--explicit-package-bases`.
- R6. Key Invariants section documents the import direction rule: **packages never import from `apps/`**. This is the single most important invariant — it prevents circular imports and keeps the dependency graph acyclic.
- R7. Don't Do section explicitly prohibits: importing from any `apps/` directory, bypassing the package's documented public interface (the exports table in README) to reach internal modules directly, and running quality commands from the package directory instead of `server/`.
- R8. Each package's CLAUDE.md also documents any package-specific invariants (see per-package notes below).
- R9. Links section references the root `CLAUDE.md` and the module README.

### Per-Package Specific Invariants

**`packages/core`:**
- `settings` is a singleton — always import `from packages.core.settings import settings`, never instantiate `Settings()` directly.
- `get_logger(__name__)` is the only approved way to get a logger — never use `logging.getLogger()` directly.

**`packages/db`:**
- `SessionLocal` is the only approved session factory — never create a new `sessionmaker()` elsewhere.
- `Base` is the only approved ORM base class — all models must inherit from it.
- Always close sessions in a `finally` block or use a context manager — never leave a session open.

**`packages/domain`:**
- Domain subpackages (`audit`, `device`, `exchange_rate`, `notification`, `snapshot`) must not import from each other — cross-subdomain calls go through the app layer.
- Domain services receive a `Session` parameter — they never create their own `SessionLocal()`. Exception: `audit.service.purge_old_audit_logs` is permitted to create its own `SessionLocal()` because it is called by the scheduler worker outside of a request context where no session is passed in.

**`packages/security`:**
- `revoke_jti` and `check_jti_revoked` are the only approved JTI revocation interface — never query `RevokedToken` directly from app code.
- `frontend_auth` and `service_auth` are separate auth contexts — do not mix their middleware or dependencies.

**`packages/storage`:**
- Always obtain a backend via `get_backend_for_type()` or `get_local_backend()` — never instantiate backend classes directly.
- Catch `StorageError` (and its subclasses `StorageRateLimitError`, `StorageConflictError`) at the app boundary — never let storage exceptions propagate to API responses unwrapped.

## Success Criteria

- An agent working inside any single package loads its CLAUDE.md and immediately knows: the import direction constraint, the package's documented public interface (from the README exports table), and what it must not do.
- A developer adding a new function to any package can determine the correct pattern by reading the package CLAUDE.md without reading source files.
- The README exports table is accurate against the actual public symbols in each package.

## Scope Boundaries

- Does not modify any Python source files — documentation only.
- Does not create a centralized `server/INVARIANTS.md` — that is idea #4 in the ideation doc and is a separate decision.
- Does not document `packages/domain` subdomains in depth — that is idea #3 (`packages/domain Subdomain Reference`) and is a separate decision. The `packages/domain` README created here contains a purpose statement and a top-level exports table only; the full subdomain inventory table belongs in idea #3.
- The `packages/domain` CLAUDE.md covers the cross-subdomain import rule and session management pattern, but does not include a subdomain inventory table.

## Key Decisions

- **Both CLAUDE.md and expanded README per package** — matches the scheduler_worker treatment. README is for human readers (what does this package do, what does it export via the exports table); CLAUDE.md is for agents and developers modifying code (what must not be violated). Dev commands appear only in CLAUDE.md to avoid duplication across 10 files.
- **Import direction rule in every package CLAUDE.md** — the rule currently lives only in root `CLAUDE.md`. Repeating it in each package makes it ambient: it travels with whatever module context is loaded, regardless of whether the agent loaded the root file.
- **Per-package invariants in addition to the shared rule** — each package has 1-2 non-obvious constraints that cause bugs when unknown (e.g., `settings` singleton, `SessionLocal` exclusivity, storage backend factory). These belong in Key Invariants, not just Patterns.
- **`--explicit-package-bases` on mypy** — required for all packages for the same reason as scheduler_worker: namespace collision avoidance in the monorepo.

## Dependencies / Assumptions

- The public symbols listed in the exports tables are sourced from the actual package source files as of the Phase 2 restructure.
- Quality commands follow the monorepo pattern: `uv run ruff check packages/<name>/`, `uv run ruff format packages/<name>/`, `uv run mypy packages/<name>/ --explicit-package-bases`, `uv run pytest packages/<name>/` — all run from `server/`.
- `packages/domain` has no README currently — R1 applies as a create, not a replace.

## Next Steps

-> `/ce:plan` for structured implementation planning
