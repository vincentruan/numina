"""WebAuthn device authentication tests."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from apps.backend.app.models.device_session import DeviceSession
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id


def _create_user_and_family(db):
    """Create a user with family for device webauthn tests."""
    family = Family(id=next_id(), name="WebAuthn Test Family", created_by=next_id())
    db.add(family)
    db.flush()

    user = User(
        id=next_id(),
        username="webauthn_user",
        display_name="WebAuthn User",
        password_hash="test_hash",
        family_id=family.id,
        avatar_color="#4A90D9",
        role="owner",
    )
    db.add(user)
    db.flush()
    return user, family


def _create_device_session(db, user, family, device_id="test-device-001"):
    """Create a valid device session."""
    now = datetime.utcnow()
    session = DeviceSession(
        user_id=user.id,
        family_id=family.id,
        device_id=device_id,
        device_name="Test Device",
        refresh_jti=f"test-jti-{next_id()}",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=30),
        is_revoked=False,
    )
    db.add(session)
    db.flush()
    return session


def test_webauthn_auth_options_success(client, db_session):
    """GET auth options returns challenge when user has passkey on trusted device."""
    user, family = _create_user_and_family(db_session)
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff001122", "sign_count": 0}
    ])
    db_session.flush()

    _create_device_session(db_session, user, family, "test-device-wa-001")

    with patch("apps.backend.app.auth.webauthn.generate_authentication_options") as mock_gen:
        # Mock the webauthn library's generate_authentication_options
        from unittest.mock import MagicMock
        mock_options = MagicMock()
        mock_gen.return_value = mock_options

        with patch("apps.backend.app.auth.webauthn.options_to_json") as mock_to_json:
            mock_to_json.return_value = json.dumps({
                "challenge": "dGVzdC1jaGFsbGVuZ2U",
                "allowCredentials": [{"id": "aabbcc", "type": "public-key"}],
                "timeout": 60000,
            })

            resp = client.post("/api/v1/auth/device/webauthn/auth-options", json={
                "device_id": "test-device-wa-001",
                "user_id": str(user.id),
            })

    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", body)
    assert "options" in data
    assert "challenge" in data
    assert len(data["challenge"]) > 0


def test_webauthn_auth_options_no_passkey(client, db_session):
    """Returns error when user has no passkey."""
    user, family = _create_user_and_family(db_session)
    # No webauthn_credentials set
    _create_device_session(db_session, user, family, "test-device-wa-002")

    resp = client.post("/api/v1/auth/device/webauthn/auth-options", json={
        "device_id": "test-device-wa-002",
        "user_id": str(user.id),
    })
    # AUTH_DEVICE_NOT_FOUND maps to an error response
    assert resp.status_code in (404, 400, 422)


def test_webauthn_auth_options_no_device_session(client, db_session):
    """Returns error when device session doesn't exist."""
    user, family = _create_user_and_family(db_session)
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff001122", "sign_count": 0}
    ])
    db_session.flush()

    resp = client.post("/api/v1/auth/device/webauthn/auth-options", json={
        "device_id": "nonexistent-device",
        "user_id": str(user.id),
    })
    assert resp.status_code in (404, 400, 422)


def test_webauthn_verify_no_2fa(client, db_session):
    """Verify endpoint issues tokens directly when user has no 2FA."""
    user, family = _create_user_and_family(db_session)
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff001122", "sign_count": 1}
    ])
    db_session.flush()

    _create_device_session(db_session, user, family, "test-device-wa-003")

    mock_credential = {"id": "aabbcc", "rawId": "aabbcc", "type": "public-key", "response": {}}

    with patch("apps.backend.app.auth.webauthn.verify_authentication_response") as mock_verify:
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.new_sign_count = 2
        mock_verify.return_value = mock_result

        resp = client.post("/api/v1/auth/device/webauthn/verify", json={
            "device_id": "test-device-wa-003",
            "user_id": str(user.id),
            "credential": mock_credential,
            "challenge": "dGVzdC1jaGFsbGVuZ2U",
        })

    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", body)
    assert data["second_factor_required"] is False


def test_webauthn_verify_with_2fa(client, db_session):
    """Verify endpoint returns temp_token when user has 2FA enabled."""
    user, family = _create_user_and_family(db_session)
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff001122", "sign_count": 1}
    ])
    user.second_factor_enabled = True
    user.second_factor_type = "numeric_pin"
    db_session.flush()

    _create_device_session(db_session, user, family, "test-device-wa-004")

    mock_credential = {"id": "aabbcc", "rawId": "aabbcc", "type": "public-key", "response": {}}

    with patch("apps.backend.app.auth.webauthn.verify_authentication_response") as mock_verify:
        from unittest.mock import MagicMock
        mock_result = MagicMock()
        mock_result.new_sign_count = 2
        mock_verify.return_value = mock_result

        resp = client.post("/api/v1/auth/device/webauthn/verify", json={
            "device_id": "test-device-wa-004",
            "user_id": str(user.id),
            "credential": mock_credential,
            "challenge": "dGVzdC1jaGFsbGVuZ2U",
        })

    assert resp.status_code == 200
    body = resp.json()
    data = body.get("data", body)
    assert data["second_factor_required"] is True
    assert data["temp_token"] is not None
    assert data["second_factor_type"] == "numeric_pin"


def test_webauthn_verify_wrong_credential(client, db_session):
    """Verify endpoint rejects credential that doesn't match stored ones."""
    user, family = _create_user_and_family(db_session)
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff001122", "sign_count": 1}
    ])
    db_session.flush()

    _create_device_session(db_session, user, family, "test-device-wa-005")

    mock_credential = {"id": "wrong-id", "rawId": "wrong", "type": "public-key", "response": {}}

    resp = client.post("/api/v1/auth/device/webauthn/verify", json={
        "device_id": "test-device-wa-005",
        "user_id": str(user.id),
        "credential": mock_credential,
        "challenge": "dGVzdC1jaGFsbGVuZ2U",
    })

    assert resp.status_code in (401, 400, 422)


def test_trust_webauthn_register_options(client, db_session):
    """Authenticated user can get WebAuthn registration options."""
    from apps.backend.app.auth.deps import create_access_token

    user, family = _create_user_and_family(db_session)
    claims = {"sub": str(user.id), "fid": str(family.id), "role": user.role}
    token = create_access_token(claims)

    resp = client.post(
        "/api/v1/auth/device/trust/webauthn/register-options",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert "options" in data
    assert "challenge" in data
    assert data["options"]["rp"]["name"] == "Numina"


def test_trust_webauthn_register_options_unauthenticated(client):
    """Unauthenticated request is rejected."""
    resp = client.post("/api/v1/auth/device/trust/webauthn/register-options")
    assert resp.status_code in (401, 403)


def test_trust_webauthn_register_success(client, db_session):
    """Authenticated user can register a WebAuthn credential."""
    from unittest.mock import MagicMock
    from apps.backend.app.auth.deps import create_access_token

    user, family = _create_user_and_family(db_session)
    claims = {"sub": str(user.id), "fid": str(family.id), "role": user.role}
    token = create_access_token(claims)

    mock_credential = {
        "id": "new-cred-id",
        "rawId": "bmV3LWNyZWQtaWQ",
        "type": "public-key",
        "response": {
            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
            "attestationObject": "o2NmbXRkbm9uZQ",
        },
    }

    mock_verification = MagicMock()
    mock_verification.credential_id = bytes.fromhex("aabb")
    mock_verification.credential_public_key = bytes.fromhex("ccdd")
    mock_verification.sign_count = 0

    with patch("apps.backend.app.auth.webauthn.verify_registration_response", return_value=mock_verification):
        resp = client.post(
            "/api/v1/auth/device/trust/webauthn/register",
            json={
                "credential": mock_credential,
                "challenge": "dGVzdC1jaGFsbGVuZ2U",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json().get("data", resp.json())["registered"] is True

    # Verify credential was stored
    db_session.refresh(user)
    creds = json.loads(user.webauthn_credentials)
    assert len(creds) == 1
    assert creds[0]["id"] == "aabb"
