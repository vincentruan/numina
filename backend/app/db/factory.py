# Re-export shim — engine factory moved to packages/db/engine.py
# create_backend / get_session_factory remain here for backend-internal use.
from sqlalchemy import Engine
from sqlalchemy.engine.url import make_url

from app.db.backend import DatabaseBackend
from app.db.postgres import PostgreSQLBackend
from app.db.sqlite import SQLiteBackend
from packages.db.engine import get_engine  # noqa: F401

BACKEND_MAP: dict[str, type[DatabaseBackend]] = {
    "sqlite": SQLiteBackend,
    "postgresql": PostgreSQLBackend,
    "postgresql+psycopg2": PostgreSQLBackend,
    "postgresql+psycopg": PostgreSQLBackend,
}


def create_backend(url: str) -> DatabaseBackend:
    parsed = make_url(url)
    dialect = parsed.drivername
    if dialect in BACKEND_MAP:
        return BACKEND_MAP[dialect]()
    base_dialect = dialect.split("+")[0] if "+" in dialect else dialect
    if base_dialect not in BACKEND_MAP:
        supported = ", ".join(BACKEND_MAP.keys())
        raise ValueError(f"不支持的数据库类型: {dialect}。支持的类型: {supported}")
    return BACKEND_MAP[base_dialect]()


def get_session_factory(url: str):
    backend = create_backend(url)
    engine: Engine = backend.create_engine(url)
    return backend.create_session_factory(engine)