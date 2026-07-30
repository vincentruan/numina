"""Tests for import_parse router (U8).

U8 (Resolved-10): import_parse is refactored from ``orchestrator.dispatch`` to
a stream_run agent (``app="import-parse"``). The router runs
``_run_import_parse_agent`` inline and harvests the ``import-parse.result``
custom event to return sync JSON ``{source, report_date, items}`` (frontend
contract preserved). These tests stub the worker function so no real LLM runs.
"""
from unittest.mock import AsyncMock, patch

import pytest

from packages.core.settings import settings as _core_settings
from packages.security.service_auth.agent_jwt import create_agent_token

_core_settings.SECRET_KEY = "test-secret-key-for-jwt-tests"
VALID_TOKEN = create_agent_token("fam1")


async def _fake_run_publishing_result(payload: dict) -> AsyncMock:
    """Return an AsyncMock for _run_import_parse_agent that publishes the given
    payload as an ``import-parse.result`` custom event on the bridge (mirrors
    what the real worker emits on a successful parse)."""

    async def _fake(*, bridge, run_manager, record, family_id, user_id, thread_id, graph_input, config):
        await bridge.publish(record.run_id, "metadata", {"run_id": record.run_id})
        await bridge.publish(record.run_id, "custom", {"type": "import-parse.result", "payload": payload})
        await bridge.publish(record.run_id, "end", {"status": "complete"})
        await bridge.publish_end(record.run_id)

    return AsyncMock(side_effect=_fake)


@pytest.mark.asyncio
async def test_parse_returns_structured_items():
    from fastapi.testclient import TestClient

    from apps.agent.app.main import app

    mock_payload = {
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
        "apps.agent.routers.import_parse._run_import_parse_agent",
        new=await _fake_run_publishing_result(mock_payload),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "贵州茅台 600519 100股 市值158000元"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "华泰证券"
    assert data["items"][0]["name"] == "贵州茅台"
    assert data["items"][0]["current_value"] == 158000.0


def test_parse_rejects_invalid_token():
    from fastapi.testclient import TestClient

    from apps.agent.app.main import app

    client = TestClient(app)
    resp = client.post(
        "/import/parse",
        json={"text": "some text"},
        headers={"X-Agent-Token": "wrong", "X-Family-Id": "fam1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_parse_returns_empty_items_when_llm_finds_nothing():
    """When the agent emits no import-parse.result event (LLM found nothing
    parseable), the router returns the empty-result fallback (items=[])."""
    from fastapi.testclient import TestClient

    from apps.agent.app.main import app

    async def _fake_no_result(*, bridge, run_manager, record, family_id, user_id, thread_id, graph_input, config):
        await bridge.publish(record.run_id, "metadata", {"run_id": record.run_id})
        # No import-parse.result event — LLM produced no parseable JSON.
        await bridge.publish(record.run_id, "end", {"status": "complete"})
        await bridge.publish_end(record.run_id)

    with patch(
        "apps.agent.routers.import_parse._run_import_parse_agent",
        new=AsyncMock(side_effect=_fake_no_result),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "这不是金融文档"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["source"] == ""


@pytest.mark.asyncio
async def test_parse_returns_empty_result_on_agent_exception():
    """If the agent run raises, the router returns the empty-result fallback
    rather than propagating (mirrors the old import_parse_service contract)."""
    from fastapi.testclient import TestClient

    from apps.agent.app.main import app

    with patch(
        "apps.agent.routers.import_parse._run_import_parse_agent",
        new=AsyncMock(side_effect=RuntimeError("LLM blew up")),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "贵州茅台 100股"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_parse_times_out_and_returns_empty_result():
    """P2 #14: a hanging agent run is bounded by IMPORT_PARSE_TIMEOUT_SECONDS.

    When ``_run_import_parse_agent`` exceeds the timeout, the router returns the
    empty-result fallback — instead of hanging forever and leaving an orphaned
    run after the backend's 120s httpx timeout disconnects. The timeout cancels
    the agent coroutine (``asyncio.timeout`` raises ``TimeoutError``); the
    router maps that to the empty-result contract.
    """
    import asyncio as _asyncio

    from fastapi.testclient import TestClient

    from apps.agent.app.main import app

    async def _fake_hang(*, bridge, run_manager, record, family_id, user_id, thread_id, graph_input, config):
        # Simulate a hanging LLM call: sleep well past the (patched) timeout.
        # The router's ``asyncio.timeout`` cancels this coroutine.
        await _asyncio.sleep(30)

    with patch(
        "apps.agent.routers.import_parse._run_import_parse_agent",
        new=AsyncMock(side_effect=_fake_hang),
    ), patch(
        "apps.agent.app.config.settings.IMPORT_PARSE_TIMEOUT_SECONDS", 0.05
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={"text": "贵州茅台 100股"},
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_parse_with_image_paths_injects_view_image_hint_and_reuses_thread_id():
    """C 方案（vision）：backend 传 thread_id + image_paths 时，agent router
    复用该 thread_id（PNG 已落其沙箱 uploads/）并把 image_paths 提示注入
    user message（引导 LLM 先 view_image 读图）。"""
    from fastapi.testclient import TestClient

    from apps.agent.app.main import app

    captured: dict = {}

    async def _fake_capture(*, bridge, run_manager, record, family_id, user_id, thread_id, graph_input, config):
        captured["thread_id"] = thread_id
        captured["content"] = graph_input["messages"][-1]["content"]
        await bridge.publish(record.run_id, "custom", {
            "type": "import-parse.result",
            "payload": {"source": "", "report_date": None, "items": []},
        })
        await bridge.publish(record.run_id, "end", {"status": "complete"})

    supplied_thread_id = "importparse-thread-supplied123"
    with patch(
        "apps.agent.routers.import_parse._run_import_parse_agent",
        new=AsyncMock(side_effect=_fake_capture),
    ):
        client = TestClient(app)
        resp = client.post(
            "/import/parse",
            json={
                "text": "文档文本",
                "thread_id": supplied_thread_id,
                "image_paths": ["/mnt/user-data/uploads/page_1.png"],
            },
            headers={"X-Agent-Token": VALID_TOKEN, "X-Family-Id": "fam1"},
        )
    assert resp.status_code == 200
    # thread_id 复用 backend 传入的（沙箱 PNG 已落该 thread）
    assert captured["thread_id"] == supplied_thread_id
    # image_paths 提示注入 user message
    assert "/mnt/user-data/uploads/page_1.png" in captured["content"]
    assert "view_image" in captured["content"]
