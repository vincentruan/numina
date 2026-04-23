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
Common pitfalls:**
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
