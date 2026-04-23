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

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
