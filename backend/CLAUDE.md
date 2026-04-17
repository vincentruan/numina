# backend/CLAUDE.md

Module-specific guidance for the Python FastAPI backend.
See root `CLAUDE.md` for architecture, models, router patterns, test fixtures, and style conventions.

## Quality Commands

```bash
uv run ruff check .          # lint — check for errors and warnings
uv run ruff check . --fix    # lint — auto-fix where possible
uv run ruff format .         # format — reformat source files
uv run mypy app/             # type check
uv run pytest tests/ -v      # run all tests
uv run pytest tests/ -v -k "keyword"   # run tests matching keyword
```

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I (imports), UP (pyupgrade).
- **mypy:** type checker. Config in `pyproject.toml` under `[tool.mypy]`. Starts lenient (`ignore_missing_imports = true`) — ratchet strictness over time by adding `disallow_untyped_defs = true` per module.
- **pytest:** test runner. Tests in `backend/tests/`. Each test gets a fresh in-memory SQLite DB.

## Pydantic v2 Patterns

Always use v2 style — never v1 style:

```python
# ✅ v2 — ConfigDict
from pydantic import BaseModel, ConfigDict

class MySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ❌ v1 — class Config (do not use)
class MySchema(BaseModel):
    class Config:
        orm_mode = True
```

```python
# ✅ v2 — model_validate
obj = MySchema.model_validate(orm_instance)

# ❌ v1 — parse_obj (do not use)
obj = MySchema.parse_obj(orm_instance)
```

```python
# ✅ v2 — field_validator
from pydantic import field_validator

class MySchema(BaseModel):
    @field_validator("field_name")
    @classmethod
    def validate_field(cls, v: str) -> str:
        return v.strip()

# ❌ v1 — validator (do not use)
```

## Alembic

```bash
uv run alembic revision --autogenerate -m "description"   # create migration
uv run alembic upgrade head                                # apply migrations
```

> **IMPORTANT — Deployment order:** Always run `uv run alembic upgrade head` **before** starting the app.
> The app calls `Base.metadata.create_all()` on startup which creates tables for fresh installs,
> but it does **not** apply Alembic migrations to existing databases. Skipping this step will cause
> `OperationalError: no such column` on any endpoint that reads newly added columns.

## Incremental Formatting

Format only files you touch. Do not run `uv run ruff format .` on the entire codebase in a single commit — it creates noise in blame history.
