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
- Backend: FastAPI + SQLAlchemy + SQLite + JWT authentication (bcrypt + access/refresh tokens)
- Frontend: Vue 3 + TypeScript + Vite + Vant 4 (mobile UI) + ECharts (charts)
- Infrastructure: Docker Compose + Nginx reverse proxy

## Development Commands

### Backend Development

```bash
cd backend

# Install dependencies (requires uv: https://docs.astral.sh/uv/)
uv sync

# Run development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests (36 tests covering auth, assets, liabilities, dashboard)
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_assets.py -v

# Run a single test function
uv run pytest tests/test_assets.py::test_create_physical_asset -v

# Run tests matching keyword
uv run pytest tests/ -v -k "daily_cost"

# Run tests with coverage
uv run pytest tests/ --cov=app --cov-report=html

# Create new Alembic migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Add a new dependency
uv add <package>

# Add a dev-only dependency
uv add --group dev <package>
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm ci

# Run development server (proxies /api to localhost:8000)
npm run dev

# Build for production
npm run build

# Type-check only (no build output)
npx vue-tsc -b --noEmit

# Preview production build
npm run preview
```

### Docker Development

```bash
# Start all services (backend, frontend, nginx)
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up -d --build

# Stop all services
docker-compose down

# Access application at http://localhost:8080
```

**Environment Variables:**
- `PORT`: Nginx port (default: 8080)
- `SECRET_KEY`: JWT signing key (default: auto-generated, **must set in production**)
- `DATABASE_URL`: Database connection string (default: sqlite:////app/data/numina.db)
- `CORS_ORIGINS`: Allowed CORS origins (default: ["*"])
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT access token lifetime (default: 15)
- `REFRESH_TOKEN_EXPIRE_DAYS`: JWT refresh token lifetime (default: 7)

### Database Configuration

Numina supports multiple database backends: **SQLite (default)**, **MySQL**, and **PostgreSQL**.

**DATABASE_URL formats:**

```
# SQLite (default)
sqlite:///./data/numina.db            # Local development
sqlite:////app/data/numina.db         # Docker

# MySQL
mysql+pymysql://user:password@host:3306/database

# PostgreSQL
postgresql+psycopg2://user:password@host:5432/database
```

**Docker with MySQL/PostgreSQL:**

```bash
# Default SQLite (no extra config)
docker-compose up -d

# Use MySQL (starts MySQL container)
docker-compose --profile mysql up -d
# Set DATABASE_URL=mysql+pymysql://numina:numinapass@mysql:3306/numina

# Use PostgreSQL (starts PostgreSQL container)
docker-compose --profile postgres up -d
# Set DATABASE_URL=postgresql+psycopg2://numina:numinapass@postgres:5432/numina
```

**MySQL/PostgreSQL default credentials (Docker):**
- Database: `numina`
- User: `numina`
- Password: `numinapass`

**Database backend architecture:**
- `backend/app/db/` — Abstract backend factory pattern
- `factory.py` — URL parsing and backend selection
- `sqlite.py`, `mysql.py`, `postgres.py` — Backend implementations with connection pool configs

**Integration tests (require Docker):**
```bash
cd backend
uv run pytest tests/integration/ -v -m integration
```

## Architecture

### Backend Structure

```
backend/app/
├── auth/           # JWT token generation, validation, get_current_user dependency
├── models/         # SQLAlchemy ORM models
│   ├── user.py         # User (family_id, username, display_name, role, avatar_color)
│   ├── family.py       # Family (name, invite_code, created_by)
│   ├── asset.py        # Asset (physical + financial, with daily cost fields)
│   ├── liability.py    # Liability (mortgage, car_loan, credit_card, personal_loan)
│   ├── category.py     # Category (system + custom, physical/financial types)
│   ├── tag.py          # Tag (many-to-many with assets via asset_tags)
│   └── snapshot.py     # AssetSnapshot (daily net worth snapshots for trend charts)
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
├── seed/           # Database seeding (21 system categories: 13 physical + 8 financial)
├── config.py       # Settings management (Pydantic BaseSettings, reads .env)
├── database.py     # SQLAlchemy engine, session factory, Base class
└── main.py         # FastAPI app initialization, CORS, lifespan, router registration
```

### Frontend Structure

```
frontend/src/
├── api/            # Axios HTTP client with JWT auto-refresh interceptor
│   ├── index.ts        # Axios instance, request/response interceptors, token refresh with lock
│   ├── auth.ts         # login, register, joinFamily, getMe, refreshToken
│   ├── assets.ts       # CRUD + updateAssetValue
│   ├── liabilities.ts  # CRUD + recordPayment
│   ├── categories.ts   # CRUD
│   ├── tags.ts         # CRUD
│   ├── dashboard.ts    # overview, allocation, trend, topAssets, dailyCost, lowUsage, returns
│   └── family.ts       # getFamily, getMembers, regenerateInviteCode, updateRole, removeMember
├── stores/         # Pinia state management (one store per domain)
├── pages/          # Route-level page components
│   ├── DashboardPage.vue       # Main dashboard with charts and analytics
│   ├── AssetListPage.vue       # Asset list with filtering/sorting
│   ├── AssetDetailPage.vue     # Asset detail with daily cost, return rate
│   ├── AssetFormPage.vue       # Create/edit asset (dynamic fields by type)
│   ├── LiabilityListPage.vue   # Liability list with active/inactive tabs
│   ├── LiabilityDetailPage.vue # Liability detail with payment progress bar + payment dialog
│   ├── LiabilityFormPage.vue   # Create/edit liability
│   ├── FamilyPage.vue          # Family overview
│   ├── LoginPage.vue / RegisterPage.vue / JoinFamilyPage.vue
│   └── SettingsPage.vue / CategoryManagePage.vue / TagManagePage.vue
├── components/     # Reusable components
│   ├── charts/         # TrendLineChart, AllocationPieChart (ECharts wrappers)
│   ├── common/         # AppTabBar, PageHeader, MoneyDisplay, EmptyState
│   ├── asset/          # AssetCard, AssetForm
│   ├── liability/      # LiabilityCard, LiabilityForm
│   └── family/         # MemberCard
├── composables/    # Vue composables (useAuth, useCurrency)
├── layouts/        # MainLayout (bottom tab bar with 5 tabs)
├── router/         # Vue Router with auth guards (requireAuth, requireGuest)
├── types/          # TypeScript interfaces matching backend schemas
└── utils/          # storage (token + refreshToken + user), format (currency, date)
```

### Key Patterns

- **Database initialization**: `Base.metadata.create_all()` runs on app startup via lifespan context manager
- **Category seeding**: 21 system categories auto-seeded on startup via `seed_categories()`
- **Authentication**: JWT Bearer tokens (15-min access, 7-day refresh) via `get_current_user` dependency
- **Token refresh**: Frontend interceptor auto-refreshes expired access tokens using refresh token, with concurrent request queuing via lock mechanism
- **Family scoping**: All assets/liabilities are family-scoped; users join families via 6-digit invite codes
- **API prefix**: All routes use `/api/v1` prefix
- **Asset types**: Single `assets` table with `asset_type` discriminator ('physical' / 'financial') and type-specific fields
- **Daily cost calculation**: `(purchase_price + annual_maintenance_cost * years) / days_used` — computed in router response, not stored
- **Return rate calculation**: `(current_value - purchase_price) / purchase_price * 100` — computed for financial assets
- **Liability payment**: `PUT /liabilities/{id}/payment` reduces `remaining_amount`; auto-sets `is_active=False` when fully paid
- **Dashboard aggregation**: All dashboard endpoints aggregate data at the family level using the current user's `family_id`

### Data Model Key Relationships

```
Family 1──N User
Family 1──N Category (custom; system categories have family_id=NULL)
Family 1──N AssetSnapshot

User 1──N Asset
User 1──N Liability

Asset N──1 Category
Asset N──M Tag (via asset_tags join table)
Liability N──1 Asset (optional linked_asset_id)
```

### Asset Enhanced Fields (for smart analytics)

- `expected_lifespan_days` (INTEGER): Expected useful life in days, for daily cost calculation
- `annual_maintenance_cost` (FLOAT): Annual maintenance cost (insurance, repairs), included in daily cost
- `usage_frequency` (TEXT): 'daily' / 'weekly' / 'monthly' / 'rarely' / 'idle' — for low-usage detection

### Predefined Categories (21 total)

**Physical (13):** 🏠房产, 🚗车辆, 📱数码, 📺家电, 🛋️家具, 💎珠宝, 👔服饰, 💄美妆, ⚽运动, 🎮玩具, 🐾宠物, 🎸乐器, 👜箱包

**Financial (8):** 🏦存款, 📊基金, 📈股票, 📜债券, 🛡️保险, 💰理财产品, ₿数字货币, 💳其他金融

### Documented Solutions

`docs/solutions/` — documented solutions to past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas.

Key categories:
- `best-practices/` — security hardening, coding patterns, architectural decisions
- `security-issues/` — vulnerability fixes and security patterns

## Testing

### Backend Unit Tests

Backend tests are in `backend/tests/` using pytest + FastAPI TestClient with in-memory SQLite.

```
backend/tests/
├── conftest.py          # Fixtures: db, client, auth_headers, second_user_headers
├── test_auth.py         # 10 tests: register, login, refresh, join-family, me, isolation
├── test_assets.py       # 11 tests: CRUD, daily cost, return rate, cross-family isolation
├── test_liabilities.py  # 8 tests: CRUD, payment, full payoff, cross-family isolation
└── test_dashboard.py    # 7 tests: overview, allocation, trend, top-assets, daily-cost, low-usage, returns
```

**Total: 36 tests, all passing.**

Key test patterns:
- Each test gets a fresh in-memory SQLite database (fixture scope: function)
- `auth_headers` fixture registers a user and returns JWT headers
- `second_user_headers` fixture creates a user in a different family for isolation tests
- System categories are seeded via `seed_categories()` in the db fixture

### E2E and Integration Tests

E2E and integration test scripts are in `tests/` (project root):

```
tests/
├── seed-complete-data.sh        # 完整测试数据生成（19项实物资产 + 11项金融资产 + 负债 + 心愿）
├── test-wishes-liabilities.sh   # 心愿和负债仿真测试（全字段验证 + 列表展示 + 功能测试）
├── create-test-data.sh          # 旧版测试数据脚本（已被 seed-complete-data.sh 替代）
├── e2e-acceptance.sh            # Basic acceptance tests (auth, CRUD operations)
├── e2e-extended.sh              # Extended E2E tests (full user flows)
├── screenshot.js                # Puppeteer screenshot capture (legacy)
├── take-screenshots.js          # Optimized screenshot capture with per-page isolation
└── TEST_DATA_SUMMARY.md         # 测试数据总结文档
```

**Running E2E tests:**

```bash
# Prerequisites: Docker services running (docker-compose up -d)

# 生成完整测试数据（推荐）
./tests/seed-complete-data.sh

# 运行心愿和负债仿真测试
./tests/test-wishes-liabilities.sh

# Run acceptance tests
./tests/e2e-acceptance.sh

# Run extended E2E tests
./tests/e2e-extended.sh

# Capture UI screenshots (requires Node.js + puppeteer)
cd tests && node take-screenshots.js
```

**Test Data Summary:**
- 实物资产: 19 项（覆盖所有 13 个分类）
- 金融资产: 11 项（覆盖所有 8 个分类）
- 负债: 3 项基础数据
- 心愿: 5 项基础数据
- 总资产价值: ¥50,792,000
- 总负债: ¥5,480,000
- 净资产: ¥45,312,000

**Test Organization Convention:**
- All simulation, E2E, integration, and UI testing scripts go in `tests/` folder
- Backend unit tests stay in `backend/tests/`
- Frontend unit tests (if added) should go in `frontend/tests/`

## Common Pitfalls

- **Auth endpoints return 200**, not 201 (register, login, join-family all return `TokenResponse` with status 200)
- **Asset/Liability POST endpoints return 201** (explicit `status_code=201` on router decorators)
- **Dashboard allocation** returns `{ items: [...], total: float }`, not a flat list
- **Dashboard trend** returns `{ points: [...] }`, not a flat list
- **InvestmentReturnItem** does not include `asset_type` field — only financial assets are returned
- **TokenResponse** does not include `user` — frontend should call `/auth/me` after login to get user info
- **SQLite file path**: In Docker, the database is at `/app/data/numina.db`; locally at `./data/numina.db`
- **Vite proxy**: Frontend dev server proxies `/api` to `http://localhost:8000` (configured in `vite.config.ts`)

## Code Style

### Backend (Python)

- Imports: stdlib → third-party → local (`app.*`), blank line between groups.
- Use `from app.models.user import User` (explicit per-model), not `from app.models import *`.
- Model imports in `main.py` use `# noqa: F401` for side-effect-only imports.
- Files: `snake_case.py`. Classes: `PascalCase`. Functions: `snake_case`.
- Route prefixes: `router = APIRouter(prefix="/assets", tags=["assets"])`.
- Private helpers: `_to_response(asset)` (leading underscore).
- Type annotations: `str | None`, `list[str]` (3.10+ syntax, not `Optional`/`List`).
- SQLAlchemy: `Mapped[type]` + `mapped_column(...)`. Pydantic: `BaseModel` + `model_config = {"from_attributes": True}`.
- Error messages in Chinese: `raise HTTPException(status_code=404, detail="资产不存在")`.

### Frontend (TypeScript / Vue 3)

- Imports: third-party first, then `@/` aliases. Use `import type { X }` for type-only.
- Vant components are auto-imported — no manual imports needed.
- Files: `PascalCase.vue` for pages/components, `camelCase.ts` for modules.
- Pages: `*Page.vue`. Components: `components/{domain}/`. Composables: `use*.ts`. Stores: `use*Store`.
- Strict mode enabled. Interfaces in `src/types/index.ts` with `snake_case` fields.
- String literal unions for enums: `'physical' | 'financial'`. Optional fields: `?:` syntax.
- `<script setup lang="ts">` only (Composition API, no Options API).

## Conventions

- **Documented solutions**: `docs/solutions/` contains documented solutions to past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (`module`, `tags`, `problem_type`). Relevant when implementing or debugging in documented areas.
- UI text and error messages are in Chinese (简体中文). Currency defaults to CNY.
- **Linting/formatting:** Each module has its own tooling — see module-level `CLAUDE.md` for commands.
  - Frontend: ESLint (`npm run lint`) + Prettier (`npm run format`) + vue-tsc (`npm run typecheck`)
  - Backend: ruff (`uv run ruff check .` / `uv run ruff format .`) + mypy (`uv run mypy app/`)
  - Agent: ruff (`uv run ruff check .` / `uv run ruff format .`) + mypy (`uv run mypy . --exclude vendor`)
  - Incremental formatting: format only files you touch — do not reformat entire modules in one commit.
- No `as any`, `@ts-ignore`, or `@ts-expect-error` — fix types properly.
- Minimal changes: fix what's asked, don't refactor unrelated code.
- Always run `uv run pytest tests/ -v` (from `backend/`) after backend changes.
- Always run `npm run build` (from `frontend/`) after frontend changes to verify types.
- DO NOT run dev servers (`uvicorn`, `npm run dev`) from automated agents — they are long-running processes.

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
