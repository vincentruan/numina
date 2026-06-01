"""Distributed lock provider for multi-instance safety."""

from __future__ import annotations

import abc
import logging
import os
import socket
import time

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

LOCK_TABLE = "_reconcile_lock"
LOCK_TIMEOUT_SECONDS = 60
LOCK_WAIT_MAX_SECONDS = 120
LOCK_CHECK_INTERVAL = 1.0


class LockProvider(abc.ABC):
    """Abstract lock interface — implementations vary by database backend."""

    @abc.abstractmethod
    def acquire(self, lock_name: str, timeout: float = LOCK_WAIT_MAX_SECONDS) -> bool:
        """Acquire a named lock. Returns True on success."""

    @abc.abstractmethod
    def release(self, lock_name: str) -> None:
        """Release a previously acquired lock."""

    @abc.abstractmethod
    def is_held(self, lock_name: str) -> bool:
        """Check if the lock is currently held (by anyone)."""


class PostgresAdvisoryLock(LockProvider):
    """Uses pg_advisory_lock for zero-table distributed locking."""

    # Stable hash for "reconcile" namespace
    _LOCK_NAMESPACE = 0x5265636F  # "Reco" in hex

    def __init__(self, engine: Engine):
        self._engine = engine
        self._conn = None

    def _lock_id(self, lock_name: str) -> int:
        return hash(lock_name) & 0x7FFFFFFF

    def acquire(self, lock_name: str, timeout: float = LOCK_WAIT_MAX_SECONDS) -> bool:
        lock_id = self._lock_id(lock_name)
        self._conn = self._engine.connect()
        try:
            self._conn.execute(
                text(f"SET lock_timeout = '{int(timeout * 1000)}ms'")
            )
            self._conn.execute(
                text("SELECT pg_advisory_lock(:ns, :id)"),
                {"ns": self._LOCK_NAMESPACE, "id": lock_id},
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to acquire advisory lock '{lock_name}': {e}")
            if self._conn:
                self._conn.close()
                self._conn = None
            return False

    def release(self, lock_name: str) -> None:
        if self._conn:
            lock_id = self._lock_id(lock_name)
            try:
                self._conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :id)"),
                    {"ns": self._LOCK_NAMESPACE, "id": lock_id},
                )
            finally:
                self._conn.close()
                self._conn = None

    def is_held(self, lock_name: str) -> bool:
        lock_id = self._lock_id(lock_name)
        with self._engine.connect() as conn:
            result = conn.execute(
                text("SELECT pg_try_advisory_lock(:ns, :id)"),
                {"ns": self._LOCK_NAMESPACE, "id": lock_id},
            )
            acquired = result.scalar()
            if acquired:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:ns, :id)"),
                    {"ns": self._LOCK_NAMESPACE, "id": lock_id},
                )
                return False
            return True


class TableBasedLock(LockProvider):
    """Fallback lock using a database table (works with SQLite and any SQL DB)."""

    def __init__(self, engine: Engine):
        self._engine = engine
        self._holder = f"{socket.gethostname()}-{os.getpid()}"
        self._ensure_table()

    def _ensure_table(self) -> None:
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(self._engine)
        if LOCK_TABLE not in inspector.get_table_names():
            dialect = self._engine.dialect.name
            with self._engine.begin() as conn:
                if dialect == "sqlite":
                    conn.execute(text(
                        f"CREATE TABLE IF NOT EXISTS {LOCK_TABLE} ("
                        "lock_name TEXT PRIMARY KEY, "
                        "locked_at REAL NOT NULL, "
                        "holder TEXT NOT NULL"
                        ")"
                    ))
                else:
                    conn.execute(text(
                        f"CREATE TABLE IF NOT EXISTS {LOCK_TABLE} ("
                        "lock_name VARCHAR(128) PRIMARY KEY, "
                        "locked_at DOUBLE PRECISION NOT NULL, "
                        "holder VARCHAR(255) NOT NULL"
                        ")"
                    ))

    def acquire(self, lock_name: str, timeout: float = LOCK_WAIT_MAX_SECONDS) -> bool:
        deadline = time.time() + timeout

        while time.time() < deadline:
            with self._engine.begin() as conn:
                result = conn.execute(
                    text(f"SELECT locked_at, holder FROM {LOCK_TABLE} WHERE lock_name = :name"),
                    {"name": lock_name},
                )
                row = result.fetchone()
                now = time.time()

                if row is None:
                    try:
                        conn.execute(
                            text(
                                f"INSERT INTO {LOCK_TABLE} (lock_name, locked_at, holder) "
                                "VALUES (:name, :at, :holder)"
                            ),
                            {"name": lock_name, "at": now, "holder": self._holder},
                        )
                        return True
                    except Exception:
                        pass
                elif now - row[0] > LOCK_TIMEOUT_SECONDS:
                    logger.warning(
                        f"Lock '{lock_name}' expired (held by {row[1]}), taking over"
                    )
                    conn.execute(
                        text(
                            f"UPDATE {LOCK_TABLE} SET locked_at = :at, holder = :holder "
                            "WHERE lock_name = :name"
                        ),
                        {"name": lock_name, "at": now, "holder": self._holder},
                    )
                    return True

            time.sleep(LOCK_CHECK_INTERVAL)

        logger.error(f"Timed out waiting for lock '{lock_name}' after {timeout}s")
        return False

    def release(self, lock_name: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {LOCK_TABLE} WHERE lock_name = :name AND holder = :holder"),
                {"name": lock_name, "holder": self._holder},
            )

    def is_held(self, lock_name: str) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT locked_at FROM {LOCK_TABLE} WHERE lock_name = :name"),
                {"name": lock_name},
            )
            row = result.fetchone()
            if row is None:
                return False
            return (time.time() - row[0]) <= LOCK_TIMEOUT_SECONDS


def create_lock_provider(engine: Engine) -> LockProvider:
    """Factory — picks the best lock strategy for the database backend."""
    dialect = engine.dialect.name
    if dialect in ("postgresql", "postgres"):
        return PostgresAdvisoryLock(engine)
    return TableBasedLock(engine)
