"""Tests for multi-account device login endpoints.

Covers:
- POST /api/v1/auth/device/check — returns multi-user list
- POST /api/v1/auth/device/select — selects a user, handles 2FA or issues tokens
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from apps.backend.app.models.device_session import DeviceSession
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_family(db) -> Family:
    from apps.backend.app.utils.snowflake import next_id

    fid = next_id()
    family = Family(id=fid, name="MultiAcctFamily", invite_code=f"MA{fid}"[:6], created_by=fid)
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


def _make_user(
    db,
    family_id: int,
    role: str = "member",
    pin_hash: str | None = None,
    second_factor_enabled: bool = False,
    second_factor_type: str | None = None,
) -> User:
    from apps.backend.app.utils.snowflake import next_id

    user = User(
        id=next_id(),
        family_id=family_id,
        username=f"user_{next_id()}",
        display_name=f"Display {uuid4().hex[:6]}",
        password_hash="x",
        avatar_color="#4F46E5",
        role=role,
        is_active=True,
        pin_hash=pin_hash,
        second_factor_enabled=second_factor_enabled,
        second_factor_type=second_factor_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_session(
    db,
    user: User,
    device_id: str,
    *,
    is_revoked: bool = False,
    expires_at: datetime | None = None,
) -> DeviceSession:
    if expires_at is None:
        expires_at = datetime.utcnow() + timedelta(days=30)

    session = DeviceSession(
        user_id=user.id,
        family_id=user.family_id,
        device_id=device_id,
        device_name="Test Device · Chrome",
        refresh_jti=str(uuid4()),
        last_seen_at=datetime.utcnow(),
        expires_at=expires_at,
        is_revoked=is_revoked,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ─────────────────────────────────────────────────────────────────────────────
# /device/check tests
# ─────────────────────────────────────────────────────────────────────────────

def test_check_device_returns_multiple_users(client, db):
    """device/check returns all users bound to a device_id (up to 6)."""
    family = _make_family(db)
    device_id = str(uuid4())

    user1 = _make_user(db, family.id, role="owner")
    user2 = _make_user(db, family.id, role="member")
    _make_session(db, user1, device_id)
    _make_session(db, user2, device_id)

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trusted"] is True
    assert len(data["users"]) == 2
    user_ids = {u["user_id"] for u in data["users"]}
    assert user1.id in user_ids
    assert user2.id in user_ids


def test_check_device_unknown_returns_not_trusted(client, db):
    """device/check returns trusted=False for an unknown device_id."""
    resp = client.post(
        "/api/v1/auth/device/check",
        json={"device_id": "nonexistent-device-id"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trusted"] is False
    assert data["users"] == []


def test_check_device_max_6_users(client, db):
    """device/check returns at most 6 users even if more sessions exist."""
    family = _make_family(db)
    device_id = str(uuid4())

    for _ in range(8):
        user = _make_user(db, family.id)
        _make_session(db, user, device_id)

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trusted"] is True
    assert len(data["users"]) <= 6


def test_check_device_excludes_expired_sessions(client, db):
    """device/check does not return users whose sessions have expired."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(db, family.id)
    _make_session(db, user, device_id, expires_at=datetime.utcnow() - timedelta(days=1))

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trusted"] is False
    assert data["users"] == []


def test_check_device_excludes_revoked_sessions(client, db):
    """device/check does not return users whose sessions are revoked."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(db, family.id)
    _make_session(db, user, device_id, is_revoked=True)

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trusted"] is False


def test_check_device_second_factor_type_child(client, db):
    """device/check returns second_factor_type=emoji_pin for child users with pin_hash."""
    family = _make_family(db)
    device_id = str(uuid4())

    child = _make_user(db, family.id, role="child", pin_hash="$2b$12$fakehash")
    _make_session(db, child, device_id)

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    users = data["users"]
    assert len(users) == 1
    assert users[0]["second_factor_type"] == "emoji_pin"


def test_check_device_second_factor_type_adult_totp(client, db):
    """device/check returns second_factor_type for adult with TOTP enabled."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(
        db, family.id, role="member",
        second_factor_enabled=True,
        second_factor_type="totp",
    )
    _make_session(db, user, device_id)

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    users = resp.json()["data"]["users"]
    assert users[0]["second_factor_type"] == "totp"


def test_check_device_no_second_factor(client, db):
    """device/check returns second_factor_type=None for user without 2FA."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(db, family.id, role="member")
    _make_session(db, user, device_id)

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    users = resp.json()["data"]["users"]
    assert users[0]["second_factor_type"] is None


# ─────────────────────────────────────────────────────────────────────────────
# /device/select tests
# ─────────────────────────────────────────────────────────────────────────────

def test_select_device_with_second_factor_returns_temp_token(client, db):
    """device/select returns temp_token when user has a second factor (emoji_pin)."""
    family = _make_family(db)
    device_id = str(uuid4())

    child = _make_user(db, family.id, role="child", pin_hash="$2b$12$fakehash")
    _make_session(db, child, device_id)

    resp = client.post(
        "/api/v1/auth/device/select",
        json={"device_id": device_id, "user_id": str(child.id), "altcha": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["second_factor_required"] is True
    assert data["temp_token"] is not None
    assert data["second_factor_type"] == "emoji_pin"
    assert data["display_name"] == child.display_name
    assert data["avatar_color"] == child.avatar_color


def test_select_device_without_second_factor_sets_cookies(client, db):
    """device/select issues auth cookies directly when user has no 2FA."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(db, family.id, role="member")
    _make_session(db, user, device_id)

    resp = client.post(
        "/api/v1/auth/device/select",
        json={"device_id": device_id, "user_id": str(user.id), "altcha": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["second_factor_required"] is False
    assert data["temp_token"] is None
    # Auth cookies must be set
    assert "access_token" in resp.cookies or "refresh_token" in resp.cookies


def test_select_device_invalid_combo_returns_404(client, db):
    """device/select returns 404 when device_id + user_id combo has no active session."""
    family = _make_family(db)
    device_id = str(uuid4())
    other_device_id = str(uuid4())

    user = _make_user(db, family.id, role="member")
    # Session bound to a DIFFERENT device
    _make_session(db, user, other_device_id)

    resp = client.post(
        "/api/v1/auth/device/select",
        json={"device_id": device_id, "user_id": str(user.id), "altcha": "test"},
    )
    assert resp.status_code == 404


def test_select_device_refreshes_session_expiry(client, db):
    """device/select rolls the session window — expires_at is extended."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(db, family.id, role="member")
    original_expires = datetime.utcnow() + timedelta(days=5)
    session = _make_session(db, user, device_id, expires_at=original_expires)

    resp = client.post(
        "/api/v1/auth/device/select",
        json={"device_id": device_id, "user_id": str(user.id), "altcha": "test"},
    )
    assert resp.status_code == 200

    db.refresh(session)
    # expires_at should have been extended beyond the original 5-day window
    assert session.expires_at > original_expires


def test_select_device_expired_session_returns_404(client, db):
    """device/select returns 404 if the session has already expired."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(db, family.id, role="member")
    _make_session(db, user, device_id, expires_at=datetime.utcnow() - timedelta(days=1))

    resp = client.post(
        "/api/v1/auth/device/select",
        json={"device_id": device_id, "user_id": str(user.id), "altcha": "test"},
    )
    assert resp.status_code == 404


def test_select_device_totp_returns_temp_token(client, db):
    """device/select returns temp_token for adult user with TOTP enabled."""
    family = _make_family(db)
    device_id = str(uuid4())

    user = _make_user(
        db, family.id, role="member",
        second_factor_enabled=True,
        second_factor_type="totp",
    )
    _make_session(db, user, device_id)

    resp = client.post(
        "/api/v1/auth/device/select",
        json={"device_id": device_id, "user_id": str(user.id), "altcha": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["second_factor_required"] is True
    assert data["second_factor_type"] == "totp"
    assert data["temp_token"] is not None
