# CLAUDE.md Restructuring Design

**Date:** 2026-04-23  
**Status:** Draft  
**Approach:** Strict hierarchy with standardized module templates

## Problem

Current CLAUDE.md structure has four issues:

1. **Root CLAUDE.md is too long** (~500 lines) — AI agents working in a single module load irrelevant context from other modules
2. **Content overlap** — "incremental formatting" rule appears in root + all three module files; Pydantic v2 patterns duplicated in backend + agent
3. **Inconsistent module structure** — backend/frontend/agent CLAUDE.md files have different section orders and depths
4. **Missing key sections** — backend lacks "Key Invariants", frontend's emoji rule isn't prominently marked as an invariant, agent lacks "Links" section

The stated goal: **standardize and modularize CLAUDE.md files for optimal AI agent consumption**, following known best practices adapted to this project.

## Design Principles

1. **Strict hierarchy** — Root = behavioral guidelines + project identity + skill routing. Modules = everything else.
2. **Single source of truth** — Each piece of information lives in exactly one file. No duplication except where modules are truly independent (e.g., Pydantic v2 patterns in backend + agent).
3. **Standardized template** — All module CLAUDE.md files follow the same section order: Quality Commands → Tooling → Key Invariants → Patterns → Links.
4. **AI-first** — Optimize for Claude Code loading context, not human readability.

## Proposed Structure

### Root `CLAUDE.md` — ~120 lines

**Keeps:**

1. **Behavioral Guidelines** (lines 5-42, keep as-is)
   - Think Before Coding
   - Simplicity First
   - Surgical Changes
   - Goal-Driven Execution

2. **Project Identity** (lines 44-51, trim)
   - One-paragraph project overview
   - Tech stack table (3 lines: Backend, Frontend, Infrastructure)
   - Remove: detailed architecture descriptions (already covered in module README.md files)

3. **Cross-cutting Conventions** (new consolidated section)
   - UI text in Chinese (user-facing messages)
   - Error messages in Chinese (backend exceptions)
   - Incremental formatting rule: "Format only files you touch — do not reformat entire modules"
   - Emoji convention ownership: "Frontend owns emoji convention — see `frontend/CLAUDE.md`"

4. **Skill Routing** (lines 472-end, keep as-is)
   - The routing rules at the bottom

**Removes:**
- All dev commands (lines 53-206) → move to module files
- Architecture sections (lines 209-303) → move to module files
- Key Patterns (lines 305-317) → move to module files
- Family Invitation Code (lines 319-329) → move to `backend/CLAUDE.md`
- Data Model Relationships (lines 331-343) → move to `backend/CLAUDE.md`
- Asset Enhanced Fields (lines 345-350) → move to `backend/CLAUDE.md`
- Predefined Categories (lines 352-356) → move to `backend/CLAUDE.md`
- Documented Solutions (lines 358-364) → keep pointer, details in `docs/solutions/README.md`
- Testing sections (lines 366-438) → move to module files
- Common Pitfalls (lines 440-449) → move to `backend/CLAUDE.md`
- Code Style sections (lines 451-471) → move to module files

---

### Module CLAUDE.md Standardized Template

Each module file follows this exact structure:

```markdown
# {module}/CLAUDE.md

Module-specific guidance for the {one-line description}.
See root `CLAUDE.md` for behavioral guidelines and cross-cutting conventions.

## Quality Commands

[bash code block with all quality commands]

## Tooling

- **{tool1}:** description + config location
- **{tool2}:** description + config location

## Key Invariants

[Non-negotiable rules that must always hold]

## Patterns

[Language/framework-specific patterns]

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — contributor quick start, architecture
- [Other relevant docs]
```

---

### `backend/CLAUDE.md` — ~150 lines

**Sections:**

1. **Header** — one-line description + pointer to root CLAUDE.md

2. **Quality Commands**
   ```bash
   uv run ruff check .          # lint
   uv run ruff check . --fix    # lint + auto-fix
   uv run ruff format .         # format (only files you touch)
   uv run mypy app/             # type check
   uv run pytest tests/ -v      # run all tests
   uv run pytest tests/ -v -k "keyword"   # run tests matching keyword
   uv run alembic revision --autogenerate -m "description"   # create migration
   uv run alembic upgrade head                                # apply migrations
   ```

3. **Tooling**
   - **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I (imports), UP (pyupgrade).
   - **mypy:** type checker. Config in `pyproject.toml` under `[tool.mypy]`. Starts lenient (`ignore_missing_imports = true`).
   - **pytest:** test runner. Tests in `backend/tests/`. Each test gets a fresh in-memory SQLite DB.

4. **Key Invariants**
   - **Always run `alembic upgrade head` before starting the app on an existing database.** The app's `Base.metadata.create_all()` only creates tables for fresh installs — it does not apply migrations. Skipping this causes `OperationalError: no such column` on endpoints that read newly added columns.
   - **Pydantic v2 only** — use `ConfigDict`, `model_validate`, `field_validator` (never v1 style: `class Config`, `parse_obj`, `validator`)
   - **Error messages in Chinese** — `raise HTTPException(status_code=404, detail="资产不存在")`

5. **Patterns**
   - Pydantic v2 examples (ConfigDict, model_validate, field_validator)
   - Import order: stdlib → third-party → local (`app.*`), blank line between groups
   - Type annotations: `str | None`, `list[str]` (Python 3.10+ syntax)
   - Private helpers: `_to_response(asset)` (leading underscore)

6. **Domain Knowledge** (new section)
   - Family Invitation Code system
   - Data Model Key Relationships
   - Asset Enhanced Fields
   - Predefined Categories (21 total)
   - Common Pitfalls (auth returns 200, asset POST returns 201, etc.)

7. **Links**
   - Root [`CLAUDE.md`](../CLAUDE.md)
   - Module [`README.md`](./README.md)
   - [`docs/solutions/`](../docs/solutions/) — documented solutions to past problems

---

### `frontend/CLAUDE.md` — ~120 lines

**Sections:**

1. **Header** — one-line description + pointer to root CLAUDE.md

2. **Quality Commands**
   ```bash
   npm run lint          # ESLint — check for errors and warnings
   npm run lint:fix      # ESLint — auto-fix where possible
   npm run format        # Prettier — format all files in src/
   npm run typecheck     # vue-tsc --noEmit — type check without building
   npm run build         # vue-tsc -b && vite build — full production build
   npm run test:run      # vitest run — run tests once (no watch)
   ```

3. **Tooling**
   - **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
   - **Prettier:** config at `.prettierrc`. Single quotes, no semicolons, trailing commas, 100-char width.
   - **vue-tsc:** canonical type gate. Run `npm run typecheck` before pushing. Strict mode is on (`tsconfig.app.json`).
   - **vitest:** test runner. Tests live in `src/**/*.test.ts` or `src/**/*.spec.ts`.

4. **Key Invariants**
   - **Emoji convention for user-facing messages** — All toast messages, confirmation dialogs, and error messages MUST include an emoji prefix. Use i18n keys (`t('toast.xxx')`) — never hard-coded strings. See Patterns section for implementation details.
   - **Vant components are auto-imported** via `unplugin-vue-components` (build tooling). Do not manually import them.
   - **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
   - **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.

5. **Patterns**
   - Emoji convention implementation (full table from current file, lines 59-83)
   - i18n workflow for adding new messages
   - Path alias `@/` maps to `src/`

6. **Links**
   - Root [`CLAUDE.md`](../CLAUDE.md)
   - Module [`README.md`](./README.md)

---

### `agent/CLAUDE.md` — ~100 lines

**Sections:**

1. **Header** — one-line description + pointer to root CLAUDE.md

2. **Quality Commands**
   ```bash
   uv run ruff check .          # lint
   uv run ruff check . --fix    # lint + auto-fix
   uv run ruff format .         # format
   uv run mypy . --exclude vendor   # type check
   uv run pytest tests/ -v      # run all tests
   ```

3. **Tooling**
   - **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I, UP.
   - **mypy:** type checker. `ignore_missing_imports = true` is intentional — LangChain and DeerFlow stubs are incomplete. Use `# type: ignore[<code>]` with an inline comment explaining why when suppressing.
   - **pytest + pytest-asyncio:** async test runner. `asyncio_mode = "auto"` is set in `pyproject.toml`.

4. **Key Invariants (Risk Control)**
   - **PII redaction:** Always call `pii_redactor` before passing user data to any tool call or writing to logs.
   - **Policy guard:** All agent requests must pass through `policy_guard`. Never skip or short-circuit it.
   - **Audit logging:** Every agent decision must emit an audit event via `audit_logger`. This includes both success and error paths.

5. **Patterns**
   - DeerFlow Toggle table (keep as-is from current file)
   - Pydantic v2 examples (ConfigDict, model_validate, field_validator)

6. **Links**
   - Root [`CLAUDE.md`](../CLAUDE.md)
   - Module [`README.md`](./README.md)

---

## Content Ownership Table

| Content | Lives in |
|---------|----------|
| Behavioral guidelines (Think Before Coding, etc.) | Root only |
| Project overview + tech stack | Root only |
| Skill routing | Root only |
| "UI text in Chinese" | Root only |
| "Error messages in Chinese" | Root only |
| "Incremental formatting" | Root only (remove from module files) |
| "No `as any`/`@ts-ignore`" | `frontend/CLAUDE.md` only |
| Pydantic v2 patterns | `backend/CLAUDE.md` + `agent/CLAUDE.md` (acceptable duplication — independent modules) |
| Emoji convention | `frontend/CLAUDE.md` only |
| Risk control invariants | `agent/CLAUDE.md` only |
| Alembic warning | `backend/CLAUDE.md` only |
| Dev commands | Each module's own file only |
| Architecture details | Each module's own file (or delegate to README.md) |
| Common pitfalls | `backend/CLAUDE.md` only (all are backend-specific) |
| Family Invitation Code | `backend/CLAUDE.md` only |
| Data model relationships | `backend/CLAUDE.md` only |
| Predefined categories | `backend/CLAUDE.md` only |

---

## Migration Plan

1. **Create new root `CLAUDE.md`** — extract behavioral guidelines, project identity, cross-cutting conventions, skill routing. ~120 lines.
2. **Rewrite `backend/CLAUDE.md`** — follow standardized template, add Key Invariants section, add Domain Knowledge section with Family Invitation Code / data model / common pitfalls.
3. **Rewrite `frontend/CLAUDE.md`** — follow standardized template, promote emoji convention to Key Invariants, keep full implementation examples.
4. **Rewrite `agent/CLAUDE.md`** — follow standardized template, keep Risk Control Invariants as Key Invariants, add Links section.
5. **Commit** — single commit: `docs: restructure CLAUDE.md files for modular AI agent consumption`

---

## Success Criteria

- Root `CLAUDE.md` is ≤150 lines
- All three module CLAUDE.md files follow the same section order: Quality Commands → Tooling → Key Invariants → Patterns → Links
- No content duplication except Pydantic v2 patterns (acceptable for independent modules)
- Each module file is self-contained — an AI agent working in that module has everything it needs without reading other module files
- "Incremental formatting" rule appears exactly once (root only)

---

## Non-Goals

- Rewriting content — we're restructuring, not rewriting
- Changing conventions — we're organizing existing conventions, not inventing new ones
- Updating README files — those were already restructured in the previous task

---

## Open Questions

None — design approved.
