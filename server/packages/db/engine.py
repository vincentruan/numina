"""Database engine factory for multiple backends (SQLite, PostgreSQL)."""

from abc import ABC, abstractmethod
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker


class _DatabaseBackend(ABC):
    @abstractmethod
    def get_connection_args(self) -> dict:
        pass

    @abstractmethod
    def get_pool_config(self) -> dict:
        pass

    def create_engine(self, url: str) -> Engine:
        return create_engine(url, connect_args=self.get_connection_args(), **self.get_pool_config())

    def create_session_factory(self, engine: Engine) -> sessionmaker:
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)


class _SQLiteBackend(_DatabaseBackend):
    def get_connection_args(self) -> dict:
        return {"check_same_thread": False}

    def get_pool_config(self) -> dict:
        return {"pool_pre_ping": True}

    def create_engine(self, url: str) -> Engine:
        # SQLite doesn't auto-create the parent directory. Ensure it exists
        # so first-boot from a freshly mounted empty volume doesn't crash.
        parsed = make_url(url)
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        eng = super().create_engine(url)

        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        return eng


class _PostgreSQLBackend(_DatabaseBackend):
    def get_connection_args(self) -> dict:
        return {}

    def get_pool_config(self) -> dict:
        return {
            "pool_size": 20,
            "max_overflow": 20,
            "pool_timeout": 10,
            "pool_recycle": 300,
            "pool_pre_ping": True,
            "pool_reset_on_return": "rollback",
        }


_BACKEND_MAP: dict[str, type[_DatabaseBackend]] = {
    "sqlite": _SQLiteBackend,
    "postgresql": _PostgreSQLBackend,
    "postgresql+psycopg2": _PostgreSQLBackend,
    "postgresql+psycopg": _PostgreSQLBackend,
}


def get_engine(url: str) -> Engine:
    """Return a SQLAlchemy Engine for the given DATABASE_URL."""
    parsed = make_url(url)
    dialect = parsed.drivername
    backend_cls = _BACKEND_MAP.get(dialect) or _BACKEND_MAP.get(dialect.split("+")[0])
    if backend_cls is None:
        supported = ", ".join(_BACKEND_MAP.keys())
        raise ValueError(f"不支持的数据库类型: {dialect}。支持的类型: {supported}")
    return backend_cls().create_engine(url)
