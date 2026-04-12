# Design: Module-level Tooling & CLAUDE.md Initialization

**Date:** 2026-04-11
**Scope:** frontend, backend, agent modules
**Approach:** All-at-once — tooling configs + module CLAUDE.md files in one pass

---

## Problem

The root `CLAUDE.md` explicitly states "no linter/formatter configured — match existing style." No module-level `CLAUDE.md` files exist. Each module has distinct stacks (Vue3+TS, Python FastAPI, Python FastAPI+LangChain) with no enforced quality tooling. Contributors must guess how to run checks and what conventions apply per module.

---

## Goals

1. Add linter/formatter/type checker to each module
2. Create module-level `CLAUDE.md` files with only module-specific content (no duplication of root)
3. Establish a consistent command surface across all three modules

---

## Frontend (`frontend/`)

### Packages (devDependencies)

| Package | Purpose |
|---|---|
| `eslint` | Core linter |
| `@eslint/js` | ESLint JS recommended rules |
| `typescript-eslint` | TS-aware lint rules + parser |
| `eslint-plugin-vue` | Vue 3 specific rules |
| `prettier` | Formatter |
| `eslint-config-prettier` | Disables ESLint rules that conflict with Prettier |

### New files

- `frontend/eslint.config.js` — flat config (ESLint v9+), Vue 3 + TS rules, prettier compat layer
- `frontend/.prettierrc` — single quotes, no semicolons, trailing commas, 100 char print width

### `package.json` scripts added

```json
"lint":      "eslint src",
"lint:fix":  "eslint src --fix",
"format":    "prettier --write src",
"typecheck": "vue-tsc --noEmit"
```

### `frontend/CLAUDE.md` content

- Quality command surface (lint / lint:fix / format / typecheck / test)
- ESLint flat config location and how to extend it
- Note: Vant components are auto-imported — no manual imports, no lint errors for them
- Path alias `@/` → `src/` (configured in both vite.config.ts and tsconfig.app.json)
- `vue-tsc --noEmit` is the canonical type gate (separate from build)
- Reference root CLAUDE.md for architecture, API patterns, and style conventions

---

## Backend (`backend/`)

### `pyproject.toml` additions

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
warn_return_any = true
plugins = ["pydantic.mypy"]
```

### Dev dependencies to add

- `ruff` (lint + format)
- `mypy` (type checker)
- `pydantic[mypy]` or `mypy-extensions` as needed by pydantic.mypy plugin

### `backend/CLAUDE.md` content

- Quality commands:
  - `uv run ruff check .` — lint
  - `uv run ruff format .` — format
  - `uv run mypy .` — type check
  - `uv run pytest tests/ -v` — tests (already documented in root, repeated here for locality)
- Pydantic v2 patterns:
  - Use `model_config = ConfigDict(...)` — not `class Config`
  - Use `model_validate(obj)` — not `.parse_obj(obj)`
  - Use `@field_validator` — not `@validator`
  - Use `from_attributes=True` in ConfigDict for ORM mode
- Alembic: `uv run alembic revision --autogenerate -m "desc"` / `uv run alembic upgrade head`
- `ignore_missing_imports = true` is intentional — ratchet mypy strictness over time
- Reference root CLAUDE.md for architecture, models, router patterns

---

## Agent (`agent/`)

### `pyproject.toml` additions

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
warn_return_any = true
plugins = ["pydantic.mypy"]
```

### Dev dependencies to add

- `ruff`
- `mypy`

### `agent/CLAUDE.md` content

- Quality commands (same surface as backend)
- **Risk control invariants** (non-negotiable):
  - Always redact PII via `pii_redactor` before any tool call or log output
  - Never bypass `policy_guard` — all requests must pass policy check
  - Always emit audit events via `audit_logger` for every agent decision
- **DeerFlow toggle** (`USE_DEERFLOW` env var, default `false`):
  - `false` → routes through `fallback_engine` (direct LLM calls)
  - `true` → routes through `deerflow_adapter`
  - Both paths must produce equivalent `AgentResponse` output
  - Test both paths when changing orchestration logic
- Pydantic v2 patterns (same as backend)
- `# type: ignore` is acceptable for LangChain/DeerFlow where stubs are absent — document the reason inline
- Reference root CLAUDE.md for shared architecture context

---

## Incremental Adoption Policy

- **Formatting:** Do not reformat the entire codebase on first commit. Format only touched files. This avoids massive diffs that obscure blame history.
- **Ruff lint:** First run will surface existing issues. Fix critical ones (F — undefined names, I — import order); suppress non-critical with `# noqa: <code>` sparingly.
- **mypy:** Start lenient (`ignore_missing_imports = true`, no `--strict`). Ratchet by adding `disallow_untyped_defs = true` per-module as coverage improves.

---

## Out of Scope

- CI pipeline changes (separate initiative)
- Pre-commit hooks (can be added later)
- Architecture-enforcing ESLint rules (import boundaries, circular dep detection)
- API contract / OpenAPI snapshot tests
- DeerFlow toggle test matrix
