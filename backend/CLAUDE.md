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
