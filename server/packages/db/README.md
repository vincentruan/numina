# packages/db

SQLAlchemy engine, session factory, ORM base class, and all shared database models for the Numina server monorepo. Both `apps/backend` and `apps/scheduler_worker` import `SessionLocal`, `Base`, and `get_db` from here — never create a separate session factory or ORM base in an app.

## Exports

| Symbol | Type | Description |
|--------|------|-------------|
| `SessionLocal` | session factory | The only approved SQLAlchemy session factory — use this everywhere |
| `Base` | class | ORM declarative base — all models must inherit from this |
| `get_db` | function | FastAPI dependency that yields a `Session` and closes it on exit |
| `engine` | instance | SQLAlchemy engine bound to `settings.DATABASE_URL` |
| `models/` | subpackage | All ORM model classes (one file per domain entity) |
