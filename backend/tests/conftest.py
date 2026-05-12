import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.ai_allocation_target import AIAllocationTarget  # noqa: F401
from app.models.ai_chat_session import AIChatSession  # noqa: F401
from app.models.ai_report import AIReport  # noqa: F401
from app.models.ai_task import AITask  # noqa: F401
from app.models.ai_ws_ticket import AIWsTicket  # noqa: F401
from app.models.cached_file import CachedFile  # noqa: F401
from app.models.category_financial_default import CategoryFinancialDefault  # noqa: F401
from app.models.device_session import DeviceSession  # noqa: F401
from app.models.family import Family  # noqa: F401
from app.models.family_invitation_code import FamilyInvitationCode  # noqa: F401
from app.models.notification_channel import NotificationChannel  # noqa: F401
from app.models.notification_config import NotificationConfig  # noqa: F401
from app.models.notification_subscription import NotificationSubscription  # noqa: F401
from app.models.reminder import Reminder  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401

# Import all models to ensure they're registered with Base.metadata
# This is required for Base.metadata.create_all() to create all tables
from app.models.user import User  # noqa: F401
from app.seed.categories import seed_categories
from app.services.cache import reset_captcha_payload_cache, reset_rate_limit_cache

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
    from app import database as app_database_module
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
