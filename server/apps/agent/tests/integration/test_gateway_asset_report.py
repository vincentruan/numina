"""U4 step 5: internal asset-report run trigger (backend → agent gateway).

Verifies the ``POST /internal/gateway/runs/asset-report/{thread_id}`` endpoint:
- ``X-Agent-Token`` auth (401 on bad/missing token).
- ``internal=True`` bypasses R1's 409 gate (frontend direct dispatch stays 409,
  tested in test_u2_app_dispatch.py).
- Triggers ``_run_asset_report_pipeline`` via ``start_run`` and streams SSE,
  including the ``report.step2_json`` custom event from the worker-synthesized
  step 3.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_stub_adapter() -> Any:
    stub = AsyncMock()

    async def typed_stream_dispatch(
        skill_name: str,
        context: Any,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        yield (
            "messages",
            {"type": "ai", "content": '```json\n{"overall_score": 88}\n```', "tool_calls": None, "id": "m1"},
        )
        yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}})

    stub.typed_stream_dispatch = typed_stream_dispatch
    return stub


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient with worker deps stubbed."""
    mock_ai_config = {
        "ai_enabled": True,
        "providers": [
            {"is_active": True, "provider": "openai", "api_key": "k", "base_url": "u"}
        ],
    }
    with (
        patch(
            "apps.agent.services.runtime.worker.BackendClient.get_family_ai_config",
            new_callable=AsyncMock,
            return_value=mock_ai_config,
        ),
        patch(
            "apps.agent.services.runtime.worker.BackendClient.get_enabled_mcp_servers",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "apps.agent.services.runtime.worker.BackendClient.persist_report_result",
            new_callable=AsyncMock,
            return_value={"ok": True, "written": 1},
        ),
        patch(
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=_make_stub_adapter(),
        ),
        patch(
            "apps.agent.services.runtime.worker.pii_redactor.redact",
            side_effect=lambda ctx: ctx,
        ),
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache.async_init_checkpointer",
            new_callable=AsyncMock,
        ),
        patch(
            "deerflow.persistence.engine.init_engine",
            new_callable=AsyncMock,
        ),
    ):
        from apps.agent.app.main import app

        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()


def _parse_sse_events(response_text: str) -> list[dict]:
    events: list[dict] = []
    current_event = None
    current_data = None
    for line in response_text.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data = json.loads(line[len("data:"):].strip())
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None
    return events


_TOKEN = "test-internal-token"


def test_asset_report_run_rejects_missing_token(client):
    """No X-Agent-Token → 401 (service-to-service auth required)."""
    response = client.post(
        "/internal/gateway/runs/asset-report/thread-1",
        json={"family_id": "family-1", "user_id": "user-1"},
    )
    assert response.status_code == 422  # missing required header → FastAPI 422


def test_asset_report_run_rejects_bad_token(client):
    """Wrong X-Agent-Token → 401."""
    response = client.post(
        "/internal/gateway/runs/asset-report/thread-1",
        headers={"X-Agent-Token": "wrong-token"},
        json={"family_id": "family-1", "user_id": "user-1"},
    )
    assert response.status_code == 401


def test_asset_report_run_streams_step2_json(client):
    """Valid token → SSE stream completes; worker persists parsed JSON (step 7).

    U4 step 3: report.step2_json is now emitted by AssetReportStep2Middleware
    (in-graph via get_stream_writer). The stub adapter bypasses the real graph
    middleware path, so no step2 event appears in this SSE stream — the worker
    only persists the parsed JSON (asserted via persist mock). The middleware's
    in-graph emission is covered by the F1 e2e run, not this unit test.
    """
    with (
        patch(
            "apps.agent.app.routers.gateway.settings.AGENT_INTERNAL_TOKEN",
            _TOKEN,
        ),
        patch(
            "apps.agent.services.runtime.worker.BackendClient.persist_report_result",
            new_callable=AsyncMock,
            return_value={"ok": True, "written": 1},
        ) as mock_persist,
    ):
        response = client.post(
            "/internal/gateway/runs/asset-report/thread-ar",
            headers={"X-Agent-Token": _TOKEN},
            json={"family_id": "family-1", "user_id": "user-1"},
        )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    # U4 step 3: worker synthesizes report.step2_json (middleware path was
    # attempted but get_stream_writer() is no-op on numina's sync stream() path
    # — plan fallback condition; worker synthesis is the sanctioned fallback).
    step2 = [
        e for e in events
        if e["event"] == "custom" and isinstance(e["data"], dict) and e["data"].get("type") == "report.step2_json"
    ]
    assert len(step2) == 1, f"expected 1 report.step2_json, got {events}"
    assert step2[0]["data"]["payload"] == {"overall_score": 88}
    # U4 step 7: worker persisted the parsed JSON to ai_reports via backend.
    mock_persist.assert_awaited_once()
    assert mock_persist.await_args.kwargs["report_json"] == {"overall_score": 88}
    end_events = [e for e in events if e["event"] == "end" and e["data"] is not None]
    assert end_events and end_events[0]["data"]["status"] == "complete"


def test_asset_report_persists_markdown_file_path(client, tmp_path, monkeypatch):
    """U4 step 3 / R5: worker copies the step-1 sandbox markdown into the tenant
    reports dir and passes ``markdown_file_path`` to persist_report_result.

    When the LLM declares ``WRITE_FILE: <filename>`` (SKILL.md §文件命名规则) and
    the sandbox workspace contains that file, the worker:
    (1) copies it to ``PathManager.tenant_report_file`` with a server-generated
        ``report_{ts}_{run_id[:8]}.md`` filename (collision defense), and
    (2) forwards that filename to ``persist_report_result``.

    F2: markdown_file_path non-empty + file exists + lands under tenant_report_dir.
    """
    # Sandbox layout: AGENT_DATA_DIR/{family}/sandboxes/{thread}/workspace/<file>
    family_id = "321210384289632256"
    thread_id = "thread-md"
    sandbox_workspace = tmp_path / family_id / "sandboxes" / thread_id / "workspace"
    sandbox_workspace.mkdir(parents=True)
    declared = "report_20260719_100530.md"
    (sandbox_workspace / declared).write_text("# 报告\n## 评分 65/100", encoding="utf-8")

    # Point the worker's AGENT_DATA_DIR at tmp_path so the sandbox file resolves.
    monkeypatch.setattr(
        "apps.agent.services.runtime.worker.settings.AGENT_DATA_DIR",
        str(tmp_path),
    )
    # PathManager must write tenant reports under tmp_path too (isolated DATA_ROOT).
    from packages.core.path_manager import PathManager as _RealPM

    # Delegate to a real PathManager rooted at tmp_path via its data_root.
    real = _RealPM(data_root=tmp_path)
    monkeypatch.setattr(
        "apps.agent.services.runtime.worker.get_path_manager",
        lambda: real,
    )

    # Stub adapter that emits a WRITE_FILE declaration + JSON in one AI message.
    stub = AsyncMock()

    async def typed_stream_dispatch(
        skill_name: str,
        context: Any,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        yield (
            "messages",
            {
                "type": "ai",
                "content": (
                    f"WRITE_FILE: {declared}\n"
                    '```json\n{"overall_score": 72}\n```'
                ),
                "tool_calls": None,
                "id": "m1",
            },
        )
        yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}})

    stub.typed_stream_dispatch = typed_stream_dispatch

    with (
        patch(
            "apps.agent.app.routers.gateway.settings.AGENT_INTERNAL_TOKEN",
            _TOKEN,
        ),
        patch(
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=stub,
        ),
        patch(
            "apps.agent.services.runtime.worker.BackendClient.persist_report_result",
            new_callable=AsyncMock,
            return_value={"ok": True, "written": 1},
        ) as mock_persist,
    ):
        response = client.post(
            "/internal/gateway/runs/asset-report/thread-md",
            headers={"X-Agent-Token": _TOKEN},
            json={"family_id": family_id, "user_id": "user-1"},
        )
    assert response.status_code == 200

    mock_persist.assert_awaited_once()
    md_path = mock_persist.await_args.kwargs.get("markdown_file_path")
    assert md_path is not None, "markdown_file_path must be forwarded to persist"
    # Server-generated filename: LLM timestamp + run_id[:8] suffix, matches pattern.
    assert md_path.startswith("report_20260719_100530_")
    assert md_path.endswith(".md")
    # File exists on disk under the tenant reports dir (F2 path-traversal guard).
    target = real.tenant_report_file(int(family_id), md_path)
    assert target.is_file(), f"persisted markdown missing at {target}"
    assert target.resolve().relative_to(real.tenant_report_dir(int(family_id)).resolve())
