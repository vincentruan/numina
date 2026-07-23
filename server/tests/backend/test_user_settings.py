"""Tests for PUT /auth/me/settings theme_color persistence (S1)."""

from tests.backend.conftest import auth_headers  # noqa: F401  (fixture wiring)


def test_update_theme_color_valid(client, auth_headers):
    """PUT /auth/me/settings with a valid hex persists theme_color."""
    resp = client.put(
        "/api/v1/auth/me/settings",
        json={"theme_color": "#007aff"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["theme_color"] == "#007aff"

    # Confirm persistence via GET /auth/me
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    me_data = me.json().get("data", me.json())
    assert me_data["theme_color"] == "#007aff"


def test_update_theme_color_invalid_returns_422(client, auth_headers):
    """PUT /auth/me/settings with an invalid hex returns 422."""
    resp = client.put(
        "/api/v1/auth/me/settings",
        json={"theme_color": "red"},
        headers=auth_headers,
    )
    assert resp.status_code == 422

    resp2 = client.put(
        "/api/v1/auth/me/settings",
        json={"theme_color": "#xyz"},
        headers=auth_headers,
    )
    assert resp2.status_code == 422


def test_update_theme_color_none_leaves_unset(client, auth_headers):
    """Omitting theme_color does not error and returns null for a fresh user."""
    resp = client.put(
        "/api/v1/auth/me/settings",
        json={"view_mode": "list"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["view_mode"] == "list"
    assert data["theme_color"] is None
