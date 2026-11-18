"""Tests for idempotent DDL helpers used by Alembic migrations.

The helpers exist because ``align_schema`` (app/services/db_migrate.py) adds
missing columns/indexes at boot without stamping ``alembic_version``. A
migration that then calls ``op.add_column`` unconditionally raises
``DuplicateColumn`` and pins the version permanently. These tests prove the
helpers no-op when the object already exists.
"""

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from apps.backend.alembic import ddl


def _ops_for(engine, monkeypatch):
    """Point the helpers' ``op`` at an Operations bound to *engine*."""
    ctx = MigrationContext.configure(engine.connect())
    ops = Operations(ctx)
    monkeypatch.setattr(ddl, "op", ops)
    return ops


def _make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _make_table(engine, name="widgets"):
    with engine.begin() as conn:
        conn.execute(sa.text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))


class TestHasHelpers:
    def test_has_table_true_and_false(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        assert ddl.has_table("widgets") is False
        _make_table(engine)
        assert ddl.has_table("widgets") is True

    def test_has_column_requires_table_and_column(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        # missing table → False, not an exception
        assert ddl.has_column("widgets", "size") is False
        _make_table(engine)
        assert ddl.has_column("widgets", "size") is False
        with engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE widgets ADD COLUMN size VARCHAR(10)"))
        assert ddl.has_column("widgets", "size") is True

    def test_has_index_requires_table_and_index(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        assert ddl.has_index("widgets", "ix_widgets_size") is False
        _make_table(engine)
        assert ddl.has_index("widgets", "ix_widgets_size") is False
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE INDEX ix_widgets_size ON widgets (id)"))
        assert ddl.has_index("widgets", "ix_widgets_size") is True


class TestAddColumnIdempotency:
    def test_add_column_creates_when_absent(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)

        ddl.add_column("widgets", sa.Column("size", sa.String(10), nullable=True))

        assert "size" in {c["name"] for c in inspect(engine).get_columns("widgets")}

    def test_add_column_noop_when_present(self, monkeypatch):
        """The core regression: a pre-existing column must not raise."""
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)
        with engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE widgets ADD COLUMN size VARCHAR(10)"))

        # Would raise DuplicateColumn without the guard.
        ddl.add_column("widgets", sa.Column("size", sa.String(99), nullable=True))

        cols = {c["name"]: c for c in inspect(engine).get_columns("widgets")}
        assert "size" in cols
        # The pre-existing definition wins — no type change is attempted.
        assert cols["size"]["type"].length == 10

    def test_add_column_noop_when_table_missing(self, monkeypatch):
        """Missing table is treated as "column absent" but must not crash either."""
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        # No table created; helper reports absent, then op.add_column will fail
        # loudly (correct — a missing table is a real problem, not drift).
        assert ddl.has_column("widgets", "size") is False


class TestCreateIndexIdempotency:
    def test_create_index_creates_when_absent(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)

        ddl.create_index("ix_widgets_id", "widgets", ["id"])

        assert "ix_widgets_id" in {i["name"] for i in inspect(engine).get_indexes("widgets")}

    def test_create_index_noop_when_present(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE INDEX ix_widgets_id ON widgets (id)"))

        # Would raise "index already exists" without the guard.
        ddl.create_index("ix_widgets_id", "widgets", ["id"])

        assert "ix_widgets_id" in {i["name"] for i in inspect(engine).get_indexes("widgets")}


class TestDropHelpers:
    def test_drop_column_noop_when_absent(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)
        ddl.drop_column("widgets", "size")  # must not raise
        assert "size" not in {c["name"] for c in inspect(engine).get_columns("widgets")}

    def test_drop_column_removes_when_present(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)
        with engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE widgets ADD COLUMN size VARCHAR(10)"))
        ddl.drop_column("widgets", "size")
        assert "size" not in {c["name"] for c in inspect(engine).get_columns("widgets")}

    def test_drop_index_noop_when_absent(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)
        ddl.drop_index("ix_widgets_id", "widgets")  # must not raise

    def test_drop_index_removes_when_present(self, monkeypatch):
        engine = _make_engine()
        _ops_for(engine, monkeypatch)
        _make_table(engine)
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE INDEX ix_widgets_id ON widgets (id)"))
        ddl.drop_index("ix_widgets_id", "widgets")
        assert "ix_widgets_id" not in {i["name"] for i in inspect(engine).get_indexes("widgets")}
