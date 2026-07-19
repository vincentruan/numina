"""finance-coach gateway route + R1 allowlist integration (Plan A T5).

Verifies the ``POST /internal/gateway/runs/finance-coach/{thread_id}`` endpoint
mirrors the asset-report trigger, and that R1 rejects direct frontend dispatch
of ``app="finance-coach"`` with 409 (must enter via the backend
/ai/finance-coach/generate endpoint — Plan A).

Style matches ``test_gateway_asset_report.py`` (sync ``TestClient``) and
``test_u2_app_dispatch.py`` (R1 409/400 gate via /api/threads/.../runs/stream).
The brief's ``/internal/gateway/runs/stream`` path does not exist — the
frontend-facing dispatch route is ``/api/threads/{thread_id}/runs/stream`` in
``apps/agent/routers/runs_stream.py`` (uses ``verify_family_token`` + the
``X-Family-Id`` header, not ``X-Agent-Token``). R1 is enforced inside
``start_run``, which both routes invoke, so the 409/400 behavior is identical.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token


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
    """Module-scoped TestClient with worker deps stubbed (mirrors
    test_gateway_asset_report.py + test_u2_app_dispatch.py)."""
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
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=_make_stub_adapter(),
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

        # verify_family_token override so /api/threads/.../runs/stream accepts
        # the request without a real JWT (mirrors test_u2_app_dispatch.py).
        app.dependency_overrides[verify_family_token] = lambda: VerifiedFamily(
            family_id="family-1", user_id="user-1", role="member"
        )
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()


_TOKEN = "test-internal-token"


def test_finance_coach_route_requires_agent_token(client):
    """Without X-Agent-Token, the finance-coach route 422s (missing required
    header — matches the asset-report route's behavior)."""
    with patch(
        "apps.agent.app.routers.gateway.settings.AGENT_INTERNAL_TOKEN",
        _TOKEN,
    ):
        resp = client.post(
            "/internal/gateway/runs/finance-coach/some-thread",
            json={"family_id": "family-1"},
        )
    assert resp.status_code in (401, 422)


def test_r1_rejects_direct_finance_coach_dispatch(client):
    """Frontend direct dispatch with app=finance-coach is rejected (409) by R1.

    Mirrors the import-parse / asset-report R1 gate — finance-coach must be
    entered via the backend /ai/finance-coach/generate endpoint. Dispatched
    through /api/threads/{tid}/runs/stream (the real frontend route), which
    calls start_run → R1 gate.
    """
    resp = client.post(
        "/api/threads/t-direct/runs/stream",
        headers={"X-Family-Id": "family-1"},
        json={
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "metadata": {"app": "finance-coach"},
        },
    )
    assert resp.status_code == 409
    assert "finance-coach" in resp.text or "财务" in resp.text


def test_r1_rejects_unknown_app_still_400(client):
    """Unknown app values still 400 (regression guard for the allowlist edit)."""
    resp = client.post(
        "/api/threads/t-bogus/runs/stream",
        headers={"X-Family-Id": "family-1"},
        json={
            "input": {"messages": [{"role": "user", "content": "hi"}]},
            "metadata": {"app": "bogus-app"},
        },
    )
    assert resp.status_code == 400
