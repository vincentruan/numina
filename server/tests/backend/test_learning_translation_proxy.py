"""Tests for the backend translate endpoint proxying to agent."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from apps.backend.app.errors import ErrorCode
from apps.backend.app.auth import deps
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


@pytest.fixture
def adult_user(db):
    user = User(
        id=1001, family_id=1, username="parent1",
        display_name="Parent", role="adult",
        password_hash="fake-hash-for-testing",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def _override_auth(adult_user):
    """Bypass auth for testing."""
    from apps.backend.app.main import app

    app.dependency_overrides[deps.require_adult] = lambda: adult_user
    yield
    app.dependency_overrides.pop(deps.require_adult, None)


def test_translate_proxies_to_agent(client, _override_auth, db):
    """Translate endpoint proxies to agent and persists translated fields."""
    topic = LearningTopic(
        topic_key="test_translate_proxy",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Addition",
        description="Basic addition",
        age_group="mid",
        evidence_json='["can add"]',
        standards_json="[]",
    )
    db.add(topic)
    db.flush()
    topic_id = topic.id

    agent_response = {
        "name_zh": "加法",
        "description_zh": "基本加法",
        "evidence_zh": ["会加法"],
        "assessment_prompt_zh": "请计算",
    }

    mock_resp = httpx.Response(
        200,
        json=agent_response,
        request=httpx.Request("POST", "http://test/translate/topic"),
    )

    with patch(
        "apps.backend.app.services.agent_client.AgentClient.post",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        resp = client.post(f"/api/v1/learning/topics/{topic_id}/translate")

    assert resp.status_code == 200
    envelope = resp.json()
    data = envelope["data"]
    assert data["name_zh"] == "加法"
    assert data["description_zh"] == "基本加法"

    # Verify DB persistence
    db.expire_all()
    updated = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    assert updated.name_zh == "加法"


def test_translate_agent_timeout_returns_503(client, _override_auth, db):
    """When agent service times out, return LEARNING_TRANSLATION_UNAVAILABLE."""
    topic = LearningTopic(
        topic_key="test_timeout_proxy",
        topic_type="CONCEPTUAL",
        subject="science",
        domain="Test",
        name="Photosynthesis",
        description="Plant process",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    with patch(
        "apps.backend.app.services.agent_client.AgentClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ):
        resp = client.post(f"/api/v1/learning/topics/{topic.id}/translate")

    assert resp.status_code == 503
    assert resp.json()["code"] == ErrorCode.LEARNING_TRANSLATION_UNAVAILABLE.value


def test_translate_agent_error_returns_503(client, _override_auth, db):
    """When agent returns an error, return LEARNING_TRANSLATION_UNAVAILABLE."""
    topic = LearningTopic(
        topic_key="test_error_proxy",
        topic_type="CONCEPTUAL",
        subject="english",
        domain="Test",
        name="Grammar",
        description="Rules",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    mock_resp = httpx.Response(
        503,
        json={"detail": "No AI provider configured"},
        request=httpx.Request("POST", "http://test/translate/topic"),
    )

    with patch(
        "apps.backend.app.services.agent_client.AgentClient.post",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        resp = client.post(f"/api/v1/learning/topics/{topic.id}/translate")

    assert resp.status_code == 503
