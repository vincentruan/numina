"""Tests for family manifesto API endpoints (U2)."""

import pytest

from apps.backend.app.auth.deps import create_access_token
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id
from tests.backend.conftest import child_login_two_phase


def _data(resp):
    body = resp.json()
    return body.get("data", body)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MANIFESTO_CREATE_BODY = {
    "template_id": "family_rules_v1",
    "title": "家庭约定",
    "body": "我们一起遵守以下约定...",
}


def _create_manifesto(client, auth_headers, **overrides):
    body = {**_MANIFESTO_CREATE_BODY, **overrides}
    resp = client.post("/api/v1/family/manifesto", headers=auth_headers, json=body)
    assert resp.status_code == 201, resp.text
    return _data(resp)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def member_headers(client, auth_headers, db):
    """Return HTTP headers for a member (non-owner) in the same family."""
    family = db.query(Family).first()
    user_id = next_id()
    user = User(
        id=user_id,
        username="memberuser",
        display_name="Member",
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
def child_user(client, auth_headers):
    """Create a child user in the same family as auth_headers."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "display_name": "小明",
            "password": "ChildPass1",
            "username": "xiaomingm",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201, resp.text
    child = _data(resp)
    token = child_login_two_phase(
        client, "xiaomingm", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"]
    )
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def manifesto(client, auth_headers):
    """Owner creates a manifesto."""
    return _create_manifesto(client, auth_headers)


# ---------------------------------------------------------------------------
# Owner creates manifesto
# ---------------------------------------------------------------------------


def test_owner_create_manifesto_201(client, auth_headers):
    resp = client.post(
        "/api/v1/family/manifesto", headers=auth_headers, json=_MANIFESTO_CREATE_BODY
    )
    assert resp.status_code == 201
    data = _data(resp)
    assert data["status"] == "active"
    assert data["current_version"] is not None
    assert data["current_version"]["version_number"] == 1
    assert data["current_version"]["change_type"] == "initial"
    assert data["current_version"]["title"] == "家庭约定"
    assert data["signatures"] == []


def test_non_owner_cannot_create_403(client, member_headers):
    resp = client.post(
        "/api/v1/family/manifesto",
        headers=member_headers,
        json=_MANIFESTO_CREATE_BODY,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Member signs manifesto
# ---------------------------------------------------------------------------


def test_member_sign_manifesto_200(client, auth_headers, member_headers, manifesto):
    resp = client.post(
        "/api/v1/family/manifesto/sign",
        headers=member_headers,
        json={"signature_data": "member_sig_data"},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["signature_data"] == "member_sig_data"


def test_member_cannot_sign_twice_409(client, member_headers, manifesto):
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=member_headers,
        json={},
    )
    resp = client.post(
        "/api/v1/family/manifesto/sign",
        headers=member_headers,
        json={},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Publish minor/major update
# ---------------------------------------------------------------------------


def test_minor_update_copies_signatures(client, auth_headers, member_headers, manifesto):
    # Owner + member both sign
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=auth_headers,
        json={},
    )
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=member_headers,
        json={},
    )
    # Publish minor update
    resp = client.patch(
        "/api/v1/family/manifesto",
        headers=auth_headers,
        json={"change_type": "minor", "title": "家庭约定 v2"},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["current_version"]["version_number"] == 2
    assert data["current_version"]["change_type"] == "minor"
    # Signatures from v1 should be copied to v2
    assert len(data["signatures"]) == 2


def test_major_update_no_signature_copy(client, auth_headers, member_headers, manifesto):
    # Both sign
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=auth_headers,
        json={},
    )
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=member_headers,
        json={},
    )
    # Publish major update
    resp = client.patch(
        "/api/v1/family/manifesto",
        headers=auth_headers,
        json={"change_type": "major", "title": "家庭约定 重大修改"},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["current_version"]["version_number"] == 2
    assert data["current_version"]["change_type"] == "major"
    # No signatures copied
    assert len(data["signatures"]) == 0


# ---------------------------------------------------------------------------
# Unsigned check
# ---------------------------------------------------------------------------


def test_unsigned_check_returns_manifesto_when_unsigned(client, auth_headers, manifesto):
    resp = client.get(
        "/api/v1/family/manifesto/unsigned-check", headers=auth_headers
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["has_unsigned"] is True
    assert data["manifesto_id"] == manifesto["id"]
    assert data["title"] == "家庭约定"


def test_unsigned_check_false_after_signing(client, auth_headers, manifesto):
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=auth_headers,
        json={},
    )
    resp = client.get(
        "/api/v1/family/manifesto/unsigned-check", headers=auth_headers
    )
    data = _data(resp)
    assert data["has_unsigned"] is False


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


def test_dashboard_summary_correct_counts(
    client, auth_headers, member_headers, manifesto, db
):
    # 2 non-child members (owner + member)
    resp = client.get(
        "/api/v1/family/manifesto/dashboard-summary", headers=auth_headers
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["total_members"] == 2
    assert data["signed_count"] == 0
    assert data["status"] == "active"

    # Owner signs
    client.post(
        "/api/v1/family/manifesto/sign",
        headers=auth_headers,
        json={},
    )
    resp = client.get(
        "/api/v1/family/manifesto/dashboard-summary", headers=auth_headers
    )
    data = _data(resp)
    assert data["signed_count"] == 1


# ---------------------------------------------------------------------------
# Child read + sign
# ---------------------------------------------------------------------------


def test_child_can_read_manifesto(client, auth_headers, child_user, manifesto):
    resp = client.get("/api/v1/child/manifesto", headers=child_user["headers"])
    assert resp.status_code == 200
    data = _data(resp)
    assert data["title"] == "家庭约定"
    assert data["signed"] is False


def test_child_can_sign_manifesto(client, auth_headers, child_user, manifesto):
    resp = client.post(
        "/api/v1/child/manifesto/sign",
        headers=child_user["headers"],
        json={},  # signature_data nullable for tap-to-consent
    )
    assert resp.status_code == 200


def test_child_cannot_create_manifesto(client, child_user):
    resp = client.post(
        "/api/v1/family/manifesto",
        headers=child_user["headers"],
        json=_MANIFESTO_CREATE_BODY,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def test_feedback_submission_and_retrieval(client, auth_headers, manifesto):
    # Submit feedback (any adult can submit)
    resp = client.post(
        "/api/v1/family/manifesto/feedback",
        headers=auth_headers,
        json={"content": "建议增加一条关于零花钱的条款"},
    )
    assert resp.status_code == 201
    fb = _data(resp)
    assert fb["content"] == "建议增加一条关于零花钱的条款"
    assert fb["is_read"] is False

    # List feedback (owner only)
    resp = client.get("/api/v1/family/manifesto/feedback", headers=auth_headers)
    assert resp.status_code == 200
    feedback_list = _data(resp)
    assert len(feedback_list) == 1
    assert feedback_list[0]["content"] == "建议增加一条关于零花钱的条款"


def test_member_cannot_list_feedback(client, member_headers, manifesto):
    resp = client.get("/api/v1/family/manifesto/feedback", headers=member_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------


def test_version_history_ordering(client, auth_headers, manifesto):
    # Publish 2 updates
    client.patch(
        "/api/v1/family/manifesto",
        headers=auth_headers,
        json={"change_type": "minor", "title": "v2"},
    )
    client.patch(
        "/api/v1/family/manifesto",
        headers=auth_headers,
        json={"change_type": "major", "title": "v3"},
    )
    resp = client.get("/api/v1/family/manifesto/history", headers=auth_headers)
    assert resp.status_code == 200
    history = _data(resp)
    assert len(history) == 3
    # Descending order: v3, v2, initial
    assert history[0]["version_number"] == 3
    assert history[1]["version_number"] == 2
    assert history[2]["version_number"] == 1
    assert history[0]["change_type"] == "major"
    assert history[1]["change_type"] == "minor"
    assert history[2]["change_type"] == "initial"


# ---------------------------------------------------------------------------
# Trackable clauses (child endpoint)
# ---------------------------------------------------------------------------


def test_trackable_clauses(client, auth_headers, child_user):
    # Create manifesto with trackable clauses
    _create_manifesto(
        client, auth_headers, trackable_clause_indices=[0, 2, 4]
    )
    resp = client.get(
        "/api/v1/child/manifesto/trackable-clauses",
        headers=child_user["headers"],
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["has_trackable"] is True
    assert data["trackable_clause_indices"] == [0, 2, 4]


def test_trackable_clauses_none(client, auth_headers, child_user, manifesto):
    # manifesto fixture has no trackable_clause_indices
    resp = client.get(
        "/api/v1/child/manifesto/trackable-clauses",
        headers=child_user["headers"],
    )
    data = _data(resp)
    assert data["has_trackable"] is False
