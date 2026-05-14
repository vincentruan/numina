# packages/core

Shared configuration and logging utilities for the Numina server monorepo. Provides a singleton `Settings` instance (loaded from environment variables via pydantic-settings), a structured `get_logger` factory, and a thread-safe Snowflake ID generator. All other packages and apps import from here — never duplicate settings or logging setup elsewhere.

## Exports

| Symbol | Type | Description |
|--------|------|-------------|
| `Settings` | class | Pydantic settings model — all env var definitions live here |
| `settings` | instance | Singleton `Settings` instance — import this, never instantiate `Settings()` directly |
| `get_logger` | function | Returns a configured `logging.Logger` for the given `__name__` |
| `setup_logging` | function | Initializes log handlers, rotation, and level — called once at app startup |
| `next_id` | function | Generates a unique 64-bit Snowflake ID as an `int` |
