"""U2: multi-app dispatch + R1 allowlist gate.

Verifies the ``app`` field in ``body.metadata`` is validated server-side in
``sse_gateway.start_run`` and propagated to ``record.metadata``:

- ``numina`` (default): accepted, dispatches to ``_run_numina_agent``.
- ``asset-report``: rejected with 409 (must enter via trigger endpoint so
  require_owner + require_ai_enabled + concurrency gating apply — R1 Finding 1).
- ``import-parse``: rejected with 400 (U8 will wire owner/member auth in
  lockstep with widening the allowlist — no U2→U8 trust-boundary window).
- unknown value: rejected with 400.

Also verifies the worker dispatch entry point (``run_agent``) routes to the
correct per-app runner and that the placeholder branches publish a 503-style
error rather than crashing (Finding 15).
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token


# ---------------------------------------------------------------------------
# Stub adapter — yields a minimal frames sequence so numina dispatch completes
# ---------------------------------------------------------------------------


def _make_stub_adapter() -> Any:
    stub = AsyncMock()

    async def typed_stream_dispatch(
        skill_name: str,
        context: Any,
        thread_id: str,
        enable_thinking: bool = False,
        subagent_enabled: bool | None = None,
        plan_mode: bool | None = None,
        resume_answer: str | None = None,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        yield (
            "messages",
            {"type": "ai", "content": "hello", "tool_calls": None, "id": "m1"},
        )
        yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}})

    stub.typed_stream_dispatch = typed_stream_dispatch
    return stub


@pytest.fixture(scope="module")
def client():
    """Module-scoped FastAPI TestClient with worker deps stubbed."""
    mock_ai_config = {
        "ai_enabled": True,
        "providers": [
            {
                "is_active": True,
                "provider": "openai",
                "api_key": "test-key",
                "base_url": "http://localhost:11434/v1",
            }
        ],
        "ai_model_id": "gpt-4o-mini",
    }
    with (
        patch(
            "apps.agent.services.runtime.worker.BackendClient.get_family_ai_config",
            new_callable=AsyncMock,
            return_value=mock_ai_config,
        ),
        patch(
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=_make_stub_adapter(),
        ),
        patch(
            "apps.agent.services.runtime.worker.generate_suggestions",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "apps.agent.services.runtime.worker.sync_title_from_checkpoint",
            new_callable=AsyncMock,
            return_value=None,
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

        app.dependency_overrides[verify_family_token] = lambda: VerifiedFamily(
            family_id="family-1", user_id="user-1", role="member"
        )
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


# ---------------------------------------------------------------------------
# R1 allowlist gate (start_run rejects disallowed app values before dispatch)
# ---------------------------------------------------------------------------


def test_app_asset_report_rejected_with_409(client):
    """app='asset-report' must not be accepted via /runs/stream direct."""
    response = client.post(
        "/api/threads/u2-asset-report/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "metadata": {"app": "asset-report"},
        },
    )
    assert response.status_code == 409
    assert "asset-report" in response.json()["detail"]


def test_app_import_parse_rejected_with_400(client):
    """app='import-parse' rejected with 400 until U8 wires its auth (lockstep)."""
    response = client.post(
        "/api/threads/u2-import-parse/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "metadata": {"app": "import-parse"},
        },
    )
    assert response.status_code == 400
    assert "import-parse" in response.json()["detail"]


def test_app_unknown_value_rejected_with_400(client):
    """Unknown app value rejected with 400."""
    response = client.post(
        "/api/threads/u2-unknown/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "metadata": {"app": "bogus-app"},
        },
    )
    assert response.status_code == 400


def test_app_numina_accepted_and_completes(client):
    """app='numina' (explicit) is accepted and the run completes."""
    response = client.post(
        "/api/threads/u2-numina/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "metadata": {"app": "numina"},
        },
    )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    end_events = [e for e in events if e["event"] == "end" and e["data"] is not None]
    assert end_events, f"no data-bearing end event: {events}"
    assert end_events[0]["data"]["status"] == "complete"


def test_app_defaults_to_numina_when_absent(client):
    """No app field → defaults to numina, run completes."""
    response = client.post(
        "/api/threads/u2-default/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={"input": {"messages": [{"role": "user", "content": "hi"}]}},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Worker dispatch: run_agent routes by record.metadata["app"]
# ---------------------------------------------------------------------------


async def _make_record(app: str | None) -> Any:
    """Build a minimal RunRecord-like object with metadata."""
    from types import SimpleNamespace

    metadata = {"family_id": "family-1", "user_id": "user-1"}
    if app is not None:
        metadata["app"] = app
    return SimpleNamespace(
        run_id=f"run-{app or 'default'}",
        metadata=metadata,
        abort_event=SimpleNamespace(is_set=lambda: False),
        status=None,
    )


class _FakeBridge:
    def __init__(self) -> None:
        self.published: list[tuple[str, Any]] = []

    async def publish(self, run_id: str, event: str, data: Any) -> None:
        self.published.append((event, data))

    async def publish_end(self, run_id: str) -> None:
        self.published.append(("__end_sentinel__", None))

    async def cleanup(self, run_id: str, delay: float = 0) -> None:
        pass


class _FakeRunManager:
    def __init__(self) -> None:
        self.status: list[tuple[str, str]] = []

    async def set_status(self, run_id: str, status: Any, **kw: Any) -> None:
        self.status.append((run_id, getattr(status, "value", str(status))))


async def test_run_agent_dispatches_asset_report_to_pipeline():
    """app='asset-report' → _run_asset_report_pipeline runs the 3-step pipeline.

    U4: the 503 placeholder is replaced by a real adapter stream. Stubs the
    adapter to yield an AI message with a fenced JSON block (step 2 output),
    then verifies the worker forwards frames, emits exactly one
    ``report.step2_json`` custom event (worker-synthesized step 3), and
    completes with status='complete'.
    """
    from apps.agent.services.runtime.worker import run_agent

    async def _stub_stream(skill_name, context, thread_id, enable_thinking=False):
        yield ("messages", {"type": "ai", "content": '```json\n{"overall_score": 72}\n```', "tool_calls": None, "id": "m1"})
        yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}})

    stub_adapter = AsyncMock()
    stub_adapter.typed_stream_dispatch = _stub_stream

    mock_ai_config = {
        "ai_enabled": True,
        "providers": [{"is_active": True, "provider": "openai", "api_key": "k", "base_url": "u"}],
    }
    with (
        patch("apps.agent.services.runtime.worker.BackendClient.get_family_ai_config", new_callable=AsyncMock, return_value=mock_ai_config),
        patch("apps.agent.services.runtime.worker.BackendClient.get_enabled_mcp_servers", new_callable=AsyncMock, return_value=[]),
        patch("apps.agent.services.runtime.worker.create_family_adapter", return_value=stub_adapter),
        patch("apps.agent.services.runtime.worker.pii_redactor.redact", side_effect=lambda ctx: ctx),
    ):
        record = await _make_record("asset-report")
        bridge = _FakeBridge()
        rm = _FakeRunManager()
        await run_agent(
            bridge=bridge,  # type: ignore[arg-type]
            run_manager=rm,  # type: ignore[arg-type]
            record=record,
            family_id="family-1",
            user_id="user-1",
            thread_id="thread-ar",
            graph_input=None,
            config={},
        )

    # No error event (pipeline completed cleanly)
    error_events = [d for ev, d in bridge.published if ev == "error"]
    assert not error_events, f"unexpected error event: {error_events}"

    # report.step2_json custom event emitted exactly once with parsed JSON
    step2 = [d for ev, d in bridge.published if ev == "custom" and isinstance(d, dict) and d.get("type") == "report.step2_json"]
    assert len(step2) == 1, f"expected 1 report.step2_json, got {len(step2)}: {bridge.published}"
    assert step2[0]["payload"] == {"overall_score": 72}

    # end frame status = complete
    end_events = [d for ev, d in bridge.published if ev == "end" and d is not None]
    assert end_events and end_events[0]["status"] == "complete", bridge.published


async def test_run_agent_asset_report_no_json_skips_step2_event():
    """If the AI output has no parseable JSON, no report.step2_json is emitted (F8)."""
    from apps.agent.services.runtime.worker import run_agent

    async def _stub_stream(skill_name, context, thread_id, enable_thinking=False):
        yield ("messages", {"type": "ai", "content": "no json here", "tool_calls": None, "id": "m1"})
        yield ("end", {})

    stub_adapter = AsyncMock()
    stub_adapter.typed_stream_dispatch = _stub_stream

    mock_ai_config = {"ai_enabled": True, "providers": [{"is_active": True, "provider": "openai", "api_key": "k", "base_url": "u"}]}
    with (
        patch("apps.agent.services.runtime.worker.BackendClient.get_family_ai_config", new_callable=AsyncMock, return_value=mock_ai_config),
        patch("apps.agent.services.runtime.worker.BackendClient.get_enabled_mcp_servers", new_callable=AsyncMock, return_value=[]),
        patch("apps.agent.services.runtime.worker.create_family_adapter", return_value=stub_adapter),
        patch("apps.agent.services.runtime.worker.pii_redactor.redact", side_effect=lambda ctx: ctx),
    ):
        record = await _make_record("asset-report")
        bridge = _FakeBridge()
        rm = _FakeRunManager()
        await run_agent(
            bridge=bridge,  # type: ignore[arg-type]
            run_manager=rm,  # type: ignore[arg-type]
            record=record,
            family_id="family-1",
            user_id="user-1",
            thread_id="thread-ar2",
            graph_input=None,
            config={},
        )

    step2 = [d for ev, d in bridge.published if ev == "custom" and isinstance(d, dict) and d.get("type") == "report.step2_json"]
    assert step2 == [], f"expected no report.step2_json for non-JSON output: {step2}"


async def test_run_agent_dispatches_import_parse_to_503_placeholder():
    """app='import-parse' → _run_import_parse_agent publishes a 503-style error."""
    from apps.agent.services.runtime.worker import run_agent

    record = await _make_record("import-parse")
    bridge = _FakeBridge()
    rm = _FakeRunManager()

    await run_agent(
        bridge=bridge,  # type: ignore[arg-type]
        run_manager=rm,  # type: ignore[arg-type]
        record=record,
        family_id="family-1",
        user_id="user-1",
        thread_id="thread-ip",
        graph_input=None,
        config={},
    )

    error_events = [d for ev, d in bridge.published if ev == "error"]
    assert error_events, f"no error event published: {bridge.published}"
    assert "import-parse" in error_events[0]["message"]
    assert "U8" in error_events[0]["message"]


async def test_run_agent_sets_family_sandbox_context_before_dispatch():
    """Resolved-3 blocker A: set_family_sandbox_context called with family_id."""
    from apps.agent.services.runtime import worker

    record = await _make_record("import-parse")  # placeholder path, no real LLM
    bridge = _FakeBridge()
    rm = _FakeRunManager()

    with patch(
        "apps.agent.services.runtime.worker.set_family_sandbox_context"
    ) as mock_set:
        await worker.run_agent(
            bridge=bridge,  # type: ignore[arg-type]
            run_manager=rm,  # type: ignore[arg-type]
            record=record,
            family_id="family-42",
            user_id="user-1",
            thread_id="thread-sbx",
            graph_input=None,
            config={},
        )
        mock_set.assert_called_once_with("family-42")


async def test_config_yaml_uses_numina_sandbox_provider():
    """Resolved-3 blocker B: base config.yaml sandbox.use = NuminaLocalSandboxProvider."""
    from pathlib import Path

    import yaml

    config_path = Path(__file__).resolve().parents[4] / (
        "apps/agent/deerflow_config/base/config.yaml"
    )
    config = yaml.safe_load(config_path.read_text())
    assert (
        config["sandbox"]["use"]
        == "apps.agent.services.runtime.sandbox_provider:NuminaLocalSandboxProvider"
    ), config["sandbox"]["use"]
