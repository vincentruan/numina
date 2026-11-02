"""Integration tests for the run events query API (T12)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.agent.routers import run_events as run_events_router
from apps.agent.services import run_event_store as store_module
from apps.agent.services.run_event_store import RunEventStore


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a TestClient with the run-events router and a temp event store."""
    store = RunEventStore(tmp_path)
    monkeypatch.setattr(store_module, "_event_store", store)

    # Seed events
    store.record_raw("run.start", "run-1", "thread-1", "family-1", {"app": "numina"})
    store.record_raw("llm.tool.result", "run-1", "thread-1", "family-1", {"tool_name": "get_assets"})
    store.record_raw("run.end", "run-1", "thread-1", "family-1", {"status": "success"})
    store.record_raw("run.start", "run-2", "thread-2", "family-1", {"app": "numina"})
    store.record_raw("run.start", "run-3", "thread-3", "family-2", {"app": "numina"})

    app = FastAPI()
    app.include_router(run_events_router.router)
    # Bypass token verification for unit-level testing
    from apps.agent.routers import run_events as re_mod

    app.dependency_overrides[re_mod.verify_service_token] = lambda: "family-1"
    return TestClient(app)


class TestRunEventsApi:
    def test_query_by_thread_id(self, client: TestClient) -> None:
        resp = client.get(
            "/run-events?thread_id=thread-1",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 3
        assert [e["event_type"] for e in events] == [
            "run.start",
            "llm.tool.result",
            "run.end",
        ]

    def test_query_by_family_id(self, client: TestClient) -> None:
        resp = client.get(
            "/run-events?family_id=family-1",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) == 4  # 3 from thread-1 + 1 from thread-2

    def test_query_empty_thread_returns_empty_array(self, client: TestClient) -> None:
        resp = client.get(
            "/run-events?thread_id=nonexistent",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_query_requires_param(self, client: TestClient) -> None:
        resp = client.get("/run-events", headers={"X-Family-Id": "family-1"})
        assert resp.status_code == 400

    def test_cross_family_denied(self, client: TestClient) -> None:
        resp = client.get(
            "/run-events?family_id=family-2",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp.status_code == 403

    def test_pagination(self, client: TestClient) -> None:
        resp = client.get(
            "/run-events?family_id=family-1&limit=2&offset=0",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp2 = client.get(
            "/run-events?family_id=family-1&limit=2&offset=2",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp2.status_code == 200
        assert len(resp2.json()) == 2

    def test_thread_query_is_family_scoped(self, client: TestClient) -> None:
        """A thread belonging to another family must not leak."""
        resp = client.get(
            "/run-events?thread_id=thread-3",
            headers={"X-Family-Id": "family-1"},
        )
        assert resp.status_code == 200
        assert resp.json() == []
