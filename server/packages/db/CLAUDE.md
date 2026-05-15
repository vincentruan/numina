# db/CLAUDE.md

Module-specific guidance for the shared database session, ORM base, and models package.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `server/`:

```bash
uv run ruff check packages/db/        # lint
uv run ruff check packages/db/ --fix  # lint + auto-fix
uv run ruff format packages/db/       # format (only files you touch)
uv run mypy packages/db/ --explicit-package-bases  # type check
uv run pytest packages/db/ -v         # run tests
```

## Tooling

- **uv:** package manager. Use `uv add`/`uv remove`. Never `pip install`.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`.
- **mypy:** type checker. Requires `--explicit-package-bases` to avoid namespace collision with other `packages/` directories.
- **SQLAlchemy 2.x:** uses `DeclarativeBase` for the ORM base class. All models inherit from `Base` defined in `session.py`.

## Key Invariants

1. **Import direction** — `packages/db` must never import from `apps/`. Dependency flow is one-way: `apps/` → `packages/`. Violating this creates circular imports.
2. **`SessionLocal` is the only approved session factory** — never create a new `sessionmaker()` anywhere else in the codebase. All session creation goes through `SessionLocal` from this package.
3. **`Base` is the only approved ORM base class** — all models must inherit from `packages.db.session.Base`. Never subclass `DeclarativeBase` directly in an app or another package.
4. **Always close sessions in a `finally` block** — every `db = SessionLocal()` call must be paired with `db.close()` in a `finally` block, or use a context manager. Never leave a session open outside a `finally` block.

## Don't Do

- **Don't import from `apps/`** — import direction rule: `packages/` must not import sibling `apps/`. Use other `packages/` for shared logic.
- **Don't create a new `sessionmaker()`** — use `SessionLocal` from this package.
- **Don't subclass a different ORM base** — all models must inherit from `Base`.
- **Don't leave sessions open** — always close in a `finally` block or use a context manager.
- **Don't run commands from the package directory** — quality commands must be invoked from `server/`, not from `packages/db/`.

## Patterns

### Session lifecycle

```python
# ✅ Correct — always close in finally
db = SessionLocal()
try:
    result = db.query(MyModel).all()
    db.commit()
finally:
    db.close()
```

### Model definition

```python
from packages.db.session import Base

class MyModel(Base):
    __tablename__ = "my_table"
    id: Mapped[int] = mapped_column(primary_key=True)
```

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, exports table
