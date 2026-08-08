# core/CLAUDE.md

Module-specific guidance for the shared configuration and logging package.
See root [`CLAUDE.md`](../../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Key Invariants

1. **Import direction** — `packages/core` must never import from `apps/`. Dependency flow is one-way: `apps/` → `packages/`. Violating this creates circular imports.
2. **`settings` is a singleton** — always import the pre-built instance: `from packages.core.settings import settings`. Never instantiate `Settings()` directly — it re-reads the environment and breaks singleton guarantees.
3. **`get_logger(__name__)` is the only approved logger** — never call `logging.getLogger()` directly. `get_logger` applies the project's log format, level, and rotation configuration.

## Don't Do

- **Don't instantiate `Settings()`** — import `settings` (the singleton instance), not the class.
- **Don't call `logging.getLogger()`** — use `get_logger(__name__)` instead.

## Modules

| Module | Exports | Purpose |
|--------|---------|---------|
| `settings.py` | `settings` (singleton), `Settings` (class) | Loads env vars via pydantic-settings |
| `logging.py` | `get_logger(__name__)`, `setup_logging()` | Project-wide logger factory + format/rotation |
| `snowflake.py` | `generate_id()` | Snowflake ID generator (used for primary keys) |
| `path_manager.py` | `PathManager` | Resolves paths for data/, logs/, config/ across containers |
| `model_entry.py` | `ModelEntry`, `MODEL_REGISTRY` | LLM model catalogue (provider × model_id × pricing) |
| `effective_config.py` | helpers | Merge layered config (defaults + env + per-family overrides) |

## Patterns

### Settings singleton import

```python
# ✅ Correct — import the pre-built singleton
from packages.core.settings import settings

# ❌ Wrong — re-reads environment, breaks singleton guarantee
from packages.core.settings import Settings
settings = Settings()
```

### Logger

```python
from packages.core.logging import get_logger
logger = get_logger(__name__)
```

## Links

- Root [`CLAUDE.md`](../../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — purpose statement, exports table
