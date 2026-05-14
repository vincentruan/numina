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
        "family_invitation_code": "AUTO-OWNER",
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


def _register_member(client):
    """Register owner first, then join as member."""
    owner_resp = client.post("/api/v1/auth/register", json={
        "username": "owner_for_member",
        "display_name": "Owner",
        "password": "OwnerPass1",
        "family_name": "Member Family",
        "family_invitation_code": "AUTO-MEMBER",
    })
    assert owner_resp.status_code == 200
    owner_headers = {"Authorization": f"Bearer {owner_resp.json()['data']['access_token']}"}

    # Get invite code
    family_resp = client.get("/api/v1/family/info", headers=owner_headers)
    invite_code = family_resp.json()["data"]["invite_code"]

    member_resp = client.post("/api/v1/auth/family/join", json={
        "username": "member1",
        "display_name": "Member",
        "password": "MemberPass1",
        "invite_code": invite_code,
    })
    assert member_resp.status_code == 200
    return {"Authorization": f"Bearer {member_resp.json()['data']['access_token']}"}


def _create_child(client, headers, pin=None):
    pin = pin or VALID_PIN
    resp = client.post("/api/v1/family/children", json={
        "display_name": "小明",
        "username": "xiaoming2",
        "password": "ChildPass1",
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
    data = resp.json()["data"]
    assert data["display_name"] == "小明"
    assert data["is_active"] is True
    assert "id" in data


def test_child_appears_in_list(client):
    headers = _register_owner(client)
    _create_child(client, headers)
    resp = client.get("/api/v1/family/children", headers=headers)
    assert resp.status_code == 200
    children = resp.json()["data"]
    assert len(children) == 1
    assert children[0]["display_name"] == "小明"


# ---------------------------------------------------------------------------
# Happy path: owner resets child PIN
# ---------------------------------------------------------------------------

def test_owner_resets_child_pin(client):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["data"]["id"]

    resp = client.patch(f"/api/v1/family/children/{child_id}", json={
        "pin": VALID_PIN_2,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == str(child_id)


# ---------------------------------------------------------------------------
# Happy path: owner unlocks child PIN
# ---------------------------------------------------------------------------

def test_owner_unlocks_child(client, db):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["data"]["id"]

    # Manually lock the child in DB
    from datetime import datetime, timedelta

    from apps.backend.app.models.user import User
    child = db.query(User).filter(User.id == child_id).first()
    child.pin_fail_count = 5
    child.pin_locked_until = datetime.utcnow() + timedelta(minutes=15)
    db.commit()

    resp = client.post(f"/api/v1/family/children/{child_id}/unlock", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "已解锁"

    db.refresh(child)
    assert child.pin_locked_until is None
    assert child.pin_fail_count == 0


# ---------------------------------------------------------------------------
# Happy path: owner force-logouts child
# ---------------------------------------------------------------------------

def test_owner_force_logout_child(client, db):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["data"]["id"]

    from apps.backend.app.models.user import User
    child = db.query(User).filter(User.id == child_id).first()
    original_version = child.token_version

    resp = client.post(f"/api/v1/family/children/{child_id}/force-logout", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "已强制退出"

    db.refresh(child)
    assert child.token_version == original_version + 1


# ---------------------------------------------------------------------------
# Error path: create child with invalid emoji → 422
# ---------------------------------------------------------------------------

def test_create_child_invalid_emoji(client):
    headers = _register_owner(client)
    resp = client.post("/api/v1/family/children", json={
        "display_name": "小红",
        "username": "xiaohong2",
        "pin": ["🍕", "🍕", "🍕", "🍕"],
    }, headers=headers)
    assert resp.status_code == 422


def test_create_child_invalid_avatar_color(client):
    headers = _register_owner(client)
    resp = client.post("/api/v1/family/children", json={
        "display_name": "小红",
        "username": "xiaohong",
        "avatar_color": "red",
        "pin": VALID_PIN,
    }, headers=headers)
    assert resp.status_code == 422


def test_update_child_invalid_avatar_color(client):
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["data"]["id"]
    resp = client.patch(f"/api/v1/family/children/{child_id}", json={
        "avatar_color": "not-a-color",
    }, headers=headers)
    assert resp.status_code == 422


def test_update_child_avatar_color_none_allowed(client):
    """PATCH with avatar_color omitted (None) should succeed — validator allows None."""
    headers = _register_owner(client)
    child_id = _create_child(client, headers).json()["data"]["id"]
    resp = client.patch(f"/api/v1/family/children/{child_id}", json={
        "display_name": "新名字",
        "username": "newname",
    }, headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Edge case: family with 3 child accounts — all returned in list
# ---------------------------------------------------------------------------

def test_three_children_all_returned(client):
    headers = _register_owner(client)

    for i in range(3):
        resp = client.post("/api/v1/family/children", json={
            "username": f"child{i}",
            "display_name": f"孩子{i}",
            "password": "ChildPass1",
            "pin": VALID_PIN,
        }, headers=headers)
        assert resp.status_code == 201

    resp = client.get("/api/v1/family/children", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 3


# ---------------------------------------------------------------------------
# TestRequireAdult: child tokens must be blocked from adult endpoints
# ---------------------------------------------------------------------------

def _get_child_token(client) -> str:
    """Register owner, create child, login as child, return Bearer token.

    Clears adult cookies after setup so subsequent requests with the child
    Bearer token are not shadowed by the owner's access_token cookie.
    """
    from tests.backend.conftest import child_login_two_phase

    owner_headers = _register_owner(client)
    _create_child(client, owner_headers)

    token = child_login_two_phase(client, "xiaoming2", "ChildPass1", VALID_PIN)

    # Clear all cookies so the adult access_token cookie doesn't shadow
    # the child Bearer token in subsequent requests.
    client.cookies.clear()
    return token


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
        from tests.backend.conftest import child_login_two_phase

        owner_headers = _register_owner(client)
        _create_child(client, owner_headers)

        child_token = child_login_two_phase(client, "xiaoming2", "ChildPass1", VALID_PIN)

        # Clear adult cookies so child Bearer token is used
        client.cookies.clear()

        resp = client.get("/api/v1/family/children", headers={"Authorization": f"Bearer {child_token}"})
        assert resp.status_code == 403
