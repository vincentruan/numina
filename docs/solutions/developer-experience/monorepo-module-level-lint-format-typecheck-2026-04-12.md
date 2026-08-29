---
title: "Monorepo module-level lint/format/typecheck setup (Vue 3 + TS + FastAPI)"
date: 2026-04-12
last_updated: 2026-05-14
category: developer-experience
module: frontend, server
problem_type: developer_experience
component: tooling
severity: medium
applies_when:
  - Adding linting/formatting to a monorepo with mixed language stacks
  - Setting up ESLint v9 flat config for Vue 3 + TypeScript
  - Adding ruff + mypy to Python FastAPI modules using uv
  - Creating module-level CLAUDE.md delta docs in a multi-module repo
tags: [eslint, prettier, vue3, typescript, ruff, mypy, pydantic, fastapi, monorepo, claude-md, tooling]
---

# Monorepo module-level lint/format/typecheck setup (Vue 3 + TS + FastAPI)

## Context

Numina is a monorepo with two top-level modules: `frontend/` (Vue 3 + TypeScript + Vite) and `server/` (Python — `server/apps/backend/` FastAPI + SQLAlchemy, `server/apps/agent/` DeerFlow). The repo had no linting, formatting, or type-check tooling configured — root `CLAUDE.md` said "match existing style." This made code review noisy and style inconsistent across contributors.

> **Note (2026-07-31):** Frontend config paths updated — `frontend/eslint.config.js` → `frontend/apps/main/eslint.config.js`, `frontend/.prettierrc` → `frontend/apps/main/.prettierrc`, `frontend/package.json` → `frontend/apps/main/package.json`. The frontend is now a multi-app workspace; tooling configs live in each app, not the workspace root.

> **Note (2026-05-14):** Phase 2 consolidated `backend/` and `agent/` into `server/apps/backend/` and `server/apps/agent/`. Path references below have been updated accordingly.

The solution: module-level tooling (each module owns its own dev-experience config) plus module-level `CLAUDE.md` delta docs that tell contributors exactly how to run quality checks inside that module.

## Guidance

### Frontend (Vue 3 + TS): ESLint v9 flat config + Prettier + vue-tsc

**Install packages:**
```bash
npm install --save-dev \
  eslint @eslint/js typescript-eslint \
  eslint-plugin-vue prettier eslint-config-prettier globals
```

**Create `frontend/apps/main/eslint.config.js`:**
```js
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'
import prettierConfig from 'eslint-config-prettier'
import globals from 'globals'

export default tseslint.config(
  // Flat config does NOT auto-ignore like legacy .eslintrc — must be explicit
  {
    ignores: ['**/node_modules/**', '**/dist/**', '**/coverage/**', '**/*.d.ts'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  prettierConfig,
  {
    files: ['src/**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        extraFileExtensions: ['.vue'],
      },
      // REQUIRED: declare browser globals or you get no-undef for window/document/HTMLElement
      globals: globals.browser,
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    languageOptions: { globals: globals.browser },
    rules: {
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
)
```

**Create `frontend/apps/main/.prettierrc`:**
```json
{
  "singleQuote": true,
  "semi": false,
  "trailingComma": "all",
  "printWidth": 100,
  "endOfLine": "lf"
}
```

**Add npm scripts to `frontend/apps/main/package.json`:**
```json
"lint":      "eslint src",
"lint:fix":  "eslint src --fix",
"format":    "prettier --write src",
"typecheck": "vue-tsc --noEmit -p tsconfig.app.json"
```

> **⚠️ Correction (2026-07-23):** this doc previously recommended bare `"typecheck": "vue-tsc --noEmit"`. That is a **silent-pass no-op** when the root `tsconfig.json` is a references-only file with `"files": []` — vue-tsc reads the root config, checks zero files, and exits 0. Always pass `-p tsconfig.app.json` (and add `"typecheck:test": "vue-tsc --noEmit -p tsconfig.vitest.json"` for tests, wired into CI). See `vue-tsc-references-only-root-tsconfig-noop-typecheck-gate-2026-07-23.md`.

### Backend (FastAPI, Python 3.12): ruff + mypy

**Add to `[dependency-groups] dev` in `server/pyproject.toml`** (or the backend extras section):
```toml
"ruff>=0.9.0",
"mypy>=1.13.0",
```

**Append tool config:**
```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
warn_return_any = true
plugins = ["pydantic.mypy"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

**Run:** `uv sync` then verify with `uv run ruff check .` and `uv run mypy apps/backend/`

### Agent (DeerFlow, Python 3.12): same pattern

Identical to backend. For mypy, exclude vendor: `uv run mypy apps/agent/ --exclude apps/agent/vendor`.

### Module-level CLAUDE.md delta docs

Each module gets a `CLAUDE.md` that answers: how do I run quality checks here, and what are the local conventions? It references root `CLAUDE.md` for shared rules and only adds module-specific content.

Minimum sections:
- **Quality Commands** — exact commands to run lint/format/typecheck/test
- **Tooling** — brief note on each tool and where its config lives
- **Key Conventions** — module-specific patterns (Pydantic v2 style, Vant auto-import, etc.)
- **Incremental Formatting** — policy: format only touched files, not the whole module

Update root `CLAUDE.md` to remove "no linter/formatter configured" and add a per-module tooling summary pointing to module docs.

## Why This Matters

- **Consistency:** Formatter + linter makes style predictable; reviews focus on logic, not whitespace.
- **Faster feedback:** Module-local commands let contributors validate without running the whole monorepo.
- **Correctness:** ESLint + ruff B/SIM rules catch real issues early (undefined vars, unused imports, suspicious constructs).
- **Type safety:** `vue-tsc` and `mypy` prevent "works at runtime but breaks later" regressions at API boundaries.
- **Onboarding:** Module CLAUDE.md files give contributors the right context at the point of change.

## When to Apply

- Adding quality tooling to a monorepo with mixed language stacks (JS/TS + Python)
- Setting up ESLint v9 flat config for Vue 3 + TypeScript for the first time
- Adding ruff + mypy to Python FastAPI modules managed with uv
- Creating module-level documentation in a multi-module repo where root docs are already thorough

## Examples

### Pitfall: ESLint `no-undef` for browser globals in flat config

**Symptom:** After adding ESLint flat config, you get errors like:
```
'window' is not defined   no-undef
'document' is not defined  no-undef
'HTMLElement' is not defined  no-undef
```

**Cause:** ESLint v9 flat config does not automatically declare browser globals. The legacy `.eslintrc` had `env: { browser: true }` — flat config requires explicit `globals.browser`.

**Fix:** Add `globals: globals.browser` to `languageOptions` for both `.vue` and `.ts` file blocks:
```js
import globals from 'globals'

{
  files: ['src/**/*.vue'],
  languageOptions: {
    globals: globals.browser,  // ← required
    parserOptions: { parser: tseslint.parser, extraFileExtensions: ['.vue'] },
  },
}
```

### Pitfall: Flat config doesn't auto-ignore `dist/` and `node_modules/`

**Symptom:** Running `eslint .` traverses build output and node_modules, causing slow runs or false positives.

**Fix:** Add an explicit `ignores` block as the first item in the config array:
```js
export default tseslint.config(
  { ignores: ['**/node_modules/**', '**/dist/**', '**/coverage/**', '**/*.d.ts'] },
  // ... rest of config
)
```

### Pitfall: Vant auto-import is build tooling, not ESLint

**Wrong doc:** "ESLint is configured to allow Vant auto-import"
**Correct doc:** "Vant components are auto-imported via `unplugin-vue-components` (build tooling). Do not manually import them."

Vant auto-import is handled by the Vite plugin at build time. ESLint doesn't need special configuration for it — just don't add `no-undef` rules for component names.

### Pitfall: `[tool.pydantic-mypy]` section missing

Without the plugin options section, `pydantic.mypy` runs but with weaker model field checking. Add:
```toml
[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

### Incremental formatting policy

When introducing formatters to an existing codebase, do NOT run `ruff format .` or `prettier --write src` on the entire codebase in one commit. This creates massive diffs that obscure blame history and make bisect painful. Instead: format only files you touch in each PR.

## Related

- Design spec: `docs/superpowers/specs/2026-04-11-module-tooling-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-11-module-tooling.md`
- Module docs: `frontend/apps/main/CLAUDE.md`, `server/apps/backend/CLAUDE.md`, `server/apps/agent/CLAUDE.md`
