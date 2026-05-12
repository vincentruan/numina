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

- **uv:** package manager. Use `uv add`/`uv remove` to manage dependencies. Never use `pip install` directly.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I (imports), UP (pyupgrade).
- **mypy:** type checker. Config in `pyproject.toml` under `[tool.mypy]`. Starts lenient (`ignore_missing_imports = true`) — ratchet strictness over time by adding `disallow_untyped_defs = true` per module.
- **pytest:** test runner. Tests in `backend/tests/`. Each test gets a fresh in-memory SQLite DB.

## Cache Backend

Controlled by `CACHE_BACKEND` env var (default: `"memory"`). Set to `"redis"` to enable Redis. When using Redis, also set `REDIS_URL` (e.g. `redis://localhost:6379/0`). The in-memory backend is suitable for single-instance dev; Redis is required for multi-worker or multi-instance deployments.

## Key Invariants

- **Always run `alembic upgrade head` before starting the app on an existing database.** `Base.metadata.create_all()` only creates tables for fresh installs — it does not apply migrations. Skipping causes `OperationalError: no such column` on endpoints that read newly added columns.
- **Pydantic v2 only** — use `ConfigDict`, `model_validate`, `field_validator`. Never v1 style (`class Config`, `parse_obj`, `validator`).

## Snowflake ID Serialization

All response schemas containing IDs inherit from `SnowflakeBase` (app/schemas/base.py).

### Pattern

```python
from app.schemas.base import SnowflakeBase

class MyResponse(SnowflakeBase):
    id: int  # Define as int (matches DB)
    family_id: int
    other_id: int
    name: str
```

JSON output automatically converts IDs to strings:
```json
{"id": "123456789012345", "family_id": "987654321098765"}
```

### Key Points

- Schemas define IDs as `int` (internal representation matches SQLAlchemy)
- SnowflakeBase.model_serializer converts to `str` during JSON serialization
- No manual `str()` calls in routers — return int values directly
- Request schemas (Create/Update) don't need SnowflakeBase — input comes as string

### Common Pitfalls

1. **Don't use plain BaseModel for schemas with IDs** → Use SnowflakeBase
2. **Don't manually define `id: str`** → Define `id: int`, let serializer convert
3. **Don't add field_validator for ID coercion** → SnowflakeBase handles it
4. **Don't call str() in routers** → Return int, schema serializes
5. **Request schemas don't need SnowflakeBase** → Input validation handles string→int

### Why

JavaScript loses precision for integers > 2^53. Snowflake IDs are 18-19 digits.
Serializing as strings preserves exact values across the API boundary.

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

21 system categories seeded on startup (read-only, `is_system=True`). See `app/seed/categories.py` and `app/constants/categories.py` for the full list.

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
