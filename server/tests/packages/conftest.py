"""Shared fixtures for packages/* tests.

packages/* modules import `SessionLocal` directly from `packages.db.session`
at module load time (`from packages.db.session import SessionLocal`), so they
hold their own reference. These fixtures build an isolated in-memory SQLite DB
from `packages.db.session.Base` and let each test patch the consuming module's
`SessionLocal` name to a factory returning the test session.

Usage in a test module:

    import packages.security.revoke_jti as revoke_mod

    def test_revoke(packages_db):
        revoke_mod.SessionLocal = lambda: packages_db  # patch consuming module
        revoke_mod.revoke_jti("jti-1", ttl_seconds=60)
        ...

Simpler: use the `patch_session_local` helper which patches a module attribute
and restores it after the test.
"""
import os
import tempfile

# Force a writable temp DATABASE_URL BEFORE any packages module imports settings,
# so `packages.db.session`'s import-time `engine = get_engine(settings.DATABASE_URL)`
# never touches a read-only/prod path.
_TEST_DIR = tempfile.mkdtemp(prefix="numina-packages-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR}/packages.db"
os.environ.setdefault("AI_ENCRYPTION_KEY", "TWkvLCaoHF_ZlwIUzytBOveIw5wmZj4ggVjWMgJr9BM=")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from packages.db.session import Base

# packages.db.session.Base is SHARED with the backend — backend models (Category,
# Tag, Asset, Liability, Wish, ...) register on the same Base. packages.db models
# like Family/User declare string relationships to them (Family.categories →
# "Category"), so the full backend model registry must be imported for
# configure_mappers() to resolve. Import the backend models package wholesale.
import apps.backend.app.models

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="session")
def _packages_engine():
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="function")
def packages_db(_packages_engine):
    """Function-scoped session with SAVEPOINT isolation (mirrors backend conftest)."""
    connection = _packages_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def patch_session_local(packages_db, monkeypatch):
    """Return a helper that patches `SessionLocal` on a given module to a factory
    yielding the test session. Restores automatically via monkeypatch.

        def test_x(patch_session_local):
            import packages.security.revoke_jti as mod
            patch_session_local(mod)
            mod.revoke_jti("j", 60)
    """
    def _patch(module):
        monkeypatch.setattr(module, "SessionLocal", lambda: packages_db)
        return packages_db

    return _patch
