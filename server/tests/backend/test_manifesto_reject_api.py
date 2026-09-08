"""Tests for family manifesto reject API endpoints."""

import pytest

from apps.backend.app.auth.deps import create_access_token
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id


def _data(resp):
    body = resp.json()
    return body.get("data", body)


_MANIFESTO_CREATE_BODY = {
    "template_id": "family_rules_v1",
    "title": "家庭约定",
    "body": "我们一起遵守以下约定...",
}


@pytest.fixture
def member_headers(client, auth_headers, db):
    """Return HTTP headers for a member (non-owner) in the same family."""
    family = db.query(Family).first()
    user_id = next_id()
    user = User(
        id=user_id,
        username="memberuser_reject",
        display_name="Member Reject",
        password_hash="hashed",
        family_id=family.id,
        role="member",
    )
    db.add(user)
    db.flush()
    token = create_access_token(
        {"sub": str(user_id), "fid": str(family.id), "role": "member"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manifesto(client, auth_headers):
    """Owner creates a manifesto."""
    resp = client.post(
        "/api/v1/family/manifesto",
        headers=auth_headers,
        json=_MANIFESTO_CREATE_BODY,
    )
    assert resp.status_code == 201
    return _data(resp)


# ---------------------------------------------------------------------------
# Reject manifesto
# ---------------------------------------------------------------------------


def test_adult_reject_manifesto_201(client, auth_headers, manifesto):
    """Adult user can reject a manifesto version."""
    resp = client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={"reason": "不同意第三条"},
    )
    assert resp.status_code == 201
    data = _data(resp)
    assert data["reason"] == "不同意第三条"
    assert data["user_id"]  # non-empty string (snowflake ID)


def test_reject_without_reason_201(client, auth_headers, manifesto):
    """Reject reason is optional (nullable)."""
    resp = client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 201
    data = _data(resp)
    assert data["reason"] is None


def test_cannot_reject_twice_409(client, auth_headers, manifesto):
    """Same user cannot reject the same version twice."""
    client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={"reason": "first"},
    )
    resp = client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={"reason": "second"},
    )
    assert resp.status_code == 409


def test_signed_user_cannot_reject_409(client, auth_headers, manifesto):
    """A user who already signed cannot reject."""
    # Sign first
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=auth_headers,
        json={},
    )
    # Try to reject
    resp = client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={"reason": "change mind"},
    )
    assert resp.status_code == 409


def test_rejected_user_cannot_sign_409(client, auth_headers, manifesto):
    """A user who already rejected cannot sign."""
    # Reject first
    client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={"reason": "no"},
    )
    # Try to sign
    resp = client.post(
        "/api/v1/family/manifesto/sign",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 409


def test_get_manifesto_includes_rejections(client, auth_headers, member_headers, manifesto):
    """GET /family/manifesto returns rejections list."""
    # Owner rejects
    client.post(
        "/api/v1/family/manifesto/reject",
        headers=auth_headers,
        json={"reason": "需要修改"},
    )
    # Fetch manifesto
    resp = client.get("/api/v1/family/manifesto", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert "rejections" in data
    assert len(data["rejections"]) == 1
    assert data["rejections"][0]["reason"] == "需要修改"


def test_get_manifesto_empty_rejections(client, auth_headers, manifesto):
    """GET /family/manifesto returns empty rejections when none exist."""
    resp = client.get("/api/v1/family/manifesto", headers=auth_headers)
    data = _data(resp)
    assert data["rejections"] == []
