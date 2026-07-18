import os
import tempfile

# Force DATABASE_URL to a writable temp file BEFORE any app modules import settings.
# The lifespan handler in app.main runs schema migration against the production
# `engine`, which reads settings.DATABASE_URL at import time. On CI the default
# (~/.numina/data/db/numina.db) or Docker path from root .env (/app/.numina/data/db)
# parent dir doesn't exist or is read-only, causing OSError.
#
# A file-based temp SQLite (not :memory:) is required because the migration
# lock table must persist across the multiple connections opened by
# `run_schema_migration`. Per-test logic still uses a separate in-memory
# StaticPool DB below; the prod engine here only keeps lifespan startup happy.
# Note: We FORCE override even if root .env already sets DATABASE_URL.
import tempfile
_TEST_LIFESPAN_DIR = tempfile.mkdtemp(prefix="numina-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_LIFESPAN_DIR}/lifespan.db"

# Set AI_ENCRYPTION_KEY for tests that need encryption (web search providers, AI config)
os.environ["AI_ENCRYPTION_KEY"] = "TWkvLCaoHF_ZlwIUzytBOveIw5wmZj4ggVjWMgJr9BM="

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from apps.backend.app.database import Base, get_db
from apps.backend.app.main import app
from apps.backend.app.middleware.rate_limit import RateLimitMiddleware
from apps.backend.app.models.ai_agent import AIAgent  # noqa: F401
from apps.backend.app.models.ai_chat_session import AIChatSession  # noqa: F401
from apps.backend.app.models.ai_report import AIReport  # noqa: F401
from apps.backend.app.models.ai_task import AITask  # noqa: F401
from apps.backend.app.models.cached_file import CachedFile  # noqa: F401
from apps.backend.app.models.category_financial_default import CategoryFinancialDefault  # noqa: F401
from apps.backend.app.models.device_session import DeviceSession  # noqa: F401
from apps.backend.app.models.family import Family  # noqa: F401
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode  # noqa: F401
from apps.backend.app.models.family_mcp_server import FamilyMCPServer  # noqa: F401
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider  # noqa: F401
from apps.backend.app.models.notification_channel import NotificationChannel  # noqa: F401
from apps.backend.app.models.notification_config import NotificationConfig  # noqa: F401
from apps.backend.app.models.notification_subscription import NotificationSubscription  # noqa: F401
from apps.backend.app.models.reminder import Reminder  # noqa: F401
from apps.backend.app.models.revoked_token import RevokedToken  # noqa: F401

# Import all models to ensure they're registered with Base.metadata
# This is required for Base.metadata.create_all() to create all tables
from apps.backend.app.models.user import User  # noqa: F401
from apps.backend.app.seed.categories import seed_categories
from apps.backend.app.services.cache import reset_captcha_payload_cache, reset_rate_limit_cache

# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped engine + table creation (create once, reuse across all tests)
# ─────────────────────────────────────────────────────────────────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

# Create session-scoped engine with StaticPool for in-memory SQLite
# StaticPool ensures all connections share the same in-memory database
_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Session-scoped sessionmaker for creating connections
_SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="session")
def _session_engine():
    """Session-scoped engine — tables created once and reused."""
    # Create all tables once at session start
    Base.metadata.create_all(bind=_engine)
    yield _engine
    # Drop all tables at session end (cleanup)
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="function")
def db(_session_engine):
    """Function-scoped session with nested transaction (SAVEPOINT) isolation.

    Pattern: Session-level tables + Function-level nested transaction.
    - Tables created once per session (fast)
    - Each test gets a SAVEPOINT via begin_nested()
    - Business code db.commit() is caught in SAVEPOINT
    - Rollback at test end restores clean state

    This is 10-100x faster than create_all/drop_all per test.
    """
    # Reset rate limit store before each test
    if hasattr(RateLimitMiddleware, "_rate_store"):
        RateLimitMiddleware._rate_store.clear()

    # Reset cache (including registration rate limits)
    reset_rate_limit_cache()

    # Create a CONNECTION (not just session) for nested transaction support
    connection = _session_engine.connect()
    transaction = connection.begin()  # Outer transaction

    # Create session bound to this connection
    session = Session(bind=connection)

    # Begin a SAVEPOINT (nested transaction)
    nested = connection.begin_nested()

    # If the session commits, it's caught in the SAVEPOINT (not the outer tx)
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            # Ensure that state is expired the way session.commit() at normal
            # operation expires state (e.g. session.refresh() behavior)
            session.expire_all()
            session.begin_nested()

    # Seed categories and invitation codes inside the SAVEPOINT
    seed_categories(session)
    _seed_test_invitation_codes(session)

    yield session

    # Rollback to SAVEPOINT, discarding all changes from the test
    session.close()
    transaction.rollback()
    connection.close()

    # Reset rate limit store after each test
    if hasattr(RateLimitMiddleware, "_rate_store"):
        RateLimitMiddleware._rate_store.clear()
    # Reset captcha payload cache and rate limit cache
    reset_captcha_payload_cache()
    reset_rate_limit_cache()


def _seed_test_invitation_codes(session):
    """Seed test invitation codes for auth fixtures and tests."""
    codes = [
        FamilyInvitationCode(code="AUTO-TEST"),          # conftest.py - auth_headers fixture
        FamilyInvitationCode(code="AUTO-TEST-2"),        # conftest.py - second_user_headers fixture
        FamilyInvitationCode(code="AUTO-ADMIN"),         # test_admin_child_switch.py
        FamilyInvitationCode(code="AUTO-CREATE"),        # test_auth.py - test_register_success
        FamilyInvitationCode(code="AUTO-DUP"),           # test_auth.py - test_register_duplicate_username
        FamilyInvitationCode(code="AUTO-PARENT"),        # test_auth_security.py
        FamilyInvitationCode(code="AUTO-TIMING"),        # test_auth_security.py
        FamilyInvitationCode(code="AUTO-OWNER"),         # test_children.py
        FamilyInvitationCode(code="AUTO-MEMBER"),        # test_children.py
        FamilyInvitationCode(code="AUTO-MILESTONE-OTHER"),  # test_milestones.py
        FamilyInvitationCode(code="AUTO-SYNC"),          # test_file_sync.py
        FamilyInvitationCode(code="AUTO-OTHER"),         # test_chores_extended.py
        FamilyInvitationCode(code="AUTO-STORAGE"),       # test_file_storage_models.py
        FamilyInvitationCode(code="AUTO-STORAGE-2"),     # test_file_storage_models.py
        FamilyInvitationCode(code="AUTO-WEBAUTHN"),      # test_webauthn.py
    ]
    for code in codes:
        session.add(code)
    # DO NOT commit here — nested transaction (SAVEPOINT) handles isolation
    # session.commit() inside SAVEPOINT is caught and rolled back at test end


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    # Override get_db dependency for request injection
    app.dependency_overrides[get_db] = override_get_db

    # Override SessionLocal for all new sessions (including generators)
    # This ensures components that create their own SessionLocal() use the test database
    from apps.backend.app import database as app_database_module
    # Create a sessionmaker that yields our nested-transaction session
    # Note: We can't replace SessionLocal directly since it's a sessionmaker,
    # but the dependency override handles most cases
    original_session_local = app_database_module.SessionLocal

    # For tests, create a factory that returns the same nested session
    def _test_session_factory():
        return db

    app_database_module.SessionLocal = _test_session_factory

    with TestClient(app) as test_client:
        yield test_client

    # Restore original SessionLocal after test
    app_database_module.SessionLocal = original_session_local
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a user and return auth headers + tokens"""
    response = client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "display_name": "Test User",
        "password": "TestPass123",
        "family_name": "Test Family",
        "family_invitation_code": "AUTO-TEST"
    })
    assert response.status_code == 200
    data = response.json().get("data", response.json())
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "_refresh_token": data["refresh_token"],
    }


@pytest.fixture
def second_user_headers(client):
    """Create a second user in a different family"""
    response = client.post("/api/v1/auth/register", json={
        "username": "testuser2",
        "display_name": "Test User 2",
        "password": "TestPass456",
        "family_name": "Test Family 2",
        "family_invitation_code": "AUTO-TEST-2"
    })
    assert response.status_code == 200
    data = response.json().get("data", response.json())
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "_refresh_token": data["refresh_token"],
    }


def child_login_two_phase(client, username: str, password: str, pin_sequence: list[str]) -> str:
    """Two-phase child login helper. Returns child access token and sets child cookies."""
    step1 = client.post("/api/v1/auth/login/step1", json={
        "username": username,
        "password": password,
    })
    assert step1.status_code == 200, f"step1 failed: {step1.text}"
    data = step1.json()["data"]
    assert data["second_factor_required"] is True
    step2 = client.post("/api/v1/auth/login/step2", json={
        "temp_token": data["temp_token"],
        "factor_type": "emoji_pin",
        "payload": {"pin_sequence": pin_sequence},
    })
    assert step2.status_code == 200, f"step2 failed: {step2.text}"
    return step2.json()["data"]["access_token"]


# Fixtures for AI result writer tests
@pytest.fixture
def db_session(db):
    """Alias for db fixture for clarity in test naming."""
    return db


@pytest.fixture
def test_family(db):
    """Create a test family."""
    from apps.backend.app.models.family import Family
    from apps.backend.app.utils.snowflake import next_id

    family = Family(id=next_id(), name="Test Family for AI Results", created_by=next_id())
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@pytest.fixture
def test_user(db, test_family):
    """Create a test user in the test family."""
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    user = User(
        id=next_id(),
        username="ai_test_user",
        display_name="AI Test User",
        password_hash="test_hash",
        family_id=test_family.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_asset(db, test_family, test_user):
    """Create a test asset owned by the test family."""
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.utils.snowflake import next_id

    # Get a valid category_id from seeded categories
    from apps.backend.app.models.category import Category
    category = db.query(Category).first()

    asset = Asset(
        id=next_id(),
        family_id=test_family.id,
        user_id=test_user.id,
        category_id=category.id,
        name="Test Asset",
        asset_type="physical",
        is_archived=False,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@pytest.fixture
def other_family(db):
    """Create another family for cross-family isolation tests."""
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    family = Family(id=next_id(), name="Other Family", created_by=next_id())
    db.add(family)
    db.commit()
    db.refresh(family)

    user = User(
        id=next_id(),
        username="other_user",
        display_name="Other User",
        password_hash="test_hash",
        family_id=family.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return family


@pytest.fixture
def other_family_asset(db, other_family):
    """Create an asset owned by another family."""
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.user import User
    from apps.backend.app.models.category import Category
    from apps.backend.app.utils.snowflake import next_id

    user = db.query(User).filter(User.family_id == other_family.id).first()
    category = db.query(Category).first()

    asset = Asset(
        id=next_id(),
        family_id=other_family.id,
        user_id=user.id,
        category_id=category.id,
        name="Other Family Asset",
        asset_type="physical",
        is_archived=False,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@pytest.fixture
def archived_asset(db, test_family, test_user):
    """Create an archived asset owned by the test family."""
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.category import Category
    from apps.backend.app.utils.snowflake import next_id

    category = db.query(Category).first()

    asset = Asset(
        id=next_id(),
        family_id=test_family.id,
        user_id=test_user.id,
        category_id=category.id,
        name="Archived Asset",
        asset_type="physical",
        is_archived=True,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
