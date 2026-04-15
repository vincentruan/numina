"""Tests for Unit 3: Child CRUD, device binding, force-logout."""

import pytest


VALID_PIN = ["🐱", "🐶", "🐸", "🦊"]
VALID_PIN_2 = ["🐼", "🐨", "🦁", "🐯"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_owner(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "owner1",
        "display_name": "Owner",
        "password": "OwnerPass1",
        "family_name": "Test Family",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_member(client):
    """Register owner first, then join as member."""
    owner_resp = client.post("/api/v1/auth/register", json={
        "username": "owner_for_member",
        "display_name": "Owner",
        "password": "OwnerPass1",
        "family_name": "Member Family",
    })
    assert owner_resp.status_code == 200
    owner_headers = {"Authorization": f"Bearer {owner_resp.json()['access_token']}"}

    # Get invite code
    family_resp = client.get("/api/v1/family/info", headers=owner_headers)
    invite_code = family_resp.json()["invite_code"]

    member_resp = client.post("/api/v1/auth/family/join", json={
        "username": "member1",
        "display_name": "Member",
        "password": "MemberPass1",
        "invite_code": invite_code,
    })
    assert member_resp.status_code == 200
    return {"Authorization": f"Bearer {member_resp.json()['access_token']}"}


def _create_child(client, headers, pin=None):
    pin = pin or VALID_PIN
    resp = client.post("/api/v1/family/children", json={
        "display_name": "小明",
        "pin": pin,
    }, headers=headers)
    return resp


# ---------------------------------------------------------------------------
# Happy path: owner creates child
# ---------------------------------------------------------------------------

def test_owner_creates_child(client):
    headers = _register_owner(client)
    resp = _create_child(client, headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "小明"
    assert data["is_active"] is True
    assert "id" in data


def test_child_appears_in_list(client):
    headers = _register_owner(client)
    _create_child(client, headers)
    resp = client.get("/api/v1/family/children", headers=headers)
    assert resp.status_code == 200
    children = resp.json()
    assert len(children) == 1
    assert children[0]["display_name"] == "小明"


# ---------------------------------------------------------------------------
# Happy path: owner resets child PIN
# ---------------------------------------------------------------------------

def test_owner_resets_child_pin(client):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["id"]

    resp = client.patch(f"/api/v1/family/children/{child_id}", json={
        "pin": VALID_PIN_2,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == child_id


# ---------------------------------------------------------------------------
# Happy path: owner unlocks child PIN
# ---------------------------------------------------------------------------

def test_owner_unlocks_child(client, db):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["id"]

    # Manually lock the child in DB
    from app.models.user import User
    from datetime import datetime, timedelta
    child = db.query(User).filter(User.id == child_id).first()
    child.pin_fail_count = 5
    child.pin_locked_until = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    resp = client.post(f"/api/v1/family/children/{child_id}/unlock", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "已解锁"

    db.refresh(child)
    assert child.pin_locked_until is None
    assert child.pin_fail_count == 0


# ---------------------------------------------------------------------------
# Happy path: owner force-logouts child
# ---------------------------------------------------------------------------

def test_owner_force_logout_child(client, db):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["id"]

    from app.models.user import User
    child = db.query(User).filter(User.id == child_id).first()
    original_version = child.token_version

    resp = client.post(f"/api/v1/family/children/{child_id}/force-logout", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "已强制退出"

    db.refresh(child)
    assert child.token_version == original_version + 1


# ---------------------------------------------------------------------------
# Happy path: bind token + GET family children (no auth)
# ---------------------------------------------------------------------------

def test_get_family_children_nonexistent_family_returns_empty(client):
    """Non-existent family_id returns empty list (not 404)."""
    resp = client.get("/api/v1/auth/child/family/nonexistent-family-id/children")
    assert resp.status_code == 200
    assert resp.json() == []


def test_bind_token_and_get_family_children(client):
    headers = _register_owner(client)
    _create_child(client, headers)

    # Get family_id
    family_resp = client.get("/api/v1/family/info", headers=headers)
    family_id = family_resp.json()["id"]

    # Generate bind token
    token_resp = client.post("/api/v1/family/child-bind-token", headers=headers)
    assert token_resp.status_code == 201
    token_data = token_resp.json()
    assert "token" in token_data
    assert token_data["bind_url"].startswith("/child/bind?token=")

    # GET children without auth
    children_resp = client.get(f"/api/v1/auth/child/family/{family_id}/children")
    assert children_resp.status_code == 200
    children = children_resp.json()
    assert len(children) == 1
    assert children[0]["display_name"] == "小明"


# ---------------------------------------------------------------------------
# Error path: member tries to create child → 403
# ---------------------------------------------------------------------------

def test_member_cannot_create_child(client):
    member_headers = _register_member(client)
    resp = _create_child(client, member_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Error path: bind token used twice → 400
# ---------------------------------------------------------------------------

def test_bind_token_used_twice(client, db):
    headers = _register_owner(client)
    token_resp = client.post("/api/v1/family/child-bind-token", headers=headers)
    token_str = token_resp.json()["token"]

    # Use it once via service directly
    from app.services.children import get_bind_info
    get_bind_info(db, token_str)

    # Second use should fail
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_bind_info(db, token_str)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Error path: expired bind token → 400
# ---------------------------------------------------------------------------

def test_expired_bind_token(client, db):
    headers = _register_owner(client)
    token_resp = client.post("/api/v1/family/child-bind-token", headers=headers)
    token_str = token_resp.json()["token"]

    # Expire it manually
    from app.models.child_bind_token import ChildBindToken
    from datetime import datetime, timedelta
    bt = db.query(ChildBindToken).filter(ChildBindToken.token == token_str).first()
    bt.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()

    from app.services.children import get_bind_info
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        get_bind_info(db, token_str)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Error path: create child with invalid emoji → 422
# ---------------------------------------------------------------------------

def test_create_child_invalid_emoji(client):
    headers = _register_owner(client)
    resp = client.post("/api/v1/family/children", json={
        "display_name": "小红",
        "pin": ["🍕", "🍕", "🍕", "🍕"],
    }, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Edge case: family with 3 child accounts — all returned in list
# ---------------------------------------------------------------------------

def test_three_children_all_returned(client):
    headers = _register_owner(client)

    for i in range(3):
        resp = client.post("/api/v1/family/children", json={
            "display_name": f"孩子{i}",
            "pin": VALID_PIN,
        }, headers=headers)
        assert resp.status_code == 201

    resp = client.get("/api/v1/family/children", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ---------------------------------------------------------------------------
# TestRequireAdult: child tokens must be blocked from adult endpoints
# ---------------------------------------------------------------------------

def _get_child_token(client) -> str:
    """Register owner, create child, login as child, return Bearer token.

    Clears adult cookies after setup so subsequent requests with the child
    Bearer token are not shadowed by the owner's access_token cookie.
    """
    owner_headers = _register_owner(client)
    child_resp = _create_child(client, owner_headers)
    child_id = child_resp.json()["id"]

    login_resp = client.post("/api/v1/auth/child/login", json={
        "child_id": child_id,
        "pin_sequence": VALID_PIN,
    })
    assert login_resp.status_code == 200
    child_token = login_resp.json()["access_token"]

    # Clear all cookies so the adult access_token cookie doesn't shadow
    # the child Bearer token in subsequent requests.
    client.cookies.clear()
    return child_token


class TestRequireAdult:
    def test_child_blocked_from_assets(self, client):
        token = _get_child_token(client)
        resp = client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_child_blocked_from_dashboard(self, client):
        token = _get_child_token(client)
        resp = client.get("/api/v1/dashboard/overview", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_child_blocked_from_wishes(self, client):
        token = _get_child_token(client)
        resp = client.get("/api/v1/wishes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_adult_can_access_assets(self, client):
        headers = _register_owner(client)
        resp = client.get("/api/v1/assets", headers=headers)
        assert resp.status_code == 200

    def test_child_blocked_from_family_children(self, client):
        # C3 fix: child tokens must NOT be able to enumerate siblings
        owner_headers = _register_owner(client)
        child_resp = _create_child(client, owner_headers)
        child_id = child_resp.json()["id"]

        login_resp = client.post("/api/v1/auth/child/login", json={
            "child_id": child_id,
            "pin_sequence": VALID_PIN,
        })
        assert login_resp.status_code == 200
        child_token = login_resp.json()["access_token"]

        # Clear adult cookies so child Bearer token is used
        client.cookies.clear()

        resp = client.get("/api/v1/family/children", headers={"Authorization": f"Bearer {child_token}"})
        assert resp.status_code == 403
