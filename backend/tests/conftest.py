import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import deps as auth_deps
from app.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import RateLimitMiddleware
from app.seed.categories import seed_categories
from app.services.cache import reset_captcha_payload_cache, reset_rate_limit_cache

# Import all models to ensure they're registered with Base.metadata
# This is required for Base.metadata.create_all() to create all tables
from app.models.user import User  # noqa: F401
from app.models.family import Family  # noqa: F401
from app.models.child_bind_token import ChildBindToken  # noqa: F401

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    # Reset rate limit store before each test
    if hasattr(RateLimitMiddleware, "_rate_store"):
        RateLimitMiddleware._rate_store.clear()

    # Reset JTI revocation stores
    auth_deps._revoked_jtis.clear()
    auth_deps._user_revocation_times.clear()

    # Reset cache (including registration rate limits)
    reset_rate_limit_cache()

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_categories(session)
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

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a user and return auth headers + tokens"""
    response = client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "display_name": "Test User",
        "password": "TestPass123",
        "family_name": "Test Family"
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
        "family_name": "Test Family 2"
    })
    assert response.status_code == 200
    data = response.json().get("data", response.json())
    return {
        "Authorization": f"Bearer {data['access_token']}",
        "_refresh_token": data["refresh_token"],
    }
