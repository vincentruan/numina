---
date: 2026-05-14
topic: scheduler-worker-docs
---

# scheduler_worker Documentation Treatment

## Problem Frame

`server/apps/scheduler_worker` runs 7 APScheduler jobs independently from the backend. It has a 1-line README and no CLAUDE.md. Any developer or agent touching this module must reverse-engineer job registration patterns, cron schedules, domain package dependencies, and test strategies from source. This is the highest-friction documentation gap in the server monorepo after the Phase 2 restructure.

## Requirements

**README — Job Inventory**

- R1. Replace the 1-line README with a structured document that includes: a one-paragraph purpose statement, a job inventory table, and dev commands scoped to this module.
- R2. The job inventory table lists all 7 registered jobs (as defined in `scheduler.py`'s `setup_all_jobs()`) with columns: job name, trigger type, schedule, domain package(s) called, and what it produces/writes. Note: 6 job functions are defined in `jobs/__init__.py`; the 7th (`file_sync_job`) is an async function in the same file — all 7 are registered in `scheduler.py`.
- R3. Dev commands section shows the exact `uv run` invocations for lint, format, typecheck, and test scoped to this module, run from `server/`. The mypy command must include `--explicit-package-bases` to avoid namespace collision errors (e.g., `uv run mypy apps/scheduler_worker/ --explicit-package-bases`).

**CLAUDE.md — Agent and Developer Guide**

- R4. Create `server/apps/scheduler_worker/CLAUDE.md` following the project's standard module template: Quality Commands, Key Invariants, Don't Do, Watch Out, Patterns, Links.
- R5. Quality Commands section lists the exact `uv run` commands for lint, format, typecheck, and test scoped to this module, run from `server/`. The mypy command must include `--explicit-package-bases` to avoid namespace collision errors.
- R6. Key Invariants section documents: `max_instances=1` (prevents concurrent job runs), `coalesce=True` (skips missed runs), `replace_existing=True` (idempotent re-registration), and the lazy-import pattern (domain imports inside job bodies, not at module level). Session management: most jobs create their own `SessionLocal()` and close it in a `finally` block; jobs that delegate to a domain service (e.g., `audit_log_purge_job` calls `purge_old_audit_logs()`) may let the service manage the session — both patterns are valid.
- R7. Don't Do section explicitly prohibits: importing from `apps/backend` or `apps/agent` (import direction rule), adding module-level imports of domain services (breaks lazy-import pattern), and running the scheduler directly from the module directory.
- R8. Patterns section includes a step-by-step "add a new job" recipe covering: (1) define the job function in `jobs/__init__.py` — use lazy imports for domain packages, manage `SessionLocal()` in a `finally` block unless delegating to a domain service that manages its own session; (2) register the function as a job in `scheduler.py`'s `setup_all_jobs()` with the three required flags (`max_instances=1`, `coalesce=True`, `replace_existing=True`); (3) add a row to the README job inventory table. The recipe must make the two-step separation (define function → register job) explicit.
- R9. Watch Out section documents: the `FILE_SYNC_INTERVAL_MINUTES` env var that controls the file sync job interval, and the exchange rate job's cron window (08:00–22:00 only, with 15-min jitter).
- R10. Links section references the root `CLAUDE.md` and the module README.

## Success Criteria

- A developer adding an 8th APScheduler job can complete the task correctly by following the CLAUDE.md recipe without reading any source files.
- An agent working in `server/apps/scheduler_worker/` loads the CLAUDE.md and immediately knows: the quality commands, the import direction constraint, and the job registration pattern.
- The README job inventory table is accurate against the 7 jobs registered in `scheduler.py`'s `setup_all_jobs()`.

## Scope Boundaries

- Does not cover the other packages (`core`, `db`, `domain`, `security`, `storage`) — those are separate ideation survivors.
- Does not add or modify any Python source files — documentation only.
- Does not create a centralized `server/INVARIANTS.md` — that is a separate idea (idea #4 in the ideation doc); this CLAUDE.md may reference root `CLAUDE.md` for cross-cutting invariants instead.
- Does not document the `main.py` FastAPI health endpoint in detail — operational concerns belong in the README, not the CLAUDE.md.

## Key Decisions

- **CLAUDE.md template**: Follow the project's established module template (Quality Commands → Key Invariants → Don't Do → Watch Out → Patterns → Links), consistent with `server/apps/backend/CLAUDE.md` and `server/apps/agent/CLAUDE.md`.
- **Job inventory in README, not CLAUDE.md**: The job table is operational reference (who reads it: operators, developers orienting to the module). The add-a-job recipe is a coding pattern (who reads it: developers and agents modifying code). Keeping them in separate files matches the project's README-for-humans / CLAUDE.md-for-agents split.
- **Lazy-import pattern as a Key Invariant**: The existing jobs all use lazy imports inside job bodies. This is a non-obvious constraint that an agent would violate if not warned — it belongs in Key Invariants, not just Patterns.

## Dependencies / Assumptions

- The 7 jobs in `jobs/__init__.py` are the canonical list as of the Phase 2 restructure (commit d971dc2). The README table must be written from the actual source, not from memory.
- Quality commands follow the monorepo pattern: `uv run ruff check apps/scheduler_worker/`, `uv run ruff format apps/scheduler_worker/`, `uv run mypy apps/scheduler_worker/`, `uv run pytest apps/scheduler_worker/` — all run from `server/`.

## Next Steps

-> `/ce:plan` for structured implementation planning
