"""Integration test for T27: verification endpoint."""

from __future__ import annotations

import json
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

    app = FastAPI()
    app.include_router(run_events_router.router)
    # Bypass token verification for unit-level testing
    from apps.agent.routers import run_events as re_mod

    app.dependency_overrides[re_mod.verify_service_token] = lambda: "family-1"
    return TestClient(app)


def test_verify_endpoint_empty(client: TestClient, tmp_path: Path) -> None:
    """Verify endpoint returns True for family with no events."""
    # Use a different directory with no events
    empty_store = RunEventStore(tmp_path / "empty")
    store_module._event_store = empty_store

    response = client.get(
        "/run-events/verify",
        headers={"X-Family-Id": "family-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["event_count"] == 0


def test_verify_endpoint_with_events(client: TestClient) -> None:
    """Verify endpoint validates hash chain."""
    store = store_module._event_store
    assert store is not None

    # Create some events
    for i in range(3):
        store.record_raw(
            f"test-event-{i}",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            data={"index": i},
        )

    response = client.get(
        "/run-events/verify",
        headers={"X-Family-Id": "family-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is True
    assert data["event_count"] == 3


def test_verify_endpoint_detects_tampering(client: TestClient, tmp_path: Path) -> None:
    """Verify endpoint detects tampered events."""
    store = store_module._event_store
    assert store is not None

    # Create events
    for i in range(3):
        store.record_raw(
            f"test-event-{i}",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            data={"index": i},
        )

    # Tamper with event 1
    path = tmp_path / "run_events" / "family-1.jsonl"
    lines = path.read_text().strip().split("\n")
    tampered = json.loads(lines[1])
    tampered["data"]["tampered"] = True
    lines[1] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n")

    # Clear cache
    store._last_hash_cache.clear()

    response = client.get(
        "/run-events/verify",
        headers={"X-Family-Id": "family-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verified"] is False
    assert data["tampered_event_index"] == 1


def test_verify_endpoint_legacy_events(client: TestClient, tmp_path: Path) -> None:
    """Verify endpoint returns 'unverified' for legacy events."""
    # Create a separate store with legacy events
    legacy_store = RunEventStore(tmp_path / "legacy")

    # Write legacy events (no hash fields) directly
    path = tmp_path / "legacy" / "run_events" / "family-1.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy_event = {
        "event_type": "run.start",
        "run_id": "run-1",
        "thread_id": "thread-1",
        "family_id": "family-1",
        "timestamp": "2026-11-03T10:00:00Z",
        "data": {},
    }
    path.write_text(json.dumps(legacy_event) + "\n")

    store_module._event_store = legacy_store

    response = client.get(
        "/run-events/verify",
        headers={"X-Family-Id": "family-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["verified"] == "unverified"
    assert "predate hash-chaining" in data["reason"]


def test_verify_endpoint_cross_family_denied(client: TestClient) -> None:
    """Verify endpoint enforces family isolation."""
    response = client.get(
        "/run-events/verify?family_id=family-2",
        headers={"X-Family-Id": "family-1"},
    )
    assert response.status_code == 403
