from datetime import datetime, timedelta

import pytest

from apps.backend.app.models.device_session import DeviceSession
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.services import device as device_service


def test_device_session_model_exists(db):
    """DeviceSession table is created and can be queried."""
    count = db.query(DeviceSession).count()
    assert count == 0


def _make_family(db) -> Family:
    from apps.backend.app.utils.snowflake import next_id
    fid = next_id()
    family = Family(id=fid, name="TestFamily", invite_code="XXXXXX", created_by=fid)
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


def _make_user(db, family_id: int, role: str = "owner") -> User:
    import bcrypt

    from apps.backend.app.utils.snowflake import next_id
    user = User(
        id=next_id(),
        family_id=family_id,
        username=f"user_{next_id()}",
        display_name="Test",
        password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_device_session(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    session = device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="test-jti-1", device_name="iPhone · Safari"
    )
    assert session.refresh_jti == "test-jti-1"
    assert session.device_name == "iPhone · Safari"
    assert not session.is_revoked
    assert session.expires_at > datetime.utcnow() + timedelta(days=29)


def test_list_device_sessions(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="jti-a", device_name="iPhone · Safari"
    )
    device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="jti-b", device_name="Android · Chrome"
    )
    sessions = device_service.list_device_sessions(db, user_id=user.id)
    assert len(sessions) == 2


def test_revoke_device_session(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    session = device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="jti-revoke", device_name="iPad · Safari"
    )
    device_service.revoke_device_session(db, device_id=session.id, user_id=user.id)
    db.refresh(session)
    assert session.is_revoked


def test_revoke_device_session_wrong_user(db):
    from apps.backend.app.errors import AppError
    family = _make_family(db)
    user1 = _make_user(db, family.id)
    user2 = _make_user(db, family.id, role="member")
    session = device_service.create_device_session(
        db, user_id=user1.id, family_id=family.id,
        refresh_jti="jti-other", device_name="Mac · Chrome"
    )
    with pytest.raises(AppError):
        device_service.revoke_device_session(db, device_id=session.id, user_id=user2.id)


def test_rotate_device_session_jti(db):
    family = _make_family(db)
    user = _make_user(db, family.id)
    session = device_service.create_device_session(
        db, user_id=user.id, family_id=family.id,
        refresh_jti="old-jti", device_name="iPhone · Safari"
    )
    device_service.rotate_device_session_jti(db, old_jti="old-jti", new_jti="new-jti")
    db.refresh(session)
    assert session.refresh_jti == "new-jti"


def test_trust_device_endpoint(client, auth_headers):
    """POST /auth/device/trust creates a DeviceSession and returns device info."""
    response = client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "session_id" in data
    assert "device_id" in data
    assert len(data["device_id"]) == 36  # UUID v4 format
    assert "device_name" in data
    assert "expires_at" in data


def test_list_devices_endpoint(client, auth_headers):
    """GET /auth/devices returns list of trusted devices."""
    client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    response = client.get(
        "/api/v1/auth/devices",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    assert response.status_code == 200
    devices = response.json()["data"]
    assert isinstance(devices, list)
    assert len(devices) >= 1
    assert "session_id" in devices[0]
    assert "device_id" in devices[0]
    assert "device_name" in devices[0]
    assert "is_current" in devices[0]


def test_revoke_device_endpoint(client, auth_headers):
    """DELETE /auth/devices/{id} revokes a device session."""
    trust_resp = client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    session_id = trust_resp.json()["data"]["session_id"]
    response = client.delete(
        f"/api/v1/auth/devices/{session_id}",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    assert response.status_code == 200
    list_resp = client.get(
        "/api/v1/auth/devices",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    ids = [d["session_id"] for d in list_resp.json()["data"]]
    assert session_id not in ids


def test_revoke_all_devices_endpoint(client, auth_headers):
    """DELETE /auth/devices revokes all device sessions."""
    client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    response = client.delete(
        "/api/v1/auth/devices",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert response.status_code == 200
    list_resp = client.get(
        "/api/v1/auth/devices",
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert list_resp.json()["data"] == []


def test_refresh_rotates_device_session_jti(client, auth_headers, db):
    """Token refresh updates DeviceSession.refresh_jti in-place."""
    # Trust device first
    trust_resp = client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    assert trust_resp.status_code == 200
    session_id = trust_resp.json()["data"]["session_id"]

    # Refresh token
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_headers["_refresh_token"]},
    )
    assert refresh_resp.status_code == 200

    # Device session should still exist (not revoked) after refresh
    new_access_token = refresh_resp.json()["data"]["access_token"]
    list_resp = client.get(
        "/api/v1/auth/devices",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert list_resp.status_code == 200
    device_session_ids = [d["session_id"] for d in list_resp.json()["data"]]
    assert session_id in device_session_ids


def test_check_device_trusted(client, auth_headers):
    """POST /auth/device/check with valid device_id returns trusted=true."""
    trust_resp = client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    device_id = trust_resp.json()["data"]["device_id"]

    check_resp = client.post(
        "/api/v1/auth/device/check",
        json={"device_id": device_id},
    )
    assert check_resp.status_code == 200
    data = check_resp.json()["data"]
    assert data["trusted"] is True
    assert data["temp_token"] is not None
    assert data["display_name"] is not None


def test_check_device_not_trusted(client):
    """POST /auth/device/check with unknown device_id returns trusted=false."""
    check_resp = client.post(
        "/api/v1/auth/device/check",
        json={"device_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert check_resp.status_code == 200
    data = check_resp.json()["data"]
    assert data["trusted"] is False


def test_trust_device_reuses_session(client, auth_headers, db):
    """Trust with same device_id reuses existing session (no new row)."""
    trust_resp1 = client.post(
        "/api/v1/auth/device/trust",
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": auth_headers["_refresh_token"]},
    )
    assert trust_resp1.status_code == 200
    device_id = trust_resp1.json()["data"]["device_id"]
    session_id_1 = trust_resp1.json()["data"]["session_id"]

    # First call rotated the refresh token. Use the new one on the next call,
    # mirroring how a real browser session would carry forward the new cookie.
    new_refresh_token = trust_resp1.cookies.get("refresh_token")
    assert new_refresh_token is not None

    # Count sessions before second trust
    count_before = db.query(DeviceSession).filter(
        DeviceSession.device_id == device_id,
        DeviceSession.is_revoked.is_(False),
    ).count()

    trust_resp2 = client.post(
        "/api/v1/auth/device/trust",
        json={"device_id": device_id},
        headers={"Authorization": auth_headers["Authorization"]},
        cookies={"refresh_token": new_refresh_token},
    )
    assert trust_resp2.status_code == 200
    session_id_2 = trust_resp2.json()["data"]["session_id"]

    # Same session row was reused
    assert session_id_1 == session_id_2

    # No new row was created
    count_after = db.query(DeviceSession).filter(
        DeviceSession.device_id == device_id,
        DeviceSession.is_revoked.is_(False),
    ).count()
    assert count_after == count_before
