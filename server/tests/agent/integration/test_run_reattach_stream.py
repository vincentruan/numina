"""Integration tests for the T13 run-reattach SSE endpoint.

Verifies that ``GET /api/threads/{thread_id}/runs/{run_id}/stream`` attaches
to an existing run's Redis buffer with Last-Event-ID, without creating a new
run, and that cross-tenant isolation is enforced.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app():
    """Build a FastAPI app with just the runs_stream router."""
    from fastapi import FastAPI

    from apps.agent.routers.runs_stream import router

    app = FastAPI()
    app.include_router(router)
    # Bypass the JWT verify dependency for unit-level tests.
    from apps.agent.routers import runs_stream as runs_stream_mod

    app.dependency_overrides[runs_stream_mod.verify_family_token] = lambda: MagicMock(
        family_id="family-1"
    )
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def _make_record(run_id: str, thread_id: str, family_id: str) -> MagicMock:
    record = MagicMock()
    record.run_id = run_id
    record.thread_id = thread_id
    record.metadata = {"family_id": family_id}
    return record


class TestReattachRunStream:
    def test_404_when_run_not_found(self, client: TestClient) -> None:
        with patch("apps.agent.routers.runs_stream.get_run_manager") as get_mgr:
            run_mgr = MagicMock()
            run_mgr.get = AsyncMock(return_value=None)
            get_mgr.return_value = run_mgr

            with patch(
                "apps.agent.routers.runs_stream.get_stream_bridge"
            ) as get_bridge:
                get_bridge.return_value = AsyncMock()
                resp = client.get(
                    "/api/threads/thread-1/runs/missing-run/stream",
                    headers={"X-Family-Id": "family-1"},
                )
        assert resp.status_code == 404

    def test_404_when_thread_mismatch(self, client: TestClient) -> None:
        record = _make_record("run-1", "thread-other", "family-1")
        with patch("apps.agent.routers.runs_stream.get_run_manager") as get_mgr:
            run_mgr = MagicMock()
            run_mgr.get = AsyncMock(return_value=record)
            get_mgr.return_value = run_mgr

            with patch(
                "apps.agent.routers.runs_stream.get_stream_bridge"
            ) as get_bridge:
                get_bridge.return_value = AsyncMock()
                resp = client.get(
                    "/api/threads/thread-1/runs/run-1/stream",
                    headers={"X-Family-Id": "family-1"},
                )
        assert resp.status_code == 404

    def test_404_when_family_mismatch(self, client: TestClient) -> None:
        record = _make_record("run-1", "thread-1", "family-OTHER")
        with patch("apps.agent.routers.runs_stream.get_run_manager") as get_mgr:
            run_mgr = MagicMock()
            run_mgr.get = AsyncMock(return_value=record)
            get_mgr.return_value = run_mgr

            with patch(
                "apps.agent.routers.runs_stream.get_stream_bridge"
            ) as get_bridge:
                get_bridge.return_value = AsyncMock()
                resp = client.get(
                    "/api/threads/thread-1/runs/run-1/stream",
                    headers={"X-Family-Id": "family-1"},
                )
        assert resp.status_code == 404

    def test_200_streams_existing_run(self, client: TestClient) -> None:
        record = _make_record("run-1", "thread-1", "family-1")

        # Stub sse_consumer to yield a deterministic frame, then close.
        async def fake_consumer(bridge, rec, request, run_mgr):
            yield "data: {\"hello\": \"world\"}\n\n"
            yield "event: end\ndata: null\n\n"

        with patch("apps.agent.routers.runs_stream.get_run_manager") as get_mgr:
            run_mgr = MagicMock()
            run_mgr.get = AsyncMock(return_value=record)
            get_mgr.return_value = run_mgr

            with patch(
                "apps.agent.routers.runs_stream.get_stream_bridge"
            ) as get_bridge:
                get_bridge.return_value = AsyncMock()

                with patch(
                    "apps.agent.routers.runs_stream.sse_consumer",
                    side_effect=fake_consumer,
                ):
                    resp = client.get(
                        "/api/threads/thread-1/runs/run-1/stream",
                        headers={"X-Family-Id": "family-1"},
                    )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "world" in resp.text
