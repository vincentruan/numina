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

### FastAPI `redirect_slashes` and HTTPS Mixed Content

FastAPI defaults to `redirect_slashes=True`, which redirects `/api/v1/assets` → `/api/v1/assets/` with a 307. In HTTPS deployments behind nginx, nginx forwards requests to FastAPI over plain HTTP internally. FastAPI then issues a `Location: http://...` redirect, which the browser blocks as Mixed Content.

**Fix:** Set `redirect_slashes=False` in `app/main.py`:
```python
app = FastAPI(..., redirect_slashes=False)
```

**Also required:** All router root-path decorators must use `""` instead of `"/"`:
```python
# ✅ Correct
@router.get("")
@router.post("")

# ❌ Causes 307 redirect → Mixed Content in HTTPS
@router.get("/")
@router.post("/")
```

This applies to every router file that has root-path endpoints (assets, liabilities, tags, wishes, family, etc.).

## Cross-Cutting Conventions

These apply to all modules. Module-specific conventions live in each module's `CLAUDE.md`.

- **UI text in Chinese** — all user-facing messages (toasts, dialogs, labels) must be in Chinese. Frontend owns the emoji convention — see `frontend/CLAUDE.md`.
- **Error messages in Chinese** — backend HTTP exceptions use Chinese detail strings: `raise HTTPException(status_code=404, detail="资产不存在")`
- **Incremental formatting** — format only files you touch. Do not run formatters on entire modules in a single commit.
- **No speculative code** — don't add features, abstractions, or error handling beyond what was asked.
- **Python: Pydantic v2 only** — use `ConfigDict`, `model_validate`, `field_validator`. Never v1 style (`class Config`, `parse_obj`, `validator`).

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

