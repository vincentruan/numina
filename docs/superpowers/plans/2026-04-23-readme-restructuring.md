# README Restructuring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure README files so module READMEs are fully self-contained for contributors, while the root README serves external users/deployers.

**Architecture:** Root README keeps project overview, features, Docker deployment, roadmap — strips module-specific dev commands and API details. Each module README (`backend/`, `agent/`, `frontend/`) becomes self-contained with quick start, env vars, architecture, API reference, and testing. A new `backend/README.md` is created from scratch.

**Tech Stack:** Markdown only — no code changes.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `README.md` | Modify | Project landing page for external users/deployers |
| `README.en.md` | Modify | English translation — mirror same structural changes as `README.md` |
| `backend/README.md` | Create | Self-contained backend contributor docs |
| `frontend/README.md` | Modify | Expand from stub to self-contained frontend contributor docs |
| `agent/README.md` | No change | Already self-contained |

---

## Task 1: Create `backend/README.md`

**Files:**
- Create: `backend/README.md`

- [ ] **Step 1: Create the file**

```markdown
# Numina Backend

FastAPI + SQLAlchemy backend for Numina family asset management.
See the root [README.md](../README.md) for project overview and Docker deployment.

## Quick Start

```bash
cd backend

# Install dependencies (requires uv: https://docs.astral.sh/uv/)
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
uv run pytest tests/ -v
```

## Quality Commands

```bash
uv run ruff check .          # lint
uv run ruff check . --fix    # lint + auto-fix
uv run ruff format .         # format (only files you touch)
uv run mypy app/             # type check
uv run pytest tests/ -v      # run all tests
uv run pytest tests/ -v -k "keyword"  # run tests matching keyword
uv run pytest tests/ --cov=app --cov-report=html  # coverage report
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | auto-generated | **Required in production.** JWT signing key. |
| `DATABASE_URL` | `sqlite:///./data/numina.db` | Database connection string. |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:8080"]` | Allowed CORS origins. Must be specific domains in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token lifetime. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token lifetime. |
| `ENVIRONMENT` | `development` | Set to `production` to enable production validations. |
| `AGENT_INTERNAL_TOKEN` | `""` | Service-to-service token for backend ↔ agent calls. |
| `AGENT_BASE_URL` | `http://agent:8001` | Agent service internal address. |
| `ALTCHA_HMAC_KEY` | auto-generated | **Required in production.** HMAC key for captcha. |
| `AI_ENCRYPTION_KEY` | `""` | **Required in production.** Fernet key for encrypting AI API keys. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `SNOWFLAKE_MACHINE_ID` | auto-derived | Snowflake ID machine number (0–1023). Set explicitly for multi-instance deployments. |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | `5` | Max failed login attempts before lockout. |
| `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` | `900` | Lockout duration in seconds (15 min). |

## Architecture

```
backend/app/
├── auth/           # JWT token generation, validation, get_current_user dependency
├── models/         # SQLAlchemy ORM models
│   ├── user.py         # User (family_id, username, display_name, role, avatar_color)
│   ├── family.py       # Family (name, invite_code, created_by)
│   ├── asset.py        # Asset (physical + financial, daily cost fields)
│   ├── liability.py    # Liability (mortgage, car_loan, credit_card, personal_loan)
│   ├── category.py     # Category (system + custom, physical/financial types)
│   ├── tag.py          # Tag (many-to-many with assets via asset_tags)
│   └── snapshot.py     # AssetSnapshot (daily net worth snapshots)
├── routers/        # FastAPI route handlers
│   ├── auth.py         # register, login, refresh, join-family, me, update-me
│   ├── assets.py       # CRUD + value update + archive
│   ├── liabilities.py  # CRUD + payment recording
│   ├── categories.py   # CRUD (system categories are read-only)
│   ├── tags.py         # CRUD
│   ├── dashboard.py    # overview, allocation, trend, top-assets, daily-cost, low-usage, returns
│   └── family.py       # info, members, aggregate, invite-code, snapshots
├── schemas/        # Pydantic request/response schemas (one file per domain)
├── services/       # Business logic (auth, asset calculations, dashboard aggregation)
├── seed/           # Database seeding (21 system categories)
├── config.py       # Settings management (Pydantic BaseSettings, reads .env)
├── database.py     # SQLAlchemy engine, session factory, Base class
└── main.py         # FastAPI app initialization, CORS, lifespan, router registration
```

## API Endpoints

All routes use `/api/v1` prefix. Interactive docs at `http://localhost:8000/docs`.

```
# Auth
POST   /api/v1/auth/register          # Register (creates family)
POST   /api/v1/auth/login             # Login
POST   /api/v1/auth/refresh           # Refresh token
POST   /api/v1/auth/family/join       # Join family via invite code
GET    /api/v1/auth/me                # Get current user

# Assets
GET    /api/v1/assets                 # List assets (filterable)
POST   /api/v1/assets                 # Create asset (returns 201)
GET    /api/v1/assets/{id}            # Asset detail
PUT    /api/v1/assets/{id}            # Update asset
DELETE /api/v1/assets/{id}            # Archive asset
PUT    /api/v1/assets/{id}/value      # Quick value update

# Liabilities
GET    /api/v1/liabilities            # List liabilities
POST   /api/v1/liabilities            # Create liability (returns 201)
GET    /api/v1/liabilities/{id}       # Liability detail
PUT    /api/v1/liabilities/{id}       # Update liability
DELETE /api/v1/liabilities/{id}       # Delete liability
PUT    /api/v1/liabilities/{id}/payment  # Record payment

# Dashboard
GET    /api/v1/dashboard/overview              # Total assets, liabilities, net worth
GET    /api/v1/dashboard/allocation            # Asset allocation by category
GET    /api/v1/dashboard/trend                 # Net worth trend over time
GET    /api/v1/dashboard/daily-cost-ranking    # Daily cost ranking
GET    /api/v1/dashboard/low-usage-assets      # Low-usage asset detection
GET    /api/v1/dashboard/investment-returns    # Investment return ranking

# Family
GET    /api/v1/family                 # Family info
GET    /api/v1/family/members         # Member list
GET    /api/v1/family/aggregate       # Family-level asset aggregate
POST   /api/v1/family/invite-code     # Regenerate invite code
GET    /api/v1/family/snapshots       # Net worth snapshot history

# Categories & Tags
GET/POST/PUT/DELETE  /api/v1/categories
GET/POST/PUT/DELETE  /api/v1/tags
```

**Common pitfalls:**
- Auth endpoints return `200`, not `201`
- Asset/Liability POST returns `201`
- `TokenResponse` does not include `user` — call `/auth/me` after login

## Testing

473 tests, all passing. Each test gets a fresh in-memory SQLite database.

```bash
uv run pytest tests/ -v                          # all tests
uv run pytest tests/test_assets.py -v            # single file
uv run pytest tests/test_assets.py::test_create_physical_asset -v  # single test
uv run pytest tests/ -v -k "daily_cost"          # keyword filter
uv run pytest tests/ --cov=app --cov-report=html # coverage
```

Test files:
- `tests/test_auth.py` — 10 tests: register, login, refresh, join-family, me, isolation
- `tests/test_assets.py` — 11 tests: CRUD, daily cost, return rate, cross-family isolation
- `tests/test_liabilities.py` — 8 tests: CRUD, payment, full payoff, cross-family isolation
- `tests/test_dashboard.py` — 7 tests: overview, allocation, trend, top-assets, daily-cost, low-usage, returns

## Database

### Supported Backends

```
# SQLite (default)
sqlite:///./data/numina.db            # local dev
sqlite:////app/data/numina.db         # Docker

# MySQL
mysql+pymysql://user:password@host:3306/database

# PostgreSQL
postgresql+psycopg2://user:password@host:5432/database
```

### Migrations

```bash
# Create a new migration after model changes
uv run alembic revision --autogenerate -m "description"

# Apply all pending migrations
uv run alembic upgrade head
```

> **Important:** Always run `alembic upgrade head` before starting the app on an existing database.
> The app's `Base.metadata.create_all()` only creates tables for fresh installs — it does not apply migrations.
> Skipping this causes `OperationalError: no such column` on endpoints that read newly added columns.

## Code Style

See root [`CLAUDE.md`](../CLAUDE.md) for full conventions. Key points:
- Imports: stdlib → third-party → local (`app.*`), blank line between groups
- Type annotations: `str | None`, `list[str]` (Python 3.10+ syntax)
- Error messages in Chinese: `raise HTTPException(status_code=404, detail="资产不存在")`
- Pydantic v2 style: `ConfigDict`, `model_validate`, `field_validator`
- Format only files you touch — do not reformat the entire module
```

- [ ] **Step 2: Verify the file was created**

```bash
wc -l backend/README.md
```

Expected: ~130 lines

- [ ] **Step 3: Commit**

```bash
git add backend/README.md
git commit -m "docs(backend): add self-contained contributor README"
```

---

## Task 2: Expand `frontend/README.md`

**Files:**
- Modify: `frontend/README.md`

- [ ] **Step 1: Replace the file content**

```markdown
# Numina Frontend

Vue 3 + TypeScript + Vite + Vant 4 + ECharts mobile-first UI.
See the root [README.md](../README.md) for project overview and Docker deployment.

## Quick Start

```bash
cd frontend

npm ci                # Install dependencies
npm run dev           # Dev server (proxies /api to localhost:8000)
npm run build         # Production build (runs vue-tsc + vite build)
npm run preview       # Preview production build locally
```

## Quality Commands

```bash
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run format        # Prettier — format files in src/
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run test:run      # vitest run — run tests once (no watch mode)
```

## Architecture

```
frontend/src/
├── api/            # Axios HTTP client with JWT auto-refresh interceptor
│   ├── index.ts        # Axios instance, request/response interceptors, token refresh with lock
│   ├── auth.ts         # login, register, joinFamily, getMe, refreshToken
│   ├── assets.ts       # CRUD + updateAssetValue
│   ├── liabilities.ts  # CRUD + recordPayment
│   ├── dashboard.ts    # overview, allocation, trend, topAssets, dailyCost, lowUsage, returns
│   └── family.ts       # getFamily, getMembers, regenerateInviteCode, updateRole, removeMember
├── stores/         # Pinia state management (one store per domain)
├── pages/          # Route-level page components (*Page.vue)
├── components/     # Reusable components (charts/, common/, asset/, liability/, family/)
├── composables/    # Vue composables (useAuth, useCurrency)
├── layouts/        # MainLayout (bottom tab bar)
├── router/         # Vue Router with auth guards (requireAuth, requireGuest)
├── types/          # TypeScript interfaces matching backend schemas
└── utils/          # storage (tokens + user), format (currency, date)
```

## Key Conventions

- **Vant components are auto-imported** via `unplugin-vue-components` — do not manually import them
- **Path alias `@/`** maps to `src/` (configured in `vite.config.ts` and `tsconfig.app.json`)
- **`<script setup lang="ts">`** only — no Options API, no `defineComponent`
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly
- **Incremental formatting** — format only files you touch, not the entire `src/`
- **Emoji convention** — all user-facing toast/dialog messages must use emoji-prefixed i18n keys (see `frontend/CLAUDE.md`)

## Detailed Conventions

See [`CLAUDE.md`](./CLAUDE.md) for:
- Full ESLint + Prettier + vue-tsc tooling config
- Emoji convention for user-facing messages with implementation examples
- i18n workflow for adding new messages
```

- [ ] **Step 2: Verify the file**

```bash
wc -l frontend/README.md
```

Expected: ~70 lines

- [ ] **Step 3: Commit**

```bash
git add frontend/README.md
git commit -m "docs(frontend): expand README to self-contained contributor docs"
```

---

## Task 3: Trim root `README.md`

**Files:**
- Modify: `README.md`

This is the largest change. The root README currently has ~424 lines. We remove module-specific dev commands and API details, and add a "Module Documentation" section.

- [ ] **Step 1: Remove the "本地开发" (Local Development) section**

Find and remove the entire section from line ~79 to ~106:

```markdown
### 本地开发

#### 后端开发

```bash
cd backend
...
```

#### 前端开发

```bash
cd frontend
...
```
```

Replace with a single line pointing to module READMEs:

```markdown
### 本地开发

各模块的本地开发说明见对应模块的 README：[后端](./backend/README.md) · [前端](./frontend/README.md) · [Agent](./agent/README.md)
```

- [ ] **Step 2: Remove the "主要 API 端点" (Main API Endpoints) section**

Find and remove the entire section (the large code block listing `/api/v1/auth/register`, `/api/v1/assets`, etc.) and the "Agent API 端点" table below it.

Replace with:

```markdown
## 📝 API 文档

启动后端服务后，访问以下地址查看自动生成的 API 文档：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

完整端点列表见 [backend/README.md](./backend/README.md) 和 [agent/README.md](./agent/README.md)。
```

- [ ] **Step 3: Remove the "🧪 测试" (Testing) section's module-specific commands**

Find the testing section. Keep the summary sentence ("后端包含 473 个自动化测试...") but remove the bash code blocks with `cd backend` / `cd agent` commands.

Replace the bash blocks with:

```markdown
详见各模块 README：[后端测试](./backend/README.md#测试) · [Agent 测试](./agent/README.md#测试) · [E2E 测试](./tests/README.md)
```

- [ ] **Step 4: Add "📚 模块文档" section**

After the "🗂️ 项目结构" section, add:

```markdown
## 📚 模块文档

各模块的开发文档（快速启动、环境变量、架构、测试）：

| 模块 | README | 说明 |
|------|--------|------|
| 后端 | [backend/README.md](./backend/README.md) | FastAPI API 开发、数据库、测试 |
| Agent | [agent/README.md](./agent/README.md) | AI 微服务、DeerFlow 集成、技能 |
| 前端 | [frontend/README.md](./frontend/README.md) | Vue 3 UI 开发、组件、测试 |
| 测试 | [tests/README.md](./tests/README.md) | E2E 测试、数据生成、截图 |
```

- [ ] **Step 5: Verify the root README still makes sense end-to-end**

Read through `README.md` and confirm:
- Project intro, features, tech stack table are intact
- Docker quick start is intact
- Project structure tree is intact
- Roadmap, contributing, license are intact
- No dangling references to removed sections

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(root): trim module-specific details, add module README links"
```

---

## Task 4: Mirror changes in `README.en.md`

**Files:**
- Modify: `README.en.md`

- [ ] **Step 1: Read the English README to understand its current structure**

```bash
wc -l README.en.md
```

- [ ] **Step 2: Apply the same structural changes as Task 3**

Mirror the same three removals and one addition from Task 3, but in English:

1. Replace the "Local Development" section with a one-liner pointing to module READMEs
2. Replace the "Main API Endpoints" section with a pointer to `backend/README.md` and `agent/README.md`
3. Replace the testing bash blocks with links to module READMEs
4. Add a "Module Documentation" table section (in English)

- [ ] **Step 3: Commit**

```bash
git add README.en.md
git commit -m "docs(root): mirror README restructuring in English translation"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|------------|
| Create `backend/README.md` with quick start, env vars, architecture, API endpoints, testing, DB config | Task 1 |
| Expand `frontend/README.md` from stub to self-contained | Task 2 |
| Trim root README: remove module dev commands, API listing, add module links section | Task 3 |
| Mirror root README changes in `README.en.md` | Task 4 |
| `agent/README.md` — no changes needed | ✅ explicitly excluded |
| `tests/README.md` — no changes needed | ✅ explicitly excluded |

**Placeholder scan:** No TBDs, TODOs, or vague steps. All steps include exact content.

**Consistency check:** No cross-task type or naming dependencies — this is pure documentation.
