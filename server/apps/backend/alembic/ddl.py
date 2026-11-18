"""Idempotent DDL helpers for Alembic migrations.

Background
----------
The backend runs ``align_schema`` on every boot (``app/services/db_migrate.py``).
It creates missing tables, adds missing columns and indexes straight from
``Base.metadata`` — but it does **not** write a new ``alembic_version``.

A database can therefore already hold a migration's schema changes while
``alembic_version`` still points at an older revision. An unconditional
``op.add_column`` then raises ``DuplicateColumn`` and pins the version
permanently, blocking every later migration in the chain.

The helpers below make such migrations safe to run against a
schema that is already aligned. Use them for any column/index creation in
migrations that may run after an ``align_schema`` pass.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def has_table(table: str) -> bool:
    """True if *table* exists in the target database."""
    return sa.inspect(op.get_bind()).has_table(table)


def has_column(table: str, column: str) -> bool:
    """True if *table* exists and already has *column*."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def has_index(table: str, index: str) -> bool:
    """True if *table* exists and already has an index named *index*."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(i["name"] == index for i in insp.get_indexes(table))


def add_column(table: str, column: sa.Column) -> None:
    """Add *column* to *table* unless the column already exists."""
    if not has_column(table, column.name):
        op.add_column(table, column)


def create_index(
    index_name: str,
    table: str,
    columns: list[str],
    unique: bool = False,
) -> None:
    """Create an index unless an index with that name already exists."""
    if not has_index(table, index_name):
        op.create_index(index_name, table, columns, unique=unique)


def drop_column(table: str, column: str) -> None:
    """Drop *column* from *table* if present."""
    if has_column(table, column):
        op.drop_column(table, column)


def drop_index(index_name: str, table: str) -> None:
    """Drop *index_name* on *table* if present."""
    if has_index(table, index_name):
        op.drop_index(index_name, table_name=table)
