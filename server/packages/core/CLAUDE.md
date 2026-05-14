# core/CLAUDE.md

Module-specific guidance for the shared configuration and logging package.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `server/`:

```bash
uv run ruff check packages/core/        # lint
uv run ruff check packages/core/ --fix  # lint + auto-fix
uv run ruff format packages/core/       # format (only files you touch)
uv run mypy packages/core/ --explicit-package-bases  # type check
uv run pytest packages/core/ -v         # run tests
```

## Tooling

- **uv:** package manager. Use `uv add`/`uv remove`. Never `pip install`.
- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`.
- **mypy:** type checker. Requires `--explicit-package-bases` to avoid namespace collision with other `packages/` directories.
- **pydantic-settings:** `Settings` loads from environment variables automatically. No manual parsing needed.

## Key Invariants

1. **Import direction** — `packages/core` must never import from `apps/`. Dependency flow is one-way: `apps/` → `packages/`. Violating this creates circular imports.
2. **`settings` is a singleton** — always import the pre-built instance: `from packages.core.settings import settings`. Never instantiate `Settings()` directly — it re-reads the environment and breaks singleton guarantees.
3. **`get_logger(__name__)` is the only approved logger** — never call `logging.getLogger()` directly. `get_logger` applies the project's log format, level, and rotation configuration.

## Don't Do

- **Don't import from `apps/`** — import direction rule: `packages/` must not import sibling `apps/`. Use other `packages/` for shared logic.
- **Don't instantiate `Settings()`** — import `settings` (the singleton instance), not the class.
- **Don't call `logging.getLogger()`** — use `get_logger(__name__)` instead.
- **Don't run commands from the package directory** — quality commands must be invoked from `server/`, not from `packages/core/`.

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, exports table
