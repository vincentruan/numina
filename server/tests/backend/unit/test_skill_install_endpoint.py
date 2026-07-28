"""Tests for POST /ai/skills/install endpoint."""

import os
import sys
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
    monkeypatch.setenv("AGENT_INTERNAL_TOKEN", "test-token")
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


class TestInstallCLICommand:
    @patch("apps.backend.app.routers.ai_skills.SkillDownloader")
    @patch("apps.backend.app.routers.ai_skills.SkillCommandParser")
    def test_valid_cli_command_installs_skill(
        self, mock_parser_cls, mock_downloader_cls, client, mock_db
    ):
        """AE1: Valid CLI command installs skill with creation_type='cmd'."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            match_type="cli",
            provider="anthropics",
            skill_name="deploy-staging",
            repo_url=None,
            raw_input="npx skills add anthropics/deploy-staging",
        )
        mock_parser_cls.return_value = mock_parser

        mock_downloader = MagicMock()
        mock_downloader.download = AsyncMock(return_value=MagicMock(
            content="---\nname: deploy-staging\ndescription: Deploy to staging\n---\nInstructions",
            source_url="https://github.com/anthropics/deploy-staging",
            skill_id="deploy-staging",
        ))
        mock_downloader_cls.return_value = mock_downloader

        resp = client.post(
            "/api/v1/ai/skills/install",
            json={"command": "npx skills add anthropics/deploy-staging"},
        )

        assert resp.status_code == 200
        data = _unwrap(resp)
        assert data["id"] == "deploy-staging"
        assert data["name"] == "deploy-staging"
        assert data["skill_type"] == "custom"

        # Verify DB record was created with creation_type='cmd'
        add_call = mock_db.add.call_args[0][0]
        assert add_call.creation_type == "cmd"
        assert add_call.source_url == "https://github.com/anthropics/deploy-staging"


class TestInstallDuplicate:
    @patch("apps.backend.app.routers.ai_skills.SkillDownloader")
    @patch("apps.backend.app.routers.ai_skills.SkillCommandParser")
    def test_duplicate_skill_returns_error(
        self, mock_parser_cls, mock_downloader_cls, client, mock_db
    ):
        """AE5: Duplicate skill_id for same family returns error."""
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()

        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            match_type="cli",
            provider="anthropics",
            skill_name="deploy-staging",
            repo_url=None,
            raw_input="npx skills add anthropics/deploy-staging",
        )
        mock_parser_cls.return_value = mock_parser

        mock_downloader = MagicMock()
        mock_downloader.download = AsyncMock(return_value=MagicMock(
            content="---\nname: deploy-staging\n---\n",
            source_url="https://github.com/anthropics/deploy-staging",
            skill_id="deploy-staging",
        ))
        mock_downloader_cls.return_value = mock_downloader

        resp = client.post(
            "/api/v1/ai/skills/install",
            json={"command": "npx skills add anthropics/deploy-staging"},
        )

        assert resp.status_code in (400, 409, 422, 503)


class TestInstallAIFallback:
    @patch("apps.backend.app.routers.ai_skills.httpx.AsyncClient")
    @patch("apps.backend.app.routers.ai_skills.SkillCommandParser")
    def test_unmatched_input_triggers_ai_fallback(
        self, mock_parser_cls, mock_httpx_cls, client, mock_db
    ):
        """Unmatched input triggers AI fallback path via skill-installer."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            match_type="unmatched",
            provider=None,
            skill_name=None,
            repo_url=None,
            raw_input="curl -fsSL https://skills.sh/install.sh | sh",
        )
        mock_parser_cls.return_value = mock_parser

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": "---\nname: deploy-helper\ndescription: Deploy helper skill\n---\nInstructions"
        }

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_resp)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_cls.return_value = mock_client_instance

        resp = client.post(
            "/api/v1/ai/skills/install",
            json={"command": "curl -fsSL https://skills.sh/install.sh | sh"},
        )

        assert resp.status_code == 200
        data = _unwrap(resp)
        assert data["name"] == "deploy-helper"

        add_call = mock_db.add.call_args[0][0]
        assert add_call.creation_type == "cmd"
        assert add_call.source_url is None


class TestInstallDownloadFailure:
    @patch("apps.backend.app.routers.ai_skills.SkillDownloader")
    @patch("apps.backend.app.routers.ai_skills.SkillCommandParser")
    def test_download_failure_returns_error(
        self, mock_parser_cls, mock_downloader_cls, client, mock_db
    ):
        """Download failure returns error."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            match_type="cli",
            provider="anthropics",
            skill_name="missing-skill",
            repo_url=None,
            raw_input="npx skills add anthropics/missing-skill",
        )
        mock_parser_cls.return_value = mock_parser

        from apps.backend.app.services.skill_downloader import SkillDownloadError

        mock_downloader = MagicMock()
        mock_downloader.download = AsyncMock(side_effect=SkillDownloadError("HTTP 404"))
        mock_downloader_cls.return_value = mock_downloader

        resp = client.post(
            "/api/v1/ai/skills/install",
            json={"command": "npx skills add anthropics/missing-skill"},
        )

        assert resp.status_code in (500, 503)


class TestInstallFrontmatterFallback:
    @patch("apps.backend.app.routers.ai_skills.SkillDownloader")
    @patch("apps.backend.app.routers.ai_skills.SkillCommandParser")
    def test_missing_frontmatter_name_uses_skill_id(
        self, mock_parser_cls, mock_downloader_cls, client, mock_db
    ):
        """Downloaded content with no frontmatter name uses skill_id as fallback."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            match_type="url",
            provider="skills.sh",
            skill_name="my-skill",
            repo_url="https://skills.sh/v1/skills/my-skill",
            raw_input="https://skills.sh/v1/skills/my-skill",
        )
        mock_parser_cls.return_value = mock_parser

        mock_downloader = MagicMock()
        mock_downloader.download = AsyncMock(return_value=MagicMock(
            content="---\ndescription: A skill without name\n---\nBody",
            source_url="https://skills.sh/v1/skills/my-skill/SKILL.md",
            skill_id="my-skill",
        ))
        mock_downloader_cls.return_value = mock_downloader

        resp = client.post(
            "/api/v1/ai/skills/install",
            json={"command": "https://skills.sh/v1/skills/my-skill"},
        )

        assert resp.status_code == 200
        data = _unwrap(resp)
        assert data["name"] == "my-skill"  # Falls back to skill_id


class TestInstallFilesystemFailureCompensation:
    @patch("apps.backend.app.routers.ai_skills.SkillDownloader")
    @patch("apps.backend.app.routers.ai_skills.SkillCommandParser")
    @patch("apps.backend.app.routers.ai_skills.workspace")
    def test_filesystem_failure_deletes_db_record(
        self, mock_workspace, mock_parser_cls, mock_downloader_cls, client, mock_db
    ):
        """P1: Filesystem write failure triggers compensating DB delete."""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = MagicMock(
            match_type="url",
            provider="skills.sh",
            skill_name="test-skill",
            repo_url="https://skills.sh/v1/skills/test-skill",
            raw_input="https://skills.sh/v1/skills/test-skill",
        )
        mock_parser_cls.return_value = mock_parser

        mock_downloader = MagicMock()
        mock_downloader.download = AsyncMock(return_value=MagicMock(
            content="---\nname: test-skill\n---\nBody",
            source_url="https://skills.sh/v1/skills/test-skill/SKILL.md",
            skill_id="test-skill",
        ))
        mock_downloader_cls.return_value = mock_downloader

        # Simulate filesystem write failure
        mock_workspace.create_custom_skill.side_effect = IOError("disk full")

        resp = client.post(
            "/api/v1/ai/skills/install",
            json={"command": "https://skills.sh/v1/skills/test-skill"},
        )

        # Should return error
        assert resp.status_code in (500, 503)

        # Verify DB delete was called as compensation
        assert mock_db.delete.called
        assert mock_db.commit.call_count >= 2  # One for add, one for delete
