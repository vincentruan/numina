# README Restructuring Design

**Date:** 2026-04-23  
**Status:** Approved  
**Approach:** Surgical deduplication (Option A)

## Problem

Current README structure has overlaps and inconsistencies:

1. **Agent API endpoints** listed in both root `README.md` and `agent/README.md`
2. **Agent architecture** appears in both files with different levels of detail
3. **Backend has no module README** — only root README covers backend dev
4. **Frontend README is a stub** — just 14 lines pointing to root
5. **Root README is comprehensive but mixes external user content with contributor details**

The stated goal: **module READMEs should be fully self-contained for developers working only in that module**, while root README serves external users/deployers.

## Design Principles

1. **Root README = external audience** — deployers, evaluators, users who want to understand what Numina is and how to run it
2. **Module READMEs = contributor audience** — developers who clone/open a subdirectory and need to work in that module
3. **Self-contained modules** — each module README has everything needed: quick start, env vars, API reference, architecture, testing
4. **Minimal duplication** — operational details (dev commands, API endpoints, architecture diagrams) live in one place
5. **Acceptable duplication** — orientation info (tech stack, project description) can appear in multiple places

## Proposed Structure

### `README.md` (root) — ~200 lines

**Audience:** External users, deployers, project evaluators

**Keeps:**
- Project intro + badges
- Core features list (实物资产、金融资产、负债管理、多用户家庭、数据可视化、儿童星星币系统)
- Tech stack table (one-liner per layer: frontend, backend, agent, database, auth, deployment)
- Docker quick start + environment variables
- Project structure tree (top-level only: `backend/`, `agent/`, `frontend/`, `tests/`, `docs/`)
- **Module README links section** — explicit links to `backend/README.md`, `agent/README.md`, `frontend/README.md`, `tests/README.md`
- Links to `docs/` documents (ARCHITECTURE.md, DATA_MODELS.md, API_SPEC.md, etc.)
- Roadmap (MVP, Phase 2-5)
- Contributing guide
- License + credits

**Removes:**
- Detailed backend/frontend/agent dev commands → delegate to module READMEs
- Agent API endpoint table → already in `agent/README.md`
- Main API endpoint listing (`/api/v1/...`) → move to `backend/README.md`
- Detailed architecture diagrams → module READMEs own these

**New section to add:**
```markdown
## 📚 Module Documentation

For contributors working on specific modules:

- [Backend (FastAPI)](./backend/README.md) — API development, database, testing
- [Agent (AI microservice)](./agent/README.md) — DeerFlow integration, skills, policy guard
- [Frontend (Vue 3)](./frontend/README.md) — UI development, components, testing
- [Tests](./tests/README.md) — E2E tests, data seeding, screenshots
```

---

### `backend/README.md` — new file, ~120 lines

**Audience:** Backend contributors

**Sections:**

1. **Header** — one-line description + link to root README
   ```markdown
   # Numina Backend
   
   FastAPI + SQLAlchemy + SQLite backend for Numina family asset management.
   See the root [README.md](../README.md) for project overview.
   ```

2. **Quick Start**
   ```bash
   cd backend
   uv sync
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   uv run pytest tests/ -v
   ```

3. **Environment Variables** — table with all backend env vars (SECRET_KEY, DATABASE_URL, CORS_ORIGINS, token expiry, etc.)

4. **Architecture Overview** — the `backend/app/` tree from CLAUDE.md:
   ```
   backend/app/
   ├── auth/           # JWT token generation, validation
   ├── models/         # SQLAlchemy ORM models
   ├── routers/        # FastAPI route handlers
   ├── schemas/        # Pydantic request/response schemas
   ├── services/       # Business logic
   ├── seed/           # Database seeding
   ├── config.py       # Settings management
   ├── database.py     # SQLAlchemy engine, session
   └── main.py         # FastAPI app initialization
   ```

5. **API Endpoints** — the main `/api/v1/...` listing currently in root README (auth, assets, liabilities, dashboard, family)

6. **Testing**
   ```bash
   # All tests (473 passing)
   uv run pytest tests/ -v
   
   # Single test file
   uv run pytest tests/test_assets.py -v
   
   # Coverage report
   uv run pytest tests/ --cov=app --cov-report=html
   ```
   
   Brief breakdown: `tests/test_auth.py` (10 tests), `tests/test_assets.py` (11 tests), etc.

7. **Database Configuration** — SQLite/MySQL/PostgreSQL support, DATABASE_URL formats, Docker profiles, migration commands:
   ```bash
   uv run alembic revision --autogenerate -m "description"
   uv run alembic upgrade head
   ```

8. **Code Style** — brief (imports order, type annotations, error messages in Chinese), link to root `CLAUDE.md` for full conventions

---

### `agent/README.md` — minor trim, mostly unchanged

**Current state:** Already well-structured (126 lines). Self-contained with architecture, quick start, env vars, API endpoints, output contract, skills, security, testing.

**Changes:**
- **Optional:** Remove "回滚" section (operational concern, not contributor docs) — or keep it, it's only 6 lines
- **Verify:** Env vars table is complete (currently only 4 vars: AGENT_INTERNAL_TOKEN, BACKEND_BASE_URL, USE_DEERFLOW, DEERFLOW_CONFIG_ENV)
- No structural changes needed

---

### `frontend/README.md` — expand from 14 lines to ~80 lines

**Current state:** Stub that just points to root README.

**New structure:**

1. **Header** — one-line description + link to root README
   ```markdown
   # Numina Frontend
   
   Vue 3 + TypeScript + Vite + Vant 4 + ECharts mobile-first UI.
   See the root [README.md](../README.md) for project overview.
   ```

2. **Quick Start**
   ```bash
   cd frontend
   npm ci
   npm run dev     # Dev server (proxies /api to localhost:8000)
   npm run build   # Production build
   ```

3. **Quality Commands**
   ```bash
   npm run lint          # ESLint check
   npm run lint:fix      # ESLint auto-fix
   npm run format        # Prettier format
   npm run typecheck     # vue-tsc --noEmit
   npm run test:run      # vitest run (no watch)
   ```

4. **Key Conventions**
   - Vant components are auto-imported (no manual imports needed)
   - Path alias `@/` maps to `src/`
   - `<script setup lang="ts">` only — no Options API
   - No `as any`, `@ts-ignore`, or `@ts-expect-error`
   - Emoji convention for user-facing messages (see CLAUDE.md)

5. **Component Structure** — brief overview:
   ```
   frontend/src/
   ├── api/            # Axios HTTP client with JWT auto-refresh
   ├── stores/         # Pinia state management
   ├── pages/          # Route-level page components
   ├── components/     # Reusable components
   ├── router/         # Vue Router with auth guards
   ├── types/          # TypeScript interfaces
   └── utils/          # storage, format helpers
   ```

6. **Detailed Conventions** — link to `frontend/CLAUDE.md` for full style guide, emoji rules, tooling config

---

### `tests/README.md` — no changes

**Current state:** Already well-structured (113 lines) and self-contained. Covers test structure, unified test account, usage, coverage, maintenance.

**Action:** Keep as-is.

---

## Migration Plan

1. **Create `backend/README.md`** — extract content from root README + CLAUDE.md
2. **Expand `frontend/README.md`** — add quick start, quality commands, conventions
3. **Trim root `README.md`** — remove module-specific details, add "Module Documentation" section with links
4. **Optional: trim `agent/README.md`** — remove "回滚" section if desired
5. **Commit** — single commit with message: `docs: restructure READMEs for self-contained modules`

## Success Criteria

- A contributor can clone `backend/` and have everything they need in `backend/README.md`
- A contributor can clone `frontend/` and have everything they need in `frontend/README.md`
- An external user can read root `README.md` and understand what Numina is, how to deploy it, and where to find module docs
- No operational details (dev commands, API endpoints, architecture diagrams) are duplicated across root and module READMEs
- Orientation info (tech stack, project description) can appear in multiple places — this is acceptable

## Non-Goals

- Rewriting existing content — we're restructuring, not rewriting
- Changing documentation in `docs/` folder — those files stay as-is
- Updating CLAUDE.md files — those are separate from READMEs

## Open Questions

None — design approved.
