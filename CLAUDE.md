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

## Known Pitfalls

### URL Style — No Trailing Slash, No Redirects

All API endpoints must respond with 200 directly. No 307 redirects. This keeps frontend/backend URL style consistent and avoids Mixed Content errors in HTTPS deployments.

**Rule:** `redirect_slashes=False` is set in `app/main.py`. All router root-path decorators must use `""` not `"/"`:
```python
# ✅ Correct — hits 200 directly
@router.get("")
@router.post("")

# ❌ Wrong — FastAPI issues 307 redirect, breaks HTTPS behind nginx
@router.get("/")
@router.post("/")
```

Applies to every router with root-path endpoints. Frontend calls must also omit trailing slashes.

## Cross-Cutting Conventions

These apply to all modules. Module-specific conventions live in each module's `CLAUDE.md`.

- **i18n required for all UI strings** — every user-facing string (toasts, dialogs, labels, status text) must be defined in `src/i18n/locales/zh-CN.ts` and referenced via `t('key')`. Never hard-code Chinese strings directly in `.vue` files or `.ts` logic — not even in template ternaries. Applies to both `frontend/apps/main` and `frontend/apps/child`.
- **Emoji convention** — all toast/error strings must include an emoji prefix. See `frontend/apps/main/CLAUDE.md` for the full table.
- **Error messages in Chinese** — backend HTTP exceptions use Chinese detail strings: `raise HTTPException(status_code=404, detail="资产不存在")`
- **Incremental formatting** — format only files you touch. Do not run formatters on entire modules in a single commit.
- **No speculative code** — don't add features, abstractions, or error handling beyond what was asked.
- **Python: Pydantic v2 only** — use `ConfigDict`, `model_validate`, `field_validator`. Never v1 style (`class Config`, `parse_obj`, `validator`).
- **Past solutions** — `docs/solutions/` contains documented fixes for recurring problems. Check before debugging known issue categories.

## Module Documentation

For module-specific dev commands, conventions, and patterns:

| Module | CLAUDE.md | README |
|--------|-----------|--------|
| Backend | [`backend/CLAUDE.md`](./backend/CLAUDE.md) | [`backend/README.md`](./backend/README.md) |
| Frontend (main) | [`frontend/apps/main/CLAUDE.md`](./frontend/apps/main/CLAUDE.md) | [`frontend/README.md`](./frontend/README.md) |
| Frontend (child) | [`frontend/apps/child/CLAUDE.md`](./frontend/apps/child/CLAUDE.md) | — |
| Agent | [`agent/CLAUDE.md`](./agent/CLAUDE.md) | [`agent/README.md`](./agent/README.md) |
| Site | [`site/CLAUDE.md`](./site/CLAUDE.md) | — |

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

