# CLAUDE.md Restructuring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure all four CLAUDE.md files so root is a lean ~120-line routing document and each module file is self-contained, standardized, and optimized for AI agent consumption.

**Architecture:** Strict hierarchy — root keeps behavioral guidelines, project identity, cross-cutting conventions, and skill routing. Module files follow a standardized template: Quality Commands → Tooling → Key Invariants → [Don't Do] → [Watch Out] → Patterns → Links. `Don't Do` and `Watch Out` sections are optional — only include when there is genuinely important content. No duplication except Pydantic v2 patterns (acceptable across independent modules).

**Tech Stack:** Markdown only — no code changes.

---

## File Map

| File | Action | Lines (target) |
|------|--------|----------------|
| `CLAUDE.md` | Rewrite | ~120 |
| `backend/CLAUDE.md` | Rewrite | ~200 |
| `frontend/CLAUDE.md` | Rewrite | ~130 |
| `agent/CLAUDE.md` | Rewrite | ~110 |

---

## Context: Current CLAUDE.md Content to Preserve

Before starting, the implementer must read all four files to extract content. Key sections to migrate:

**From root `CLAUDE.md` → `backend/CLAUDE.md`:**
- Family Invitation Code system (lines ~319-329)
- Data Model Key Relationships (lines ~331-343)
- Asset Enhanced Fields (lines ~345-350)
- Predefined Categories (lines ~352-356)
- Common Pitfalls (lines ~440-449)
- Backend code style (lines ~451-460)

**From root `CLAUDE.md` → `frontend/CLAUDE.md`:**
- Frontend code style (lines ~461-471)

**From root `CLAUDE.md` → keep in root:**
- Behavioral Guidelines (lines 5-42) — keep verbatim
- Project Overview + Tech Stack (lines 44-51) — keep, trim architecture details
- Skill Routing (lines ~472-end) — keep verbatim

**Cross-cutting conventions to consolidate in root:**
- "UI text in Chinese" — currently scattered
- "Error messages in Chinese" — currently in backend section
- "Incremental formatting" — currently in root + all three module files (remove from modules)

---

## Task 1: Rewrite root `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read the current root CLAUDE.md**

```bash
cat CLAUDE.md | head -50
```

Confirm the Behavioral Guidelines section (lines 5-42) and Skill Routing section (lines ~472-end) are intact before editing.

- [ ] **Step 2: Write the new root CLAUDE.md**

Replace the entire file with:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Behavioral Guidelines

### 1. Think Before Coding

Before implementing, state assumptions explicitly. If multiple interpretations exist, present them — don't pick silently. If a simpler approach exists, say so. If something is unclear, stop and ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must. When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that **your** changes made unused, but leave pre-existing dead code alone.

Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals before starting:

- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Add validation" → write tests for invalid inputs, then make them pass.
- "Refactor X" → ensure tests pass before and after.

For multi-step tasks, state a brief plan with explicit verify steps before coding.

## Project Overview

Numina (家庭资产可视化) is a privacy-first, self-hosted family asset visualization and management system. It helps families track, manage, and visualize their assets and liabilities across multiple members with role-based access control.

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Agent | Python 3.11+ + FastAPI + DeerFlow/LangChain |
| Infrastructure | Docker Compose + Nginx |

## Cross-Cutting Conventions

These apply to all modules. Module-specific conventions live in each module's `CLAUDE.md`.

- **UI text in Chinese** — all user-facing messages (toasts, dialogs, labels) must be in Chinese. Frontend owns the emoji convention — see `frontend/CLAUDE.md`.
- **Error messages in Chinese** — backend HTTP exceptions use Chinese detail strings: `raise HTTPException(status_code=404, detail="资产不存在")`
- **Incremental formatting** — format only files you touch. Do not run formatters on entire modules in a single commit.
- **No speculative code** — don't add features, abstractions, or error handling beyond what was asked.

## Module Documentation

For module-specific dev commands, conventions, and patterns:

| Module | CLAUDE.md | README |
|--------|-----------|--------|
| Backend | [`backend/CLAUDE.md`](./backend/CLAUDE.md) | [`backend/README.md`](./backend/README.md) |
| Frontend | [`frontend/CLAUDE.md`](./frontend/CLAUDE.md) | [`frontend/README.md`](./frontend/README.md) |
| Agent | [`agent/CLAUDE.md`](./agent/CLAUDE.md) | [`agent/README.md`](./agent/README.md) |

## Development Commands

### Docker (All Services)

```bash
docker-compose up -d          # Start all services
docker-compose logs -f        # View logs
docker-compose up -d --build  # Rebuild after code changes
docker-compose down           # Stop all services
# Access at http://localhost:8080
```

### Quick Reference

```bash
# Backend
cd backend && uv run pytest tests/ -v

# Frontend
cd frontend && npm run typecheck

# Agent
cd agent && uv run pytest tests/ -v
```
```

> Note: Keep the existing Skill Routing section verbatim at the end of the file. Read it from the current file before overwriting.

- [ ] **Step 3: Append the existing Skill Routing section**

Read the current `CLAUDE.md` from line ~472 to end and append it to the new file verbatim.

- [ ] **Step 4: Verify line count**

```bash
wc -l CLAUDE.md
```

Expected: 100–150 lines.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(root): slim CLAUDE.md to behavioral guidelines, conventions, and module routing"
```

---

## Task 2: Rewrite `backend/CLAUDE.md`

**Files:**
- Modify: `backend/CLAUDE.md`

- [ ] **Step 1: Read current backend/CLAUDE.md and root CLAUDE.md**

Read both files to extract content to migrate:
- From `backend/CLAUDE.md`: Quality Commands, Tooling, Pydantic v2 patterns, Alembic note, incremental formatting note
- From root `CLAUDE.md`: Family Invitation Code, Data Model Relationships, Asset Enhanced Fields, Predefined Categories, Common Pitfalls, backend code style

- [ ] **Step 2: Write the new backend/CLAUDE.md**

```markdown
# backend/CLAUDE.md

Module-specific guidance for the Python FastAPI backend.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

```bash
uv run ruff check .                    # lint
uv run ruff check . --fix              # lint + auto-fix
uv run ruff format .                   # format (only files you touch)
uv run mypy app/                       # type check
uv run pytest tests/ -v                # run all tests
uv run pytest tests/ -v -k "keyword"   # run tests matching keyword
uv run alembic revision --autogenerate -m "description"   # create migration
uv run alembic upgrade head                                # apply migrations
```

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I (imports), UP (pyupgrade).
- **mypy:** type checker. Config in `pyproject.toml` under `[tool.mypy]`. Starts lenient (`ignore_missing_imports = true`) — ratchet strictness over time by adding `disallow_untyped_defs = true` per module.
- **pytest:** test runner. Tests in `backend/tests/`. Each test gets a fresh in-memory SQLite DB.

## Key Invariants

- **Always run `alembic upgrade head` before starting the app on an existing database.** `Base.metadata.create_all()` only creates tables for fresh installs — it does not apply migrations. Skipping causes `OperationalError: no such column` on endpoints that read newly added columns.
- **Pydantic v2 only** — use `ConfigDict`, `model_validate`, `field_validator`. Never v1 style (`class Config`, `parse_obj`, `validator`).
- **Error messages in Chinese** — `raise HTTPException(status_code=404, detail="资产不存在")`

## Patterns

### Pydantic v2

```python
# ✅ ConfigDict
from pydantic import BaseModel, ConfigDict
class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ✅ model_validate
obj = MySchema.model_validate(orm_instance)

# ✅ field_validator
from pydantic import field_validator
class MySchema(BaseModel):
    @field_validator("field_name")
    @classmethod
    def validate_field(cls, v: str) -> str:
        return v.strip()
```

### Code Style

- **Import order:** stdlib → third-party → local (`app.*`), blank line between groups
- **Type annotations:** `str | None`, `list[str]` (Python 3.10+ union syntax)
- **Private helpers:** `_to_response(asset)` (leading underscore)

### Family Invitation Code

- 6-character alphanumeric code stored on the `Family` model
- `POST /api/v1/family/invite-code` regenerates it (owner only)
- `POST /api/v1/auth/family/join` accepts it — joins the caller to that family
- Codes are single-use per join attempt but not invalidated after use (any member can share the same code)

### Data Model Key Relationships

- `User` → `Family` (many-to-one via `family_id`)
- `Asset` → `User` (many-to-one via `owner_id`); family aggregate queries join through `User.family_id`
- `Asset` → `Category` (many-to-one); `Asset` ↔ `Tag` (many-to-many via `asset_tags`)
- `Liability` → `Asset` (optional many-to-one via `linked_asset_id`)
- `AssetSnapshot` → `Family` (many-to-one); one snapshot per family per day

### Asset Enhanced Fields

Physical assets carry daily-cost fields:
- `purchase_price`, `current_value`, `purchase_date`, `expected_lifespan_years`, `annual_maintenance_cost`
- `daily_cost` = `(purchase_price + total_maintenance) / total_days_owned` (computed, not stored)
- `usage_frequency`: `daily` / `weekly` / `monthly` / `rarely` / `never`

Financial assets carry return fields:
- `principal_amount`, `current_value`, `annual_return_rate`
- `return_rate` = `(current_value - principal_amount) / principal_amount` (computed)

### Predefined Categories

21 system categories seeded on startup (read-only, `is_system=True`):
- **Physical (13):** 房产, 车辆, 数码产品, 家电, 家具, 珠宝首饰, 服饰, 美妆, 运动器材, 玩具, 宠物, 乐器, 箱包
- **Financial (8):** 存款, 基金, 股票, 债券, 保险, 理财产品, 数字货币, 其他金融

### Common Pitfalls

- Auth endpoints (`/login`, `/register`, `/refresh`) return `200`, not `201`
- Asset and Liability `POST` endpoints return `201`
- `TokenResponse` does not include `user` — call `GET /auth/me` separately after login
- `DELETE /assets/{id}` archives (sets `is_archived=True`), does not hard-delete
- Dashboard queries filter `is_archived=False` — archived assets are excluded from all aggregates

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
- [`docs/solutions/`](../docs/solutions/) — documented solutions to past problems
```

- [ ] **Step 3: Verify line count**

```bash
wc -l backend/CLAUDE.md
```

Expected: 120–200 lines.

- [ ] **Step 4: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(backend): rewrite CLAUDE.md with standardized template and domain knowledge"
```

---

## Task 3: Rewrite `frontend/CLAUDE.md`

**Files:**
- Modify: `frontend/CLAUDE.md`

- [ ] **Step 1: Read current frontend/CLAUDE.md**

Read the file to extract: Quality Commands, Tooling, emoji convention table and implementation rules, i18n workflow.

- [ ] **Step 2: Write the new frontend/CLAUDE.md**

```markdown
# frontend/CLAUDE.md

Module-specific guidance for the Vue 3 + TypeScript frontend.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

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

## Key Invariants

- **Emoji convention** — All user-facing toast messages, confirmation dialogs, and error messages MUST include an emoji prefix via i18n keys. Never hard-code strings directly in Vue files. See Patterns section.
- **Vant components are auto-imported** via `unplugin-vue-components`. Do not manually import them.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.
- **Incremental formatting** — format only files you touch. Do not run `npm run format` on the entire repo in a single commit.

## Patterns

### Emoji Convention for User-Facing Messages

| Type | Emoji | Examples |
|------|-------|---------|
| Success | ✅ | `✅ 添加成功`, `✅ 已保存` |
| Failure/Error | ❌ | `❌ 操作失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 请先选择资产`, `⚠️ 邀请码无效` |
| Delete | 🗑️ | `🗑️ 已删除` |
| Info/Status | 📡, 🤖, 🔑 | `📡 网络错误`, `🤖 AI 功能未启用` |
| Special | 💰, 🎨, 🔥, 🎉 | `💰 还款成功`, `🎉 注册成功` |

**Implementation rules:**
1. Define emoji-prefixed strings in `src/i18n/locales/*.ts` under `toast` or `errors`
2. Use `t('toast.xxx')` or `t('errors.xxx')` in Vue files — never hard-coded strings
3. Confirmation dialogs use emoji too: `t('toast.confirmDelete', { name })` → `⚠️ 确定要删除「{name}」吗？`
4. Dynamic messages use interpolation: `t('toast.assetDeletedCount', { count: 3 })` → `🗑️ 已删除 3 项资产`

```ts
// ✅ Correct
showToast(t('toast.addSuccess'))        // Shows: ✅ 添加成功

// ❌ Wrong — hard-coded string without emoji
showToast('添加成功')
```

### Adding New Messages

1. Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` and `en-US.ts` under `toast` or `errors`
2. Use `t('key')` or `t('key', { param })` in the Vue file
3. Run `npm run typecheck` to verify

### Path Alias

`@/` maps to `src/` — configured in both `vite.config.ts` and `tsconfig.app.json`.

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, component structure
```

- [ ] **Step 3: Verify line count**

```bash
wc -l frontend/CLAUDE.md
```

Expected: 100–140 lines.

- [ ] **Step 4: Commit**

```bash
git add frontend/CLAUDE.md
git commit -m "docs(frontend): rewrite CLAUDE.md with standardized template, promote emoji to Key Invariants"
```

---

## Task 4: Rewrite `agent/CLAUDE.md`

**Files:**
- Modify: `agent/CLAUDE.md`

- [ ] **Step 1: Read current agent/CLAUDE.md**

Read the file to extract: Quality Commands, Tooling, Risk Control Invariants, DeerFlow Toggle table, Pydantic v2 patterns, incremental formatting note.

- [ ] **Step 2: Write the new agent/CLAUDE.md**

```markdown
# agent/CLAUDE.md

Module-specific guidance for the Python FastAPI AI agent microservice.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

```bash
uv run ruff check .              # lint
uv run ruff check . --fix        # lint + auto-fix
uv run ruff format .             # format (only files you touch)
uv run mypy . --exclude vendor   # type check
uv run pytest tests/ -v          # run all tests
```

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I, UP.
- **mypy:** type checker. `ignore_missing_imports = true` is intentional — LangChain and DeerFlow stubs are incomplete. Use `# type: ignore[<code>]` with an inline comment explaining why when suppressing.
- **pytest + pytest-asyncio:** async test runner. `asyncio_mode = "auto"` is set in `pyproject.toml`.

## Key Invariants (Risk Control)

These must hold in every code path — never bypass them:

1. **PII redaction:** Always call `pii_redactor` before passing user data to any tool call or writing to logs.
2. **Policy guard:** All agent requests must pass through `policy_guard`. Never skip or short-circuit it.
3. **Audit logging:** Every agent decision must emit an audit event via `audit_logger`. This includes both success and error paths.

## Patterns

### DeerFlow Toggle

Controlled by `USE_DEERFLOW` env var (default: `false`). Set in `config.py` as `settings.USE_DEERFLOW`.

| `USE_DEERFLOW` | Execution path |
|---|---|
| `false` | `fallback_engine` — direct LLM calls via Anthropic/OpenAI SDK |
| `true` | `deerflow_adapter` — routes through DeerFlow harness |

Both paths must produce equivalent `AgentResponse` output. When changing orchestration logic, test both paths.

### Pydantic v2

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

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
```

- [ ] **Step 3: Verify line count**

```bash
wc -l agent/CLAUDE.md
```

Expected: 90–120 lines.

- [ ] **Step 4: Commit**

```bash
git add agent/CLAUDE.md
git commit -m "docs(agent): rewrite CLAUDE.md with standardized template, add Links section"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|------------|
| Root ≤150 lines, keeps behavioral guidelines + project identity + cross-cutting conventions + skill routing | Task 1 |
| Remove all dev commands, architecture, domain knowledge from root | Task 1 |
| Standardized template: Quality Commands → Tooling → Key Invariants → Patterns → Links | Tasks 2, 3, 4 |
| `Don't Do` / `Watch Out` optional — only when genuinely needed | None added (no genuinely critical anti-patterns beyond Key Invariants) |
| backend: add Key Invariants (alembic warning, Pydantic v2, Chinese errors) | Task 2 |
| backend: add Domain Knowledge (Family Invitation Code, data model, asset fields, categories, pitfalls) | Task 2 |
| frontend: promote emoji convention to Key Invariants | Task 3 |
| frontend: remove incremental formatting (moves to root) | Task 3 |
| agent: rename Risk Control Invariants → Key Invariants | Task 4 |
| agent: add Links section | Task 4 |
| agent: remove incremental formatting (moves to root) | Task 4 |
| backend: remove incremental formatting (moves to root) | Task 2 |
| "Incremental formatting" in root only | Task 1 |
| Content ownership: no duplication except Pydantic v2 in backend + agent | Tasks 1-4 |

**Placeholder scan:** No TBDs, TODOs, or vague steps. All file content is written in full.

**Consistency check:** No cross-task dependencies — each task rewrites one independent file.
