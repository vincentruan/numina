"""ContextVar tenant-isolation regression for ``POST /import/parse``.

``parse_import`` sets the family sandbox ContextVar directly (it bypasses
``worker.run_agent``, which would otherwise set it at dispatch entry) and must
reset it on *every* exit path via a ``finally`` block. A future regression
dropping the reset would leak ``family_id`` / caller into a reused coroutine or
executor thread (shared worker task), resolving sandbox paths to the wrong
tenant — and the existing import_parse tests stub the worker so the sandbox
provider never runs, leaving the suite green.

These tests pin the set/reset bracket by spying on
``set_family_sandbox_context`` / ``reset_family_sandbox_context`` (the endpoint
re-imports them fresh from ``sandbox_provider`` at call time, so patching the
module attribute is visible to the endpoint) and asserting that the reset fires
exactly once per request across the success, exception, and timeout exit paths,
and that the family_id the agent observes mid-run matches the request's
``X-Family-Id`` header (proving the set precedes the agent run).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from packages.core.settings import settings as _core_settings
from packages.security.service_auth.agent_jwt import create_agent_token

_core_settings.SECRET_KEY = "test-secret-key-for-jwt-tests"


def _client_with_stubbed_worker(agent_run: Any):
    """Build a TestClient with worker deps stubbed.

    ``agent_run`` is the AsyncMock used in place of ``_run_import_parse_agent``.
    Mirrors the fixture shape in ``test_gateway_finance_coach.py``.
    """
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
            "apps.agent.services.deerflow_adapter.family_adapter_cache.async_init_checkpointer",
            new_callable=AsyncMock,
        ),
        patch(
            "deerflow.persistence.engine.init_engine",
            new_callable=AsyncMock,
        ),
        patch(
            "apps.agent.routers.import_parse._run_import_parse_agent",
            agent_run,
        ),
    ):
        from apps.agent.app.main import app

        with TestClient(app) as test_client:
            yield test_client


def _post(client: TestClient, family_id: str) -> Any:
    return client.post(
        "/import/parse",
        headers={
            "X-Agent-Token": create_agent_token(family_id),
            "X-Family-Id": family_id,
            "X-User-Id": f"user-{family_id}",
        },
        json={"text": "某基金 1000 份"},
    )


def test_contextvar_set_before_agent_and_reset_after_success():
    """Success path: set fires before the agent runs; reset fires exactly once."""
    observed_family_ids: list[str | None] = []

    async def fake_run(**kwargs: Any) -> None:
        # Inside the agent run, the sandbox ContextVar must already be set to the
        # request's family_id — proving set_family_sandbox_context preceded the run.
        from apps.agent.services.runtime.sandbox_provider import (
            get_family_sandbox_context,
        )

        observed_family_ids.append(get_family_sandbox_context())

    agent_run = AsyncMock(side_effect=fake_run)

    from apps.agent.services.runtime import sandbox_provider as sp

    with (
        patch.object(sp, "set_family_sandbox_context", wraps=sp.set_family_sandbox_context) as set_spy,
        patch.object(sp, "reset_family_sandbox_context", wraps=sp.reset_family_sandbox_context) as reset_spy,
    ):
        for _client in _client_with_stubbed_worker(agent_run):
            resp_a = _post(_client, "family-A")
            resp_b = _post(_client, "family-B")

    # Empty-result contract holds (no result event published by the stub).
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    # The agent observed the correct family_id on each call (set preceded the run).
    assert observed_family_ids == ["family-A", "family-B"]
    # set + reset each fired exactly once per request (no leak, no double-reset).
    assert set_spy.call_count == 2
    assert reset_spy.call_count == 2
    set_spy.assert_any_call("family-A", caller_user_id="user-family-A")
    set_spy.assert_any_call("family-B", caller_user_id="user-family-B")


def test_contextvar_reset_on_agent_exception():
    """Exception path: even when the agent raises, the reset still fires once."""
    agent_run = AsyncMock(side_effect=RuntimeError("agent blew up"))

    from apps.agent.services.runtime import sandbox_provider as sp

    with patch.object(sp, "reset_family_sandbox_context", wraps=sp.reset_family_sandbox_context) as reset_spy:
        for _client in _client_with_stubbed_worker(agent_run):
            resp = _post(_client, "family-exc")

    # The endpoint maps agent failure to the empty-result contract (no 500).
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    # The finally reset fired despite the exception.
    assert reset_spy.call_count == 1


def test_contextvar_reset_on_timeout():
    """Timeout path: ``asyncio.timeout`` -> TimeoutError is caught; reset still fires."""
    import asyncio

    async def slow_run(**kwargs: Any) -> None:
        # Sleep past IMPORT_PARSE_TIMEOUT_SECONDS so asyncio.timeout fires.
        await asyncio.sleep(30)

    agent_run = AsyncMock(side_effect=slow_run)

    from apps.agent.services.runtime import sandbox_provider as sp

    with (
        patch(
            "apps.agent.routers.import_parse.settings.IMPORT_PARSE_TIMEOUT_SECONDS",
            0.05,
        ),
        patch.object(sp, "reset_family_sandbox_context", wraps=sp.reset_family_sandbox_context) as reset_spy,
    ):
        for _client in _client_with_stubbed_worker(agent_run):
            resp = _post(_client, "family-timeout")

    # Timeout maps to the empty-result contract (no 500).
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    # The finally reset fired despite the timeout.
    assert reset_spy.call_count == 1
