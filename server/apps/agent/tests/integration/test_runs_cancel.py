"""Integration tests for the runs cancel endpoint.

Verifies the ``@langchain/langgraph-sdk`` ``runs.cancel`` protocol:
``POST /api/threads/{thread_id}/runs/{run_id}/cancel`` cancels an in-flight
run, and unknown / mismatched / cross-family runs return 404 so existence is
not leaked across tenants.

Uses ``httpx.AsyncClient`` with an ASGI transport (no lifespan) and overrides
``verify_family_token`` + ``get_run_manager`` so the test's ``RunManager``
asyncio primitives stay in the test's own event loop.
"""

from __future__ import annotations

import httpx
import pytest
from deerflow.runtime import RunManager, RunStatus

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token
from apps.agent.services.runtime.lifespan import get_run_manager


@pytest.fixture
def run_manager() -> RunManager:
    """A fresh in-memory RunManager per test (no persistent store)."""
    return RunManager(store=None)


@pytest.fixture
async def client(run_manager: RunManager):
    """Async ASGI client with auth + run-manager deps overridden."""
    from apps.agent.app.main import app

    app.dependency_overrides[verify_family_token] = lambda: VerifiedFamily(
        family_id="family-1", user_id="user-1", role="member"
    )
    app.dependency_overrides[get_run_manager] = lambda: run_manager
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def _make_run(
    run_manager: RunManager,
    *,
    thread_id: str = "thread-1",
    family_id: str = "family-1",
):
    return await run_manager.create_or_reject(
        thread_id=thread_id,
        assistant_id="agent",
        metadata={"family_id": family_id},
    )


async def test_cancel_run_cancels_inflight_run(client, run_manager):
    record = await _make_run(run_manager)
    resp = await client.post(
        f"/api/threads/thread-1/runs/{record.run_id}/cancel",
        params={"action": "interrupt", "wait": "0"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == record.run_id
    assert body["cancelled"] is True
    assert (await run_manager.get(record.run_id)).status == RunStatus.interrupted


async def test_cancel_unknown_run_returns_404(client):
    resp = await client.post("/api/threads/thread-1/runs/no-such-run/cancel")
    assert resp.status_code == 404


async def test_cancel_run_with_mismatched_thread_returns_404(client, run_manager):
    record = await _make_run(run_manager, thread_id="thread-1")
    resp = await client.post(
        f"/api/threads/wrong-thread/runs/{record.run_id}/cancel"
    )
    assert resp.status_code == 404
    # Run is untouched.
    assert (await run_manager.get(record.run_id)).status == RunStatus.pending


async def test_cancel_cross_family_run_returns_404(client, run_manager):
    record = await _make_run(run_manager, family_id="family-other")
    resp = await client.post(
        f"/api/threads/thread-1/runs/{record.run_id}/cancel"
    )
    assert resp.status_code == 404
    # Caller could not cancel a run belonging to another family.
    assert (await run_manager.get(record.run_id)).status == RunStatus.pending
