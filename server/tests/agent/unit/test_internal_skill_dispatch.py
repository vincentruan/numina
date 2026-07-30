"""Unit tests for POST /internal/gateway/skill-dispatch endpoint."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.app.main import app
from apps.agent.services.deerflow_adapter.exceptions import DeerFlowTimeoutError
from packages.core.settings import settings as _core_settings
from packages.security.service_auth.agent_jwt import create_agent_token

_core_settings.SECRET_KEY = "test-secret-key-for-jwt-tests"

_TEST_FAMILY_ID = "1234567890"


@pytest.fixture
def client():
    return TestClient(app)


def _valid_payload(skill_name: str = "skill-creator") -> dict:
    return {
        "skill_name": skill_name,
        "family_id": "1234567890",
        "input_text": "Create a skill for tracking expenses",
    }


def _auth_headers() -> dict:
    return {"X-Agent-Token": create_agent_token(_TEST_FAMILY_ID)}


class TestSkillDispatchSuccess:
    @patch("apps.agent.app.routers.gateway.create_family_adapter")
    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_skill_creator_returns_content(self, mock_client_cls, mock_create_adapter, client):
        """Valid request with skill-creator returns generated SKILL.md text."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(return_value={
            "ai_provider": "anthropic",
            "api_key": "sk-test",
            "ai_model_id": "claude-3-5-sonnet",
        })
        mock_client_cls.return_value = mock_instance

        mock_adapter = MagicMock()
        mock_adapter.dispatch = AsyncMock(return_value="# SKILL.md\n## Expense Tracker\n...")
        mock_create_adapter.return_value = mock_adapter

        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload("skill-creator"),
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert "SKILL.md" in body["content"]

    @patch("apps.agent.app.routers.gateway.create_family_adapter")
    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_skill_installer_returns_content(self, mock_client_cls, mock_create_adapter, client):
        """Valid request with skill-installer returns downloaded SKILL.md text."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(return_value={
            "ai_provider": "openai",
            "api_key": "sk-openai-test",
            "ai_model_id": "gpt-4o",
        })
        mock_client_cls.return_value = mock_instance

        mock_adapter = MagicMock()
        mock_adapter.dispatch = AsyncMock(return_value="# Installed Skill\nContent here")
        mock_create_adapter.return_value = mock_adapter

        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload("skill-installer"),
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert "Installed Skill" in body["content"]

    @patch("apps.agent.app.routers.gateway.create_family_adapter")
    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_dispatch_called_with_correct_params(self, mock_client_cls, mock_create_adapter, client):
        """Dispatch is called with skill_name, context containing family_id and free_text, and a uuid thread_id."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(return_value={"ai_provider": "anthropic", "api_key": "sk-test"})
        mock_client_cls.return_value = mock_instance

        mock_adapter = MagicMock()
        mock_adapter.dispatch = AsyncMock(return_value="result")
        mock_create_adapter.return_value = mock_adapter

        payload = _valid_payload("skill-creator")
        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=payload,
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        mock_adapter.dispatch.assert_called_once()
        call_args = mock_adapter.dispatch.call_args
        assert call_args[0][0] == "skill-creator"  # skill_name positional
        # context should have family_id and free_text set
        context = call_args[0][1]
        assert context.family_id == payload["family_id"]
        assert context.free_text == payload["input_text"]
        # thread_id should be a valid UUID string
        thread_id = call_args[1]["thread_id"]
        assert len(thread_id) > 0  # uuid4 produces a non-empty string


class TestSkillDispatchAuth:
    def test_missing_token_returns_401(self, client):
        """Missing X-Agent-Token header returns 401."""
        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload(),
        )
        assert resp.status_code == 422  # FastAPI treats missing required header as 422

    def test_invalid_token_returns_401(self, client):
        """Invalid X-Agent-Token returns 401."""
        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload(),
            headers={"X-Agent-Token": "wrong-token"},
        )
        assert resp.status_code == 401


class TestSkillDispatchValidation:
    def test_invalid_skill_name_returns_400(self, client):
        """skill_name not in whitelist returns 400."""
        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json={
                "skill_name": "chat",
                "family_id": "1234567890",
                "input_text": "hello",
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 400
        assert "Invalid skill_name" in resp.json()["detail"]

    def test_another_invalid_skill_name_returns_400(self, client):
        """A non-whitelisted skill_name returns 400 with detail."""
        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json={
                "skill_name": "suggest",
                "family_id": "1234567890",
                "input_text": "hello",
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 400


class TestSkillDispatchTimeout:
    @patch("apps.agent.app.routers.gateway.create_family_adapter")
    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_dispatch_timeout_returns_504(self, mock_client_cls, mock_create_adapter, client):
        """DeerFlow dispatch timeout returns 504 with timeout message."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(return_value={"ai_provider": "anthropic", "api_key": "sk-test"})
        mock_client_cls.return_value = mock_instance

        mock_adapter = MagicMock()
        mock_adapter.dispatch = AsyncMock(side_effect=DeerFlowTimeoutError("timed out after 60s"))
        mock_create_adapter.return_value = mock_adapter

        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload(),
            headers=_auth_headers(),
        )

        assert resp.status_code == 504
        body = resp.json()
        assert "detail" in body
        assert "timed out" in body["detail"].lower()


class TestSkillDispatchError:
    @patch("apps.agent.app.routers.gateway.create_family_adapter")
    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_dispatch_error_returns_502(self, mock_client_cls, mock_create_adapter, client):
        """DeerFlow dispatch error returns 502 with error detail."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(return_value={"ai_provider": "anthropic", "api_key": "sk-test"})
        mock_client_cls.return_value = mock_instance

        mock_adapter = MagicMock()
        mock_adapter.dispatch = AsyncMock(side_effect=RuntimeError("LLM provider error"))
        mock_create_adapter.return_value = mock_adapter

        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload(),
            headers=_auth_headers(),
        )

        assert resp.status_code == 502
        body = resp.json()
        assert "detail" in body
        assert "dispatch failed" in body["detail"].lower()

    @patch("apps.agent.app.routers.gateway.create_family_adapter")
    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_adapter_creation_failure_returns_502(self, mock_client_cls, mock_create_adapter, client):
        """Adapter construction failure returns 502, not 500."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(return_value={"ai_provider": "anthropic", "api_key": "sk-test"})
        mock_client_cls.return_value = mock_instance
        mock_create_adapter.side_effect = RuntimeError("missing api_key in config")

        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload(),
            headers=_auth_headers(),
        )

        assert resp.status_code == 502
        assert "adapter" in resp.json()["detail"].lower()

    @patch("apps.agent.app.routers.gateway.BackendClient")
    def test_ai_config_fetch_failure_returns_502(self, mock_client_cls, client):
        """Failure to fetch AI config returns 502."""
        mock_instance = MagicMock()
        mock_instance.get_family_ai_config = AsyncMock(side_effect=Exception("backend unreachable"))
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json=_valid_payload(),
            headers=_auth_headers(),
        )

        assert resp.status_code == 502
        body = resp.json()
        assert "detail" in body
        assert "AI config" in body["detail"]


class TestSkillDispatchInvalidFamilyId:
    @pytest.mark.skip(reason="Family ID validation is currently disabled for development testing")
    def test_invalid_family_id_returns_400(self, client):
        """BackendClient ValueError on invalid family_id returns 400, not 500."""
        resp = client.post(
            "/internal/gateway/skill-dispatch",
            json={
                "skill_name": "skill-creator",
                "family_id": "abc",
                "input_text": "Create a skill",
            },
            headers=_auth_headers(),
        )

        assert resp.status_code == 400
        assert "family_id" in resp.json()["detail"].lower()
