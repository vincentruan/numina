import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.backend.app.database import Base, get_db
from apps.backend.app.main import app
from apps.backend.app.middleware.rate_limit import RateLimitMiddleware
from apps.backend.app.models.ai_allocation_target import AIAllocationTarget  # noqa: F401
from apps.backend.app.models.ai_chat_session import AIChatSession  # noqa: F401
from apps.backend.app.models.ai_report import AIReport  # noqa: F401
from apps.backend.app.models.ai_task import AITask  # noqa: F401
from apps.backend.app.models.ai_ws_ticket import AIWsTicket  # noqa: F401
from apps.backend.app.models.cached_file import CachedFile  # noqa: F401
from apps.backend.app.models.category_financial_default import CategoryFinancialDefault  # noqa: F401
from apps.backend.app.models.device_session import DeviceSession  # noqa: F401
from apps.backend.app.models.family import Family  # noqa: F401
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode  # noqa: F401
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

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

# Create engine and session factory for tests
# StaticPool ensures all connections share the same in-memory database
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
    session.commit()


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    # Reset rate limit store before each test
    if hasattr(RateLimitMiddleware, "_rate_store"):
        RateLimitMiddleware._rate_store.clear()

    # Reset cache (including registration rate limits)
    reset_rate_limit_cache()

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_categories(session)
    # Seed test invitation codes for fixtures
    _seed_test_invitation_codes(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        # Reset rate limit store after each test
        if hasattr(RateLimitMiddleware, "_rate_store"):
            RateLimitMiddleware._rate_store.clear()
        # Reset captcha payload cache and rate limit cache
        reset_captcha_payload_cache()
        reset_rate_limit_cache()


@pytest.fixture(scope="function")
def client(db):
    """Create a test client with database override"""
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
    original_session_local = app_database_module.SessionLocal
    app_database_module.SessionLocal = TestingSessionLocal

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
