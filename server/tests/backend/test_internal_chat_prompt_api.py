"""Integration test for GET /internal/prompts/{family_id}/chat."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.main import app
from apps.backend.app.models.family import Family
from apps.backend.app.services import workspace
from packages.security.service_auth.agent_jwt import create_agent_token

FAMILY_ID = 100


@pytest.fixture
def minimal_db():
    """Minimal in-memory DB with only Family table (avoid JSONB model imports)."""
    # Use in-memory SQLite with StaticPool for shared connection
    db_url = "sqlite:///:memory:"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create only the Family table
    Family.__table__.create(bind=engine, checkfirst=True)

    session = SessionLocal()
    family = Family(id=FAMILY_ID, name="Test Family", created_by=1)
    session.add(family)
    session.commit()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def agent_client(minimal_db, tmp_path, monkeypatch):
    """Client with agent token and workspace configured."""
    monkeypatch.setattr(settings, "WORKSPACE_ROOT", str(tmp_path))

    def override_get_db():
        try:
            yield minimal_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def _agent_headers(token: str | None = None) -> dict:
    """Generate auth headers with a valid JWT agent token."""
    jwt_token = token or create_agent_token(str(FAMILY_ID))
    return {
        "Authorization": f"Bearer {jwt_token}",
        "X-Family-Id": str(FAMILY_ID),
    }


def test_get_chat_prompt_returns_null_when_no_override(agent_client):
    resp = agent_client.get(
        f"/api/v1/internal/prompts/{FAMILY_ID}/chat",
        headers=_agent_headers(),
    )
    assert resp.status_code == 200
    # EnvelopeResponse wraps in {code, data, message}
    assert resp.json() == {"code": "OK", "data": {"content": None}, "message": ""}


def test_get_chat_prompt_returns_family_override(agent_client):
    workspace.save_chat_prompt(str(FAMILY_ID), "family A custom prompt")
    resp = agent_client.get(
        f"/api/v1/internal/prompts/{FAMILY_ID}/chat",
        headers=_agent_headers(),
    )
    assert resp.status_code == 200
    assert resp.json() == {"code": "OK", "data": {"content": "family A custom prompt"}, "message": ""}


def test_get_chat_prompt_rejects_invalid_token(agent_client):
    resp = agent_client.get(
        f"/api/v1/internal/prompts/{FAMILY_ID}/chat",
        headers=_agent_headers(token="wrong-token"),
    )
    assert resp.status_code == 401