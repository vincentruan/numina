"""Tests for POST /ai/skills/ai-create and POST /ai/skills/custom/raw endpoints."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.backend.app.auth.deps import require_owner
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User


def _make_mock_user(**overrides):
    defaults = dict(id=123, family_id=456, is_active=True, role="owner")
    defaults.update(overrides)
    return MagicMock(spec=User, **defaults)


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_BASE_URL", "http://agent:8001")
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.scalar.return_value = 199
    return db


@pytest.fixture
def client(tmp_path, mock_db):
    from apps.backend.app.main import app

    mock_user = _make_mock_user()

    def _override_owner():
        return mock_user

    def _override_db():
        yield mock_db

    app.dependency_overrides[require_owner] = _override_owner
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _unwrap(resp):
    """Unwrap the global response envelope {"code": ..., "data": ...}."""
    body = resp.json()
    return body.get("data", body)


class TestAICreateEndpoint:
    @patch("apps.backend.app.routers.ai_skills.httpx.AsyncClient")
    def test_valid_description_returns_skill_md(self, mock_httpx_cls, client):
        """Valid description returns well-formed SKILL.md with frontmatter."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": "---\nname: expense-tracker\ndescription: Track monthly expenses\n---\n## When to Use\nWhen user asks about expenses.\n## Instructions\nAnalyze spending patterns."
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        resp = client.post(
            "/api/v1/ai/skills/ai-create",
            json={"description": "帮我创建一个分析家庭月度支出趋势的技能"},
        )

        assert resp.status_code == 200
        data = _unwrap(resp)
        assert "content" in data
        assert data["parsed_name"] == "expense-tracker"
        assert data["parsed_description"] == "Track monthly expenses"

    def test_empty_description_returns_validation_error(self, client):
        """Empty description returns 422 validation error."""
        resp = client.post(
            "/api/v1/ai/skills/ai-create",
            json={"description": ""},
        )
        assert resp.status_code == 422

    def test_too_long_description_returns_validation_error(self, client):
        """Description > 4096 chars returns 422 validation error."""
        resp = client.post(
            "/api/v1/ai/skills/ai-create",
            json={"description": "x" * 4097},
        )
        assert resp.status_code == 422

    @patch("apps.backend.app.routers.ai_skills.httpx.AsyncClient")
    def test_agent_timeout_returns_error(self, mock_httpx_cls, client):
        """Agent service timeout returns error."""
        import httpx

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        resp = client.post(
            "/api/v1/ai/skills/ai-create",
            json={"description": "Create a skill"},
        )
        assert resp.status_code in (500, 504)

    @patch("apps.backend.app.routers.ai_skills.httpx.AsyncClient")
    def test_malformed_content_still_returned(self, mock_httpx_cls, client):
        """Agent returns content without frontmatter — still returned with null parsed fields."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": "Just plain text without frontmatter"}

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        resp = client.post(
            "/api/v1/ai/skills/ai-create",
            json={"description": "Create something"},
        )

        assert resp.status_code == 200
        data = _unwrap(resp)
        assert data["content"] == "Just plain text without frontmatter"
        assert data["parsed_name"] is None
        assert data["parsed_description"] is None

    @patch("apps.backend.app.routers.ai_skills.httpx.AsyncClient")
    def test_agent_returns_504(self, mock_httpx_cls, client):
        """Agent returns 504 — translated to error response."""
        mock_resp = MagicMock()
        mock_resp.status_code = 504
        mock_resp.text = "DeerFlow dispatch timed out"

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        resp = client.post(
            "/api/v1/ai/skills/ai-create",
            json={"description": "Create a skill"},
        )
        assert resp.status_code in (500, 504)


class TestRawSkillSaveEndpoint:
    @patch("apps.backend.app.routers.ai_skills.workspace")
    def test_save_raw_skill_with_frontmatter(self, mock_ws, client, mock_db):
        """Saving AI-generated raw content preserves SKILL.md structure."""
        mock_ws.skills_custom_dir.return_value = MagicMock(
            resolve=lambda: Path("/tmp/ws")
        )
        mock_ws.create_custom_skill.return_value = MagicMock()

        resp = client.post(
            "/api/v1/ai/skills/custom/raw",
            json={
                "skill_id": "expense-tracker",
                "content": "---\nname: expense-tracker\ndescription: Track expenses\n---\n## When to Use\nWhen asked about spending.\n## Instructions\nAnalyze patterns.",
                "icon": "📊",
                "color": "#007aff",
            },
        )

        assert resp.status_code == 200
        data = _unwrap(resp)
        assert data["name"] == "expense-tracker"
        assert data["description"] == "Track expenses"

        # Verify creation_type='ai_created'
        add_call = mock_db.add.call_args[0][0]
        assert add_call.creation_type == "ai_created"

    def test_duplicate_skill_id_rejected(self, client, mock_db):
        """Duplicate skill_id for same family returns error."""
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

        resp = client.post(
            "/api/v1/ai/skills/custom/raw",
            json={
                "skill_id": "expense-tracker",
                "content": "---\nname: expense-tracker\n---\nContent",
                "icon": "📊",
                "color": "#007aff",
            },
        )
        assert resp.status_code in (400, 409, 422, 503)

    def test_internal_skill_id_rejected(self, client):
        """skill_id matching internal-only skills is rejected."""
        resp = client.post(
            "/api/v1/ai/skills/custom/raw",
            json={
                "skill_id": "skill-creator",
                "content": "---\nname: skill-creator\n---\nContent",
                "icon": "⚡",
                "color": "#007aff",
            },
        )
        assert resp.status_code == 422

    def test_builtin_skill_id_rejected(self, client):
        """skill_id matching builtin/reserved capabilities is rejected."""
        # "report" was removed in the two-ai-apps refactor; use a current
        # RESERVED_NAMES entry (finance-coach) to verify the rejection logic.
        resp = client.post(
            "/api/v1/ai/skills/custom/raw",
            json={
                "skill_id": "finance-coach",
                "content": "---\nname: finance-coach\n---\nContent",
                "icon": "⚡",
                "color": "#007aff",
            },
        )
        assert resp.status_code == 422

    @patch("apps.backend.app.routers.ai_skills.workspace")
    def test_filesystem_failure_deletes_db_record(self, mock_workspace, client, mock_db):
        """P1: Raw save filesystem write failure triggers compensating DB delete."""
        # Simulate filesystem write failure
        mock_workspace.create_custom_skill.side_effect = OSError("disk full")

        resp = client.post(
            "/api/v1/ai/skills/custom/raw",
            json={
                "skill_id": "expense-tracker",
                "content": "---\nname: expense-tracker\n---\nContent",
                "icon": "📊",
                "color": "#007aff",
            },
        )

        # Should return error
        assert resp.status_code in (500, 503)

        # Verify DB delete was called as compensation
        assert mock_db.delete.called
        assert mock_db.commit.call_count >= 2  # One for add, one for delete

    def test_content_exceeds_64kb_rejected(self, client):
        """P2: Content exceeding 64KB limit is rejected."""
        large_content = "---\nname: large-skill\n---\n" + "x" * 66000
        resp = client.post(
            "/api/v1/ai/skills/custom/raw",
            json={
                "skill_id": "large-skill",
                "content": large_content,
                "icon": "📊",
                "color": "#007aff",
            },
        )
        assert resp.status_code == 422
