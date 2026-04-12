---
date: 2026-04-11
topic: module-tooling-and-claude-md
focus: Initialize module-level CLAUDE.md files for frontend/backend/agent; add ESLint+Prettier+vue-tsc for frontend; ruff+mypy+pydantic v2 for Python modules
---

# Ideation: Module-level Tooling & CLAUDE.md Initialization

## Codebase Context

- Monorepo: frontend (Vue 3 + TS + Vite + Vant), backend (Python FastAPI + SQLAlchemy), agent (Python FastAPI + LangChain/DeerFlow)
- Root CLAUDE.md is thorough but explicitly states "no linter/formatter configured — match existing style"
- No module-level CLAUDE.md files exist
- Frontend: vue-tsc in build, vitest present, NO ESLint/Prettier installed
- Backend pyproject.toml: pytest present, no ruff/mypy
- Agent pyproject.toml: pytest + pytest-asyncio present, no ruff/mypy
- Pydantic v2 already used in both Python modules; uv for Python deps
- Agent has unique concerns: PII redaction, policy guard, audit logging, DeerFlow toggle (USE_DEERFLOW)

## Ranked Ideas

### 1. Module-level CLAUDE.md delta docs
**Description:** Create `frontend/CLAUDE.md`, `backend/CLAUDE.md`, `agent/CLAUDE.md` — each containing only what's unique to that module: local commands, directory map, tooling invocations, conventions, gotchas. Explicitly reference root CLAUDE.md for shared rules. No duplication.
**Rationale:** Root CLAUDE.md is already thorough. Module docs give contributors the right context at the point of change without re-reading the whole root doc. Each module has distinct stacks and concerns.
**Downsides:** Requires discipline to keep in sync with root; risk of drift if root changes.
**Confidence:** 95%
**Complexity:** Low
**Status:** Explored — 2026-04-11

### 2. Frontend: ESLint (flat config) + typescript-eslint + eslint-plugin-vue + Prettier
**Description:** Install `eslint`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`, `eslint-plugin-vue`, `prettier`, `eslint-config-prettier`. Add `eslint.config.js` (flat config), `.prettierrc`. Add `lint` and `format` npm scripts. Adopt "format only touched files" policy to avoid a massive reformat commit.
**Rationale:** Frontend currently has zero lint/format tooling. vue-tsc catches types but not Vue-specific patterns, unused vars, or style drift. ESLint+Prettier is the standard Vue3+TS stack.
**Downsides:** Initial config tuning needed; flat config is newer and some plugins have partial support.
**Confidence:** 92%
**Complexity:** Low–Medium
**Status:** Explored — 2026-04-11

### 3. Frontend: Dedicated `typecheck` npm script
**Description:** Add `"typecheck": "vue-tsc --noEmit"` to `package.json` scripts (separate from build). Document it in `frontend/CLAUDE.md` as the canonical type gate.
**Rationale:** vue-tsc is already in the build script but coupled to it. A standalone `typecheck` script makes type checking a first-class, fast feedback loop — runnable without triggering a full build.
**Downsides:** Minimal — it's already there, just needs surfacing.
**Confidence:** 98%
**Complexity:** Low (trivial)
**Status:** Explored — 2026-04-11

### 4. Python (backend + agent): Ruff for lint + format
**Description:** Add `[tool.ruff]` sections to both `backend/pyproject.toml` and `agent/pyproject.toml`. Configure a curated rule set (E, F, I for imports, UP for pyupgrade). Enable Ruff formatter. Add `uv run ruff check .` and `uv run ruff format .` as documented commands. Adopt incrementally — format only on touched files initially.
**Rationale:** One fast tool replaces isort + flake8 + black. Both Python modules have no lint/format tooling today. Ruff is the modern standard for Python projects using uv.
**Downsides:** Initial run will flag existing issues; need to decide whether to fix-all or use `# noqa` sparingly.
**Confidence:** 93%
**Complexity:** Low
**Status:** Explored — 2026-04-11

### 5. Python (backend + agent): mypy with pragmatic baseline
**Description:** Add `[tool.mypy]` to both `pyproject.toml` files. Start with `ignore_missing_imports = true`, `warn_return_any = true`, Pydantic v2 plugin (`pydantic.mypy`). Document the "lenient then ratchet" approach in module CLAUDE.md files.
**Rationale:** Both modules use Pydantic v2 and FastAPI — domains where type errors are expensive. Starting lenient avoids a blocked rollout while still catching the most impactful issues.
**Downsides:** LangChain/DeerFlow stubs are incomplete; agent module will need more `# type: ignore` initially.
**Confidence:** 82%
**Complexity:** Medium
**Status:** Explored — 2026-04-11

### 6. Pydantic v2 patterns section in Python CLAUDE.md files
**Description:** Add a short "Pydantic v2 patterns" section to `backend/CLAUDE.md` and `agent/CLAUDE.md` covering: `model_config = ConfigDict(...)` over `class Config`, `model_validate()` over `.parse_obj()`, `field_validator` syntax, `from_attributes=True` for ORM mode.
**Rationale:** Pydantic v2 has breaking changes from v1. Both modules already use v2 but without documented conventions — inconsistencies accumulate silently.
**Downsides:** Needs to stay current as Pydantic evolves.
**Confidence:** 90%
**Complexity:** Low (docs only)
**Status:** Explored — 2026-04-11

### 7. Agent CLAUDE.md: risk controls + DeerFlow governance section
**Description:** In `agent/CLAUDE.md`, document: PII redaction invariants (always redact before tool calls/logs), policy guard requirements (never bypass), audit logging expectations, and DeerFlow toggle behavior (`USE_DEERFLOW` env var, what changes between modes).
**Rationale:** The agent module has unique safety concerns not covered by root CLAUDE.md. Making these explicit prevents accidental regressions in the most sensitive module.
**Downsides:** Requires someone with domain knowledge to write accurately; risk of becoming stale.
**Confidence:** 88%
**Complexity:** Low (docs only)
**Status:** Explored — 2026-04-11

### 8. Standardized uv-based dev commands in Python CLAUDE.md files
**Description:** In `backend/CLAUDE.md` and `agent/CLAUDE.md`, document the canonical command surface: `uv run ruff check .`, `uv run ruff format .`, `uv run mypy .`, `uv run pytest tests/ -v`. Mirror the frontend's `npm run lint/format/typecheck/test` pattern.
**Rationale:** Contributors shouldn't have to guess how to run quality checks. Consistent command surfaces reduce "works on my machine" loops and make CI steps map 1:1 to local commands.
**Downsides:** Needs updating when tooling changes.
**Confidence:** 95%
**Complexity:** Low (docs only)
**Status:** Explored — 2026-04-11

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| D | ESLint architecture-enforcing rules | High-friction, repo-structure-dependent, false positive tuning cost exceeds value now |
| K | CI pipeline per-module matrix | Separate project, high effort, not required to add tooling |
| L | DeerFlow toggle test matrix | Only valuable with strong deterministic tests already in place |
| M | API contract/OpenAPI snapshot tests | Big methodology decision, infra-heavy, out of scope |
| N | Golden path onboarding + troubleshooting matrix | Vague, duplicative, turns CLAUDE.md into a wiki |
| O | Top-level aggregator script | Becomes bespoke build system; use existing workspace tooling instead |

## Session Log
- 2026-04-11: Initial ideation — ~30 raw candidates generated across 4 frames, 8 survivors. All 8 selected for brainstorm/execution.
