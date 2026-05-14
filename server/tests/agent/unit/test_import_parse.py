"""Tests for import_parse router."""
from unittest.mock import AsyncMock, patch

import pytest


VALID_TOKEN = "test-token"


@pytest.fixture(autouse=True)
def patch_token(monkeypatch):
    monkeypatch.setenv("AGENT_INTERNAL_TOKEN", VALID_TOKEN)
    # Also patch the already-instantiated settings singleton — monkeypatch.setenv
    # alone doesn't affect it because pydantic-settings reads env vars at init time.
    with patch("apps.agent.app.config.settings.AGENT_INTERNAL_TOKEN", VALID_TOKEN):
        yield


def test_parse_returns_structured_items():
    from apps.agent.app.main import app
    from fastapi.testclient import TestClient

    mock_response = {
        "source": "华泰证券",
        "report_date": "2026-04-01",
        "items": [
            {
                "name": "贵州茅台",
                "asset_type": "financial",
                "category_hint": "股票",
                "current_value": 158000.0,
                "currency": "CNY",
                "quantity": 100,
            }
        ],
    }
    with patch(
        "apps.agent.routers.import_parse.orchestrator.dispatch",
        new=AsyncMock(return_value=type("R", (), {"model_dump": lambda self: mock_response})()),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "贵州茅台 600519 100股 市值158000元"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["name"] == "贵州茅台"
    assert data["items"][0]["current_value"] == 158000.0


def test_parse_rejects_invalid_token():
    from apps.agent.app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post(
        "/import/parse",
        json={"text": "some text"},
        headers={"X-Agent-Token": "wrong", "X-Family-Id": "fam1"},
    )
    assert resp.status_code == 401


def test_parse_returns_empty_items_when_llm_finds_nothing():
    from apps.agent.app.main import app
    from fastapi.testclient import TestClient

    empty_response = {"source": "", "report_date": None, "items": []}
    with patch(
        "apps.agent.routers.import_parse.orchestrator.dispatch",
        new=AsyncMock(return_value=type("R", (), {"model_dump": lambda self: empty_response})()),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "这不是金融文档"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_orchestrator_import_parse_capability():
    from apps.agent.services.orchestrator import orchestrator
    from unittest.mock import AsyncMock, patch

    mock_result = {
        "source": "华泰证券",
        "report_date": "2026-04-01",
        "items": [{"name": "贵州茅台", "asset_type": "financial", "category_hint": "股票", "current_value": 158000.0, "currency": "CNY", "quantity": 100}],
    }
    with patch("apps.agent.services.import_parse_service.parse_holdings_from_text", new=AsyncMock(return_value=mock_result)):
        result = await orchestrator.dispatch(
            capability="import_parse",
            family_id="fam1",
            user_id="user1",
            free_text='{"text": "贵州茅台 100股"}',
        )
    assert hasattr(result, "model_dump")
    data = result.model_dump()
    assert "summary" in data or "items" in data or data.get("capability") == "import_parse"
