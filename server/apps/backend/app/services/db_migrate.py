"""Database schema alignment service.

Provides automatic schema migration with:
- Multi-database support (SQLite, PostgreSQL)
- Distributed locking for multi-instance safety
- Full table/column/index alignment
"""

import logging
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from apps.backend.app.database import Base

logger = logging.getLogger(__name__)

# Lock configuration
LOCK_TABLE_NAME = "_schema_migration_lock"
LOCK_TIMEOUT_SECONDS = 30  # Max time to hold lock
LOCK_WAIT_MAX_SECONDS = 60  # Max time to wait for lock
LOCK_CHECK_INTERVAL = 0.5  # Interval to check lock status


def get_db_type(engine: Engine) -> str:
    """Detect database type from engine."""
    dialect = engine.dialect.name
    if dialect == "sqlite":
        return "sqlite"
    elif dialect in ("postgresql", "postgres"):
        return "postgresql"
    else:
        return dialect


def get_existing_tables(engine: Engine) -> set[str]:
    """Get list of existing tables in database."""
    db_type = get_db_type(engine)

    with engine.connect() as conn:
        if db_type == "sqlite":
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
            return {row[0] for row in result}
        elif db_type == "postgresql":
            result = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            return {row[0] for row in result}
        else:
            return set()


def get_existing_columns(engine: Engine, table_name: str) -> dict[str, str]:
    """Get existing columns for a table. Returns dict of column_name -> column_type."""
    db_type = get_db_type(engine)

    with engine.connect() as conn:
        if db_type == "sqlite":
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            return {row[1]: row[2] for row in result}
        elif db_type == "postgresql":
            result = conn.execute(
                text(
                    f"SELECT column_name, data_type FROM information_schema.columns "
                    f"WHERE table_schema = 'public' AND table_name = '{table_name}'"
                )
            )
            return {row[0]: row[1] for row in result}
        else:
            return {}


def get_existing_indexes(engine: Engine, table_name: str) -> set[str]:
    """Get existing indexes for a table."""
    db_type = get_db_type(engine)

    with engine.connect() as conn:
        if db_type == "sqlite":
            result = conn.execute(text(f"PRAGMA index_list({table_name})"))
            return {row[1] for row in result}
        elif db_type == "postgresql":
            result = conn.execute(
                text(
                    f"SELECT indexname FROM pg_indexes "
                    f"WHERE schemaname = 'public' AND tablename = '{table_name}'"
                )
            )
            return {row[0] for row in result}
        else:
            return set()


def ensure_lock_table(engine: Engine) -> None:
    """Create the migration lock table if it doesn't exist."""
    db_type = get_db_type(engine)
    existing = get_existing_tables(engine)

    if LOCK_TABLE_NAME in existing:
        return

    logger.info(f"Creating migration lock table: {LOCK_TABLE_NAME}")

    with engine.begin() as conn:
        if db_type == "sqlite":
            conn.execute(
                text(
                    f"CREATE TABLE {LOCK_TABLE_NAME} ("
                    "lock_id TEXT PRIMARY KEY, "
                    "locked_at REAL, "
                    "holder TEXT"
                    ")"
                )
            )
        elif db_type == "postgresql":
            conn.execute(
                text(
                    f"CREATE TABLE {LOCK_TABLE_NAME} ("
                    "lock_id VARCHAR(64) PRIMARY KEY, "
                    "locked_at DOUBLE PRECISION, "
                    "holder VARCHAR(255)"
                    ")"
                )
            )


def acquire_migration_lock(engine: Engine) -> bool:
    """Acquire migration lock with timeout handling.

    Returns True if lock acquired, False if failed.
    Uses double-check pattern to handle concurrent acquisition.
    """
    ensure_lock_table(engine)

    # Generate unique holder ID
    import os
    import socket

    holder_id = f"{socket.gethostname()}-{os.getpid()}"

    lock_id = "schema_migration"

    def try_acquire() -> bool:
        """Attempt to acquire lock."""
        with engine.begin() as conn:
            # Check if lock exists
            result = conn.execute(
                text(
                    f"SELECT locked_at, holder FROM {LOCK_TABLE_NAME} WHERE lock_id = :lock_id"
                ),
                {"lock_id": lock_id},
            )
            row = result.fetchone()

            current_time = time.time()

            if row is None:
                # No lock exists, try to acquire
                try:
                    conn.execute(
                        text(
                            f"INSERT INTO {LOCK_TABLE_NAME} (lock_id, locked_at, holder) "
                            "VALUES (:lock_id, :locked_at, :holder)"
                        ),
                        {
                            "lock_id": lock_id,
                            "locked_at": current_time,
                            "holder": holder_id,
                        },
                    )
                    return True
                except Exception:
                    # Concurrent insert failed
                    return False

            locked_at, existing_holder = row

            # Check if lock is expired
            if current_time - locked_at > LOCK_TIMEOUT_SECONDS:
                logger.warning(
                    f"Lock held by {existing_holder} is expired (age: {current_time - locked_at:.1f}s), "
                    "attempting to take over"
                )
                try:
                    conn.execute(
                        text(
                            f"UPDATE {LOCK_TABLE_NAME} "
                            "SET locked_at = :locked_at, holder = :holder "
                            "WHERE lock_id = :lock_id"
                        ),
                        {
                            "lock_id": lock_id,
                            "locked_at": current_time,
                            "holder": holder_id,
                        },
                    )
                    return True
                except Exception:
                    return False

            # Lock is held by another process
            return False

    def double_check(holder: str) -> bool:
        """Double-check that we actually hold the lock."""
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT holder FROM {LOCK_TABLE_NAME} WHERE lock_id = :lock_id"),
                {"lock_id": lock_id},
            )
            row = result.fetchone()
            return row is not None and row[0] == holder

    # Try to acquire with retries
    wait_time = 0
    while wait_time < LOCK_WAIT_MAX_SECONDS:
        if try_acquire():
            # Double-check we actually hold it
            if double_check(holder_id):
                logger.info(f"Migration lock acquired by {holder_id}")
                return True
            # Race condition - someone else got it
            logger.info("Lock acquisition race detected, retrying...")

        wait_time = int(wait_time + LOCK_CHECK_INTERVAL)
        time.sleep(LOCK_CHECK_INTERVAL)

    logger.error(f"Failed to acquire migration lock after {wait_time:.1f}s")
    return False


def release_migration_lock(engine: Engine) -> None:
    """Release migration lock."""
    import os
    import socket

    holder_id = f"{socket.gethostname()}-{os.getpid()}"
    lock_id = "schema_migration"

    with engine.begin() as conn:
        result = conn.execute(
            text(f"SELECT holder FROM {LOCK_TABLE_NAME} WHERE lock_id = :lock_id"),
            {"lock_id": lock_id},
        )
        row = result.fetchone()

        if row and row[0] == holder_id:
            conn.execute(
                text(f"DELETE FROM {LOCK_TABLE_NAME} WHERE lock_id = :lock_id"),
                {"lock_id": lock_id},
            )
            logger.info(f"Migration lock released by {holder_id}")
        elif row:
            logger.warning(f"Lock held by {row[0]}, not releasing (we are {holder_id})")


def get_expected_columns_from_model(table_name: str) -> dict[str, Any]:
    """Extract expected columns from SQLAlchemy model definition."""
    if table_name not in Base.metadata.tables:
        return {}

    table = Base.metadata.tables[table_name]
    columns = {}

    for column in table.columns:
        # Extract default value properly
        default_val = None
        default_type = None  # Track type of default: 'scalar', 'func_now', None

        # Check server_default first (database-level default)
        if column.server_default is not None:
            # server_default can be a func expression like func.now()
            if hasattr(column.server_default, "arg"):
                arg = column.server_default.arg
                # Check if it's a SQL function expression
                if isinstance(arg, str):
                    default_val = arg
                    default_type = "sql_expr"
                elif hasattr(arg, "text") and isinstance(
                    getattr(arg, "text", None), str
                ):
                    # text("...") yields a TextClause whose .text holds the raw
                    # SQL expression (e.g. text("true") -> "true"). Use it as the
                    # default so server_default=text("true") produces DEFAULT true.
                    default_val = arg.text
                    default_type = "sql_expr"
                elif hasattr(arg, "name"):
                    default_type = "func_now" if arg.name == "now" else "sql_func"
                else:
                    default_type = "sql_expr"
            else:
                default_type = "sql_expr"
        # Check default (Python-side default)
        elif column.default is not None:
            # SQLAlchemy ColumnDefault has .arg attribute with actual value
            if hasattr(column.default, "arg"):
                arg = column.default.arg
                # Handle callable defaults (functions) - skip them
                if callable(arg):
                    default_val = None
                    default_type = None
                else:
                    default_val = arg
                    default_type = "scalar"
            elif isinstance(column.default, (str, int, float, bool)):
                default_val = column.default  # type: ignore[assignment]
                default_type = "scalar"
            # For other cases, try to get scalar value
            elif hasattr(column.default, "value"):
                default_val = column.default.value
                default_type = "scalar"
            else:
                # Skip non-simple defaults
                default_val = None
                default_type = None

        columns[column.name] = {
            "type": str(column.type),
            "nullable": column.nullable,
            "primary_key": column.primary_key,
            "default": default_val,
            "default_type": default_type,
        }

    return columns


def get_expected_indexes_from_model(table_name: str) -> dict[str, Any]:
    """Extract expected indexes from SQLAlchemy model definition."""
    if table_name not in Base.metadata.tables:
        return {}

    table = Base.metadata.tables[table_name]
    indexes: dict[str, Any] = {}

    for index in table.indexes:
        # Skip primary key indexes (they're handled separately)
        if len(index.columns) == 1 and index.columns[0].primary_key:
            continue
        idx_name = index.name
        if idx_name is None:
            continue
        indexes[idx_name] = {
            "columns": [c.name for c in index.columns],
            "unique": index.unique,
        }

    return indexes


def add_column(
    engine: Engine, table_name: str, column_name: str, column_info: dict
) -> None:
    """Add a missing column to a table."""
    db_type = get_db_type(engine)
    col_type = column_info["type"]

    # Normalize type for different databases
    type_sql = col_type

    # Handle common type mappings
    if db_type == "sqlite":
        # SQLite doesn't support TEXT(n) syntax - strip length specifiers
        import re

        # Remove length specifier from TEXT types: TEXT(20) -> TEXT
        type_sql = re.sub(r"TEXT\(\d+\)", "TEXT", type_sql.upper())
        # Also handle VARCHAR(n) -> TEXT (SQLite treats them same)
        type_sql = re.sub(r"VARCHAR\(\d+\)", "TEXT", type_sql)
        # Simplify other types
        if "INTEGER" in type_sql.upper():
            type_sql = "INTEGER"
        elif "BOOLEAN" in type_sql.upper():
            type_sql = "BOOLEAN"
        elif "DATETIME" in type_sql.upper() or "TIMESTAMP" in type_sql.upper():
            type_sql = "DATETIME"
        elif "FLOAT" in type_sql.upper() or "REAL" in type_sql.upper():
            type_sql = "REAL"
        elif "NUMERIC" in type_sql.upper():
            type_sql = "NUMERIC"
    nullable_clause = "" if column_info["nullable"] else "NOT NULL"

    # Handle default value properly
    default_clause = ""
    default_val = column_info.get("default")
    default_type = column_info.get("default_type")

    if default_type == "func_now":
        # func.now() - use database-specific timestamp function
        if db_type in ("sqlite", "postgresql"):
            default_clause = "DEFAULT CURRENT_TIMESTAMP"
    elif default_type == "sql_expr" and default_val is not None:
        # SQL expression default - use as-is
        default_clause = f"DEFAULT {default_val}"
    elif default_type == "scalar" and default_val is not None:
        # Scalar value default
        if isinstance(default_val, bool):
            # Boolean: SQLite uses 0/1, PostgreSQL uses FALSE/TRUE
            if db_type == "sqlite":
                default_clause = f"DEFAULT {1 if default_val else 0}"
            else:
                default_clause = f"DEFAULT {'TRUE' if default_val else 'FALSE'}"
        elif isinstance(default_val, (int, float)):
            default_clause = f"DEFAULT {default_val}"
        elif isinstance(default_val, str):
            # String: quote it
            # Escape single quotes
            escaped_val = default_val.replace("'", "''")
            default_clause = f"DEFAULT '{escaped_val}'"
        # Skip callable defaults and other complex types

    # SQLite cannot ALTER TABLE ADD COLUMN with NOT NULL and no default:
    # existing rows would need a value, so SQLite rejects it with
    # "Cannot add a NOT NULL column with default value NULL". Provide a
    # type-appropriate fallback so legacy DBs can be upgraded in place.
    # (Columns with a real server_default are already handled above.)
    if db_type == "sqlite" and not column_info["nullable"] and not default_clause:
        if "BOOLEAN" in type_sql.upper():
            default_clause = "DEFAULT 0"
        elif "INTEGER" in type_sql.upper():
            default_clause = "DEFAULT 0"
        elif any(t in type_sql.upper() for t in ("REAL", "NUMERIC", "FLOAT")):
            default_clause = "DEFAULT 0"
        else:  # TEXT and other string types
            default_clause = "DEFAULT ''"

    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {type_sql} {nullable_clause} {default_clause}"
    sql = sql.strip()

    logger.info(f"Adding column: {table_name}.{column_name} ({type_sql})")

    with engine.begin() as conn:
        conn.execute(text(sql))


def add_index(
    engine: Engine, table_name: str, index_name: str, index_info: dict
) -> None:
    """Add a missing index to a table."""
    columns = index_info["columns"]
    unique = "UNIQUE" if index_info["unique"] else ""

    columns_str = ", ".join(columns)

    sql = f"CREATE {unique} INDEX {index_name} ON {table_name} ({columns_str})"
    sql = sql.strip()

    logger.info(f"Adding index: {index_name} on {table_name} ({columns_str})")

    with engine.begin() as conn:
        conn.execute(text(sql))


def create_table(engine: Engine, table_name: str) -> None:
    """Create a missing table."""
    if table_name not in Base.metadata.tables:
        logger.warning(f"Table {table_name} not found in models, skipping")
        return

    table = Base.metadata.tables[table_name]

    # Use SQLAlchemy's built-in create for this table only
    logger.info(f"Creating missing table: {table_name}")

    with engine.begin() as conn:
        table.create(conn)


def align_schema(engine: Engine) -> dict[str, Any]:
    """Align database schema with model definitions.

    Returns a summary of changes made.
    """
    summary: dict[str, Any] = {
        "tables_created": [],
        "columns_added": [],
        "indexes_added": [],
        "errors": [],
    }

    expected_tables = set(Base.metadata.tables.keys())
    existing_tables = get_existing_tables(engine)

    # 1. Create missing tables
    for table_name in expected_tables:
        if table_name not in existing_tables:
            try:
                create_table(engine, table_name)
                summary["tables_created"].append(table_name)
            except Exception as e:
                logger.error(f"Failed to create table {table_name}: {e}")
                summary["errors"].append(f"table:{table_name}:{str(e)}")
                continue

    # Refresh existing tables after creations
    existing_tables = get_existing_tables(engine)

    # 2. Add missing columns to existing tables
    for table_name in expected_tables:
        if table_name not in existing_tables:
            continue

        expected_columns = get_expected_columns_from_model(table_name)
        existing_columns = get_existing_columns(engine, table_name)

        for col_name, col_info in expected_columns.items():
            if col_name not in existing_columns:
                try:
                    add_column(engine, table_name, col_name, col_info)
                    summary["columns_added"].append(f"{table_name}.{col_name}")
                except Exception as e:
                    logger.error(f"Failed to add column {table_name}.{col_name}: {e}")
                    summary["errors"].append(f"column:{table_name}.{col_name}:{str(e)}")

    # 3. Add missing indexes
    for table_name in expected_tables:
        if table_name not in existing_tables:
            continue

        expected_indexes = get_expected_indexes_from_model(table_name)
        existing_indexes = get_existing_indexes(engine, table_name)

        for idx_name, idx_info in expected_indexes.items():
            if idx_name not in existing_indexes:
                try:
                    add_index(engine, table_name, idx_name, idx_info)
                    summary["indexes_added"].append(f"{table_name}.{idx_name}")
                except Exception as e:
                    logger.error(f"Failed to add index {table_name}.{idx_name}: {e}")
                    summary["errors"].append(f"index:{table_name}.{idx_name}:{str(e)}")

    return summary


def run_schema_migration(engine: Engine) -> dict[str, Any]:
    """Run schema migration with distributed locking.

    This is the main entry point called from lifespan.

    Returns a summary of migration results.
    """
    db_type = get_db_type(engine)
    logger.info(f"Starting schema migration check (database: {db_type})")

    # Try to acquire lock
    if not acquire_migration_lock(engine):
        logger.warning(
            "Another instance is performing schema migration. "
            "Waiting and verifying schema..."
        )

        # Wait for migration to complete (lock release)
        wait_time = 0
        while wait_time < LOCK_WAIT_MAX_SECONDS:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        f"SELECT lock_id FROM {LOCK_TABLE_NAME} WHERE lock_id = 'schema_migration'"
                    )
                )
                if result.fetchone() is None:
                    break
            wait_time = int(wait_time + LOCK_CHECK_INTERVAL)
            time.sleep(LOCK_CHECK_INTERVAL)

        # Double-check schema after waiting
        existing = get_existing_tables(engine)
        expected = set(Base.metadata.tables.keys())

        missing = expected - existing
        if missing:
            logger.warning(f"After waiting, still missing tables: {missing}")
            # Try migration anyway (lock might have expired)
            if acquire_migration_lock(engine):
                summary = align_schema(engine)
                release_migration_lock(engine)
                return summary

        return {
            "tables_created": [],
            "columns_added": [],
            "indexes_added": [],
            "errors": [],
            "skipped": True,
            "reason": "Another instance completed migration",
        }

    # We have the lock, perform migration
    try:
        summary = align_schema(engine)
        summary["db_type"] = db_type
        return summary
    finally:
        release_migration_lock(engine)
