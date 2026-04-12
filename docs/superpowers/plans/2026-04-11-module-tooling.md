# Module Tooling & CLAUDE.md Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add linter/formatter/type checker to each module and create module-level CLAUDE.md files with only module-specific content.

**Architecture:** Three independent modules (frontend, backend, agent) each get their own tooling config additions and a CLAUDE.md delta doc. No cross-module dependencies. Frontend uses ESLint + Prettier + vue-tsc; Python modules use ruff + mypy. All CLAUDE.md files reference root CLAUDE.md for shared rules.

**Tech Stack:** ESLint v9 (flat config), typescript-eslint, eslint-plugin-vue, Prettier — frontend; ruff, mypy, pydantic.mypy plugin — backend + agent; uv for Python dep management.

---

## File Map

**Created:**
- `frontend/eslint.config.js`
- `frontend/.prettierrc`
- `frontend/CLAUDE.md`
- `backend/CLAUDE.md`
- `agent/CLAUDE.md`

**Modified:**
- `frontend/package.json` — add lint/format/typecheck scripts + devDependencies
- `backend/pyproject.toml` — add [tool.ruff] + [tool.mypy] + ruff/mypy dev deps
- `agent/pyproject.toml` — add [tool.ruff] + [tool.mypy] + ruff/mypy dev deps

---

## Task 1: Frontend — Install ESLint + Prettier packages

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install devDependencies**

Run from `frontend/`:
```bash
npm install --save-dev \
  eslint \
  @eslint/js \
  typescript-eslint \
  eslint-plugin-vue \
  prettier \
  eslint-config-prettier
```

- [ ] **Step 2: Verify packages appear in package.json devDependencies**

Run:
```bash
node -e "const p = require('./package.json'); const keys = Object.keys(p.devDependencies); ['eslint','typescript-eslint','eslint-plugin-vue','prettier','eslint-config-prettier'].forEach(k => { if (!keys.includes(k)) throw new Error('missing: ' + k); }); console.log('all present');"
```
Expected output: `all present`

- [ ] **Step 3: Commit**

```bash
cd frontend
git add package.json package-lock.json
git commit -m "chore(frontend): install eslint, typescript-eslint, eslint-plugin-vue, prettier"
```

---

## Task 2: Frontend — Add ESLint flat config

**Files:**
- Create: `frontend/eslint.config.js`

- [ ] **Step 1: Create `frontend/eslint.config.js`**

```js
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import prettierConfig from 'eslint-config-prettier'

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  prettierConfig,
  {
    files: ['src/**/*.vue', 'src/**/*.ts', 'src/**/*.tsx'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        extraFileExtensions: ['.vue'],
      },
    },
    rules: {
      // Relax rules that conflict with Vue auto-import pattern (Vant)
      'vue/multi-word-component-names': 'off',
      // Allow unused vars prefixed with _ (common in Vue destructuring)
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
)
```

- [ ] **Step 2: Verify ESLint runs without crashing**

Run from `frontend/`:
```bash
npx eslint src --max-warnings=9999
```
Expected: exits 0 (warnings OK, no parse errors or config errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/eslint.config.js
git commit -m "chore(frontend): add eslint flat config (vue3 + typescript-eslint + prettier)"
```

---

## Task 3: Frontend — Add Prettier config + npm scripts

**Files:**
- Create: `frontend/.prettierrc`
- Modify: `frontend/package.json`

- [ ] **Step 1: Create `frontend/.prettierrc`**

```json
{
  "singleQuote": true,
  "semi": false,
  "trailingComma": "all",
  "printWidth": 100,
  "endOfLine": "lf"
}
```

- [ ] **Step 2: Add scripts to `frontend/package.json`**

In the `"scripts"` section, add these four entries (keep existing scripts):
```json
"lint":      "eslint src",
"lint:fix":  "eslint src --fix",
"format":    "prettier --write src",
"typecheck": "vue-tsc --noEmit"
```

- [ ] **Step 3: Verify typecheck script works**

Run from `frontend/`:
```bash
npm run typecheck
```
Expected: exits 0 (no type errors)

- [ ] **Step 4: Verify format script runs**

Run from `frontend/`:
```bash
npm run format -- --check
```
Expected: exits 0 or lists files that would change (no crash)

- [ ] **Step 5: Commit**

```bash
git add frontend/.prettierrc frontend/package.json
git commit -m "chore(frontend): add prettier config and lint/format/typecheck npm scripts"
```

---

## Task 4: Frontend — Write CLAUDE.md

**Files:**
- Create: `frontend/CLAUDE.md`

- [ ] **Step 1: Create `frontend/CLAUDE.md`**

```markdown
# frontend/CLAUDE.md

Module-specific guidance for the Vue 3 + TypeScript frontend.
See root `CLAUDE.md` for architecture, API patterns, component structure, and style conventions.

## Quality Commands

```bash
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run format        # Prettier — format all files in src/
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run build         # vue-tsc -b && vite build — full production build
npm run test:run      # vitest run — run tests once (no watch)
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **Prettier:** config at `.prettierrc`. Single quotes, no semicolons, trailing commas, 100-char width.
- **vue-tsc:** canonical type gate. Run `npm run typecheck` before pushing. Strict mode is on (`tsconfig.app.json`).
- **vitest:** test runner. Tests live in `src/**/*.test.ts` or `src/**/*.spec.ts`.

## Key Conventions

- **Vant components are auto-imported** via `unplugin-vue-components`. Do not manually import them — ESLint is configured to allow this.
- **Path alias `@/`** maps to `src/`. Configured in both `vite.config.ts` and `tsconfig.app.json`.
- **`<script setup lang="ts">`** only — no Options API, no `defineComponent`.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **Incremental formatting:** format only files you touch. Do not run `npm run format` on the entire repo in a single commit.
```

- [ ] **Step 2: Commit**

```bash
git add frontend/CLAUDE.md
git commit -m "docs(frontend): add module-level CLAUDE.md with quality commands and conventions"
```

---

## Task 5: Backend — Add ruff + mypy to pyproject.toml

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add ruff and mypy to dev dependencies**

In `backend/pyproject.toml`, update the `[dependency-groups]` dev section to add `ruff` and `mypy`:

```toml
[dependency-groups]
dev = [
    "playwright>=1.58.0",
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "docker>=7.0.0",
    "ruff>=0.9.0",
    "mypy>=1.13.0",
]
```

- [ ] **Step 2: Add ruff and mypy tool config sections**

Append to the end of `backend/pyproject.toml`:

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

- [ ] **Step 3: Sync dependencies**

Run from `backend/`:
```bash
uv sync
```
Expected: resolves and installs ruff + mypy without errors

- [ ] **Step 4: Verify ruff runs**

Run from `backend/`:
```bash
uv run ruff check .
```
Expected: exits 0 or lists lint warnings (no crash, no config error)

- [ ] **Step 5: Verify mypy runs**

Run from `backend/`:
```bash
uv run mypy app/
```
Expected: exits 0 or reports type errors (no crash, no "module not found for plugin" error)

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore(backend): add ruff and mypy dev dependencies and tool config"
```

---

## Task 6: Backend — Write CLAUDE.md

**Files:**
- Create: `backend/CLAUDE.md`

- [ ] **Step 1: Create `backend/CLAUDE.md`**

```markdown
# backend/CLAUDE.md

Module-specific guidance for the Python FastAPI backend.
See root `CLAUDE.md` for architecture, models, router patterns, test fixtures, and style conventions.

## Quality Commands

```bash
uv run ruff check .          # lint — check for errors and warnings
uv run ruff check . --fix    # lint — auto-fix where possible
uv run ruff format .         # format — reformat source files
uv run mypy app/             # type check
uv run pytest tests/ -v      # run all tests
uv run pytest tests/ -v -k "keyword"   # run tests matching keyword
```

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I (imports), UP (pyupgrade).
- **mypy:** type checker. Config in `pyproject.toml` under `[tool.mypy]`. Starts lenient (`ignore_missing_imports = true`) — ratchet strictness over time by adding `disallow_untyped_defs = true` per module.
- **pytest:** test runner. Tests in `backend/tests/`. Each test gets a fresh in-memory SQLite DB.

## Pydantic v2 Patterns

Always use v2 style — never v1 style:

```python
# ✅ v2 — ConfigDict
from pydantic import BaseModel, ConfigDict

class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ❌ v1 — class Config (do not use)
class MySchema(BaseModel):
    class Config:
        orm_mode = True
```

```python
# ✅ v2 — model_validate
obj = MySchema.model_validate(orm_instance)

# ❌ v1 — parse_obj (do not use)
obj = MySchema.parse_obj(orm_instance)
```

```python
# ✅ v2 — field_validator
from pydantic import field_validator

class MySchema(BaseModel):
    @field_validator("field_name")
    @classmethod
    def validate_field(cls, v: str) -> str:
        return v.strip()

# ❌ v1 — validator (do not use)
```

## Alembic

```bash
uv run alembic revision --autogenerate -m "description"   # create migration
uv run alembic upgrade head                                # apply migrations
```

## Incremental Formatting

Format only files you touch. Do not run `uv run ruff format .` on the entire codebase in a single commit — it creates noise in blame history.
```

- [ ] **Step 2: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(backend): add module-level CLAUDE.md with quality commands and pydantic v2 patterns"
```

---

## Task 7: Agent — Add ruff + mypy to pyproject.toml

**Files:**
- Modify: `agent/pyproject.toml`

- [ ] **Step 1: Add ruff and mypy to dev dependencies**

In `agent/pyproject.toml`, update the `[dependency-groups]` dev section:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.9.0",
    "mypy>=1.13.0",
]
```

- [ ] **Step 2: Add ruff and mypy tool config sections**

Append to the end of `agent/pyproject.toml`:

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

- [ ] **Step 3: Sync dependencies**

Run from `agent/`:
```bash
uv sync
```
Expected: resolves and installs ruff + mypy without errors

- [ ] **Step 4: Verify ruff runs**

Run from `agent/`:
```bash
uv run ruff check .
```
Expected: exits 0 or lists lint warnings (no crash)

- [ ] **Step 5: Verify mypy runs**

Run from `agent/`:
```bash
uv run mypy .
```
Expected: exits 0 or reports type errors (no crash, no plugin error)

- [ ] **Step 6: Commit**

```bash
git add agent/pyproject.toml agent/uv.lock
git commit -m "chore(agent): add ruff and mypy dev dependencies and tool config"
```

---

## Task 8: Agent — Write CLAUDE.md

**Files:**
- Create: `agent/CLAUDE.md`

- [ ] **Step 1: Create `agent/CLAUDE.md`**

```markdown
# agent/CLAUDE.md

Module-specific guidance for the Python FastAPI AI agent microservice.
See root `CLAUDE.md` for shared architecture context.

## Quality Commands

```bash
uv run ruff check .          # lint
uv run ruff check . --fix    # lint + auto-fix
uv run ruff format .         # format
uv run mypy .                # type check
uv run pytest tests/ -v      # run all tests
```

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I, UP.
- **mypy:** type checker. `ignore_missing_imports = true` is intentional — LangChain and DeerFlow stubs are incomplete. Use `# type: ignore[<code>]` with an inline comment explaining why when suppressing.
- **pytest + pytest-asyncio:** async test runner. `asyncio_mode = "auto"` is set in `pyproject.toml`.

## Risk Control Invariants (Non-Negotiable)

These must hold in every code path — never bypass them:

1. **PII redaction:** Always call `pii_redactor` before passing user data to any tool call or writing to logs.
2. **Policy guard:** All agent requests must pass through `policy_guard`. Never skip or short-circuit it.
3. **Audit logging:** Every agent decision must emit an audit event via `audit_logger`. This includes both success and error paths.

## DeerFlow Toggle

Controlled by `USE_DEERFLOW` env var (default: `false`).

| `USE_DEERFLOW` | Execution path |
|---|---|
| `false` | `fallback_engine` — direct LLM calls via Anthropic/OpenAI SDK |
| `true` | `deerflow_adapter` — routes through DeerFlow harness |

Both paths must produce equivalent `AgentResponse` output. When changing orchestration logic, test both paths. The toggle is in `config.py` as `settings.USE_DEERFLOW`.

## Pydantic v2 Patterns

Same as backend — always use v2 style:

```python
# ✅ ConfigDict
from pydantic import BaseModel, ConfigDict
class MyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ✅ model_validate
obj = MyModel.model_validate(data)

# ✅ field_validator
from pydantic import field_validator
class MyModel(BaseModel):
    @field_validator("field")
    @classmethod
    def check(cls, v: str) -> str:
        return v.strip()
```

## Incremental Formatting

Format only files you touch. Do not reformat the entire module in a single commit.
```

- [ ] **Step 2: Commit**

```bash
git add agent/CLAUDE.md
git commit -m "docs(agent): add module-level CLAUDE.md with quality commands, risk controls, and deerflow toggle docs"
```

---

## Self-Review Checklist

- [x] All 8 ideas from the spec are covered (3 CLAUDE.md files, ESLint+Prettier frontend, vue-tsc script, ruff+mypy backend, ruff+mypy agent, Pydantic v2 patterns)
- [x] No TBDs or placeholders
- [x] Python version targets match pyproject.toml (3.11 backend, 3.12 agent)
- [x] ruff version pinned consistently (>=0.9.0) across both Python modules
- [x] Incremental formatting policy stated in both Python CLAUDE.md files and frontend CLAUDE.md
- [x] DeerFlow toggle table matches `config.py` (`settings.USE_DEERFLOW`, default `false`)
- [x] Pydantic v2 patterns consistent between backend and agent CLAUDE.md
