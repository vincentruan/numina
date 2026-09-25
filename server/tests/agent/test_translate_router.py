"""Tests for the agent translate router."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.agent.app.main import app
from packages.security.service_auth.agent_token_verify import verify_service_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def override_auth():
    """Override verify_service_token for tests."""
    app.dependency_overrides[verify_service_token] = lambda: "test-family-id"
    yield
    app.dependency_overrides.clear()


_HEADERS = {"X-Family-Id": "123"}


def test_translate_endpoint_no_token_rejected(client):
    """Request without X-Agent-Token returns 422 (missing required header)."""
    resp = client.post(
        "/translate/topic",
        json={"name": "Test", "description": "D", "evidence": [], "assessment_prompt": ""},
    )
    # 422 because X-Agent-Token is a required header
    assert resp.status_code == 422


def test_translate_endpoint_no_provider_returns_503(client, override_auth):
    """When no AI provider is configured, return 503."""
    from apps.agent.core.backend_client import BackendClient

    with patch.object(
        BackendClient, "get_family_ai_config",
        new_callable=AsyncMock,
        return_value={"providers": []},
    ):
        resp = client.post(
            "/translate/topic",
            json={"name": "Test", "description": "D", "evidence": [], "assessment_prompt": ""},
            headers=_HEADERS,
        )
    assert resp.status_code == 503


def test_translate_endpoint_all_providers_open_returns_503(client, override_auth):
    """When all providers have open circuits, return 503."""
    from apps.agent.core.backend_client import BackendClient

    with patch.object(
        BackendClient, "get_family_ai_config",
        new_callable=AsyncMock,
        return_value={"providers": [{"circuit_state": "open", "ai_provider": "openai"}]},
    ):
        resp = client.post(
            "/translate/topic",
            json={"name": "Test", "description": "D", "evidence": [], "assessment_prompt": ""},
            headers=_HEADERS,
        )
    assert resp.status_code == 503


def test_translate_endpoint_success(client, override_auth):
    """Successful translation returns _zh fields."""
    from apps.agent.core.backend_client import BackendClient

    provider_config = {
        "ai_provider": "openai_compatible",
        "ai_model_id": "qwen-plus",
        "api_key": "test-key",
        "ai_base_url": "https://example.com/v1",
        "circuit_state": "closed",
    }

    translated = {
        "name_zh": "加法",
        "description_zh": "基本加法",
        "evidence_zh": ["会加法"],
        "assessment_prompt_zh": "请计算",
    }

    with patch.object(
        BackendClient, "get_family_ai_config",
        new_callable=AsyncMock,
        return_value={"providers": [provider_config]},
    ):
        with patch(
            "apps.agent.routers.translate.translate_topic",
            new_callable=AsyncMock,
            return_value=translated,
        ):
            resp = client.post(
                "/translate/topic",
                json={"name": "Addition", "description": "D", "evidence": [], "assessment_prompt": ""},
                headers=_HEADERS,
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name_zh"] == "加法"
    assert data["description_zh"] == "基本加法"


def test_translate_endpoint_llm_failure_returns_503(client, override_auth):
    """When LLM call fails, return 503."""
    from apps.agent.core.backend_client import BackendClient

    provider_config = {
        "ai_provider": "openai_compatible",
        "ai_model_id": "qwen-plus",
        "api_key": "test-key",
        "ai_base_url": "https://example.com/v1",
        "circuit_state": "closed",
    }

    with patch.object(
        BackendClient, "get_family_ai_config",
        new_callable=AsyncMock,
        return_value={"providers": [provider_config]},
    ):
        with patch(
            "apps.agent.routers.translate.translate_topic",
            new_callable=AsyncMock,
            side_effect=ValueError("LLM API key not configured"),
        ):
            resp = client.post(
                "/translate/topic",
                json={"name": "Test", "description": "D", "evidence": [], "assessment_prompt": ""},
                headers=_HEADERS,
            )
    assert resp.status_code == 503
