"""Tests for GET /auth/device-ping ETag persistence endpoint."""

from fastapi.testclient import TestClient


def test_device_ping_no_etag_returns_null(client: TestClient):
    """Without If-None-Match, returns device_id: null."""
    resp = client.get("/api/v1/auth/device-ping")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"device_id": None}
    assert "no-store" in resp.headers.get("cache-control", "")


def test_device_ping_with_etag_returns_device_id(client: TestClient):
    """With If-None-Match containing a device_id, returns it back for recovery."""
    device_id = "abc123-def456"
    resp = client.get(
        "/api/v1/auth/device-ping",
        headers={"If-None-Match": f'"{device_id}"'},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["device_id"] == device_id
    assert resp.headers.get("etag") == f'"{device_id}"'
    assert "max-age=" in resp.headers.get("cache-control", "")
