"""Tests for WebAuthn passkey authentication for child users.

WebAuthn endpoints use child_id in request body (not auth headers).
Tests mock the py_webauthn library since we cannot test actual hardware authenticators.
"""

import base64
import json
from unittest.mock import patch

from apps.backend.app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_owner(client):
    """Register owner and return auth headers."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "owner1",
            "display_name": "Owner",
            "password": "OwnerPass1",
            "family_name": "Test Family",
            "family_invitation_code": "AUT15",
        },
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


def _create_child(client, headers, display_name="WebAuthn Child", username="webautnchild"):
    """Create a child user and return response."""
    resp = client.post(
        "/api/v1/family/children",
        json={
            "username": username,
            "display_name": display_name,
            "password": "ChildPass1",
            "pin": ["🐱", "🐶", "🐸", "🦊"],
        },
        headers=headers,
    )
    return resp


def _make_credential_id() -> str:
    """Generate a fake credential ID (hex string)."""
    return base64.b64encode(b"test-credential-id-12345").hex()


def _make_public_key() -> str:
    """Generate a fake public key (hex string)."""
    return base64.b64encode(b"test-public-key-abcdef").hex()


# ---------------------------------------------------------------------------
# Register options endpoint tests
# ---------------------------------------------------------------------------


def test_webauthn_register_options_returns_challenge(client, db):
    """Register-options endpoint returns WebAuthn challenge."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    assert child_resp.status_code == 201
    child_id = child_resp.json()["data"]["id"]

    # Mock the webauthn helper to return fake options
    mock_options = {
        "challenge": "test-challenge-base64url",
        "rp": {"name": "Numina", "id": "localhost"},
        "user": {"id": child_id, "name": "WebAuthn Child", "displayName": "WebAuthn Child"},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
    }
    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.generate_registration_challenge",
        return_value=mock_options,
    ):
        response = client.post(
            "/api/v1/auth/child/webauthn/register-options",
            json={"child_id": child_id},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "options" in data
        assert "challenge" in data
        assert data["challenge"] == "test-challenge-base64url"


def test_webauthn_register_options_nonexistent_child(client):
    """Register-options returns error for nonexistent child."""
    fake_child_id = "999999999999999999"  # Valid Snowflake ID format, but nonexistent
    response = client.post(
        "/api/v1/auth/child/webauthn/register-options",
        json={"child_id": fake_child_id},
    )
    assert response.status_code == 404


def test_webauthn_register_options_invalid_uuid(client):
    """Register-options returns 422 for invalid child_id format."""
    response = client.post(
        "/api/v1/auth/child/webauthn/register-options",
        json={"child_id": "not-a-uuid"},
    )
    assert response.status_code == 422


def test_webauthn_register_options_excludes_existing_credentials(client, db):
    """Register-options excludes already-registered credentials."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    # Add existing credential
    existing_cred = {
        "id": _make_credential_id(),
        "public_key": _make_public_key(),
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([existing_cred])
    db.commit()

    mock_options = {
        "challenge": "new-challenge",
        "excludeCredentials": [{"id": existing_cred["id"], "type": "public-key"}],
    }
    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.generate_registration_challenge",
        return_value=mock_options,
    ) as mock_gen:
        response = client.post(
            "/api/v1/auth/child/webauthn/register-options",
            json={"child_id": child_id},
        )
        assert response.status_code == 200
        # Verify helper was called with existing_credentials
        call_args = mock_gen.call_args
        assert len(call_args[1]["existing_credentials"]) == 1


# ---------------------------------------------------------------------------
# Register endpoint tests
# ---------------------------------------------------------------------------


def test_webauthn_register_stores_credential(client, db):
    """Register endpoint stores verified credential in user.webauthn_credentials."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    fake_challenge = base64.b64encode(b"test-challenge").decode()
    fake_credential = {
        "id": "cred-id-base64url",
        "rawId": "cred-id-base64url",
        "response": {
            "clientDataJSON": "client-data",
            "attestationObject": "attestation-obj",
        },
        "type": "public-key",
    }
    verified_cred = {
        "id": _make_credential_id(),
        "public_key": _make_public_key(),
        "sign_count": 0,
    }

    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.verify_registration",
        return_value=verified_cred,
    ), patch("apps.backend.app.routers.auth._decode_webauthn_challenge", return_value=b"test-challenge"):
        response = client.post(
            "/api/v1/auth/child/webauthn/register",
            json={
                "child_id": child_id,
                "credential": fake_credential,
                "challenge": fake_challenge,
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["message"] == "passkey registered"

        # Verify credential was stored
        child = db.query(User).filter(User.id == child_id).first()
        stored = json.loads(child.webauthn_credentials)
        assert len(stored) == 1
        assert stored[0]["id"] == verified_cred["id"]


def test_webauthn_register_verification_fails(client, db):
    """Register returns error when WebAuthn verification fails."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.verify_registration",
        side_effect=Exception("Invalid attestation"),
    ), patch("apps.backend.app.routers.auth._decode_webauthn_challenge", return_value=b"test-challenge"):
        response = client.post(
            "/api/v1/auth/child/webauthn/register",
            json={
                "child_id": child_id,
                "credential": {"id": "x", "response": {}},
                "challenge": "invalid-challenge",
            },
        )
        assert response.status_code == 401


def test_webauthn_register_nonexistent_child(client):
    """Register returns 404 for nonexistent child."""
    fake_child_id = "999999999999999999"  # Valid Snowflake ID format, but nonexistent
    response = client.post(
        "/api/v1/auth/child/webauthn/register",
        json={
            "child_id": fake_child_id,
            "credential": {"id": "x", "response": {}},
            "challenge": "challenge",
        },
    )
    assert response.status_code == 404


def test_webauthn_register_appends_to_existing_credentials(client, db):
    """Register appends new credential to existing list."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    # Add existing credential
    existing_cred = {
        "id": "existing-cred-id",
        "public_key": "existing-public-key",
        "sign_count": 5,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([existing_cred])
    db.commit()

    new_cred = {
        "id": _make_credential_id(),
        "public_key": _make_public_key(),
        "sign_count": 0,
    }

    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.verify_registration",
        return_value=new_cred,
    ), patch("apps.backend.app.routers.auth._decode_webauthn_challenge", return_value=b"test-challenge"):
        response = client.post(
            "/api/v1/auth/child/webauthn/register",
            json={
                "child_id": child_id,
                "credential": {"id": "new-cred", "response": {}},
                "challenge": "challenge",
            },
        )
        assert response.status_code == 200

        child = db.query(User).filter(User.id == child_id).first()
        stored = json.loads(child.webauthn_credentials)
        assert len(stored) == 2


# ---------------------------------------------------------------------------
# Login options endpoint tests
# ---------------------------------------------------------------------------


def test_webauthn_login_options_returns_challenge(client, db):
    """Login-options endpoint returns authentication challenge."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    # Add a credential first
    credential = {
        "id": _make_credential_id(),
        "public_key": _make_public_key(),
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([credential])
    db.commit()

    mock_options = {
        "challenge": "auth-challenge-base64url",
        "allowCredentials": [{"id": credential["id"], "type": "public-key"}],
    }
    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.generate_authentication_challenge",
        return_value=mock_options,
    ):
        response = client.post(
            "/api/v1/auth/child/webauthn/login-options",
            json={"child_id": child_id},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "options" in data
        assert "challenge" in data


def test_webauthn_login_options_no_credentials(client, db):
    """Login-options returns error if child has no credentials."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    response = client.post(
        "/api/v1/auth/child/webauthn/login-options",
        json={"child_id": child_id},
    )
    assert response.status_code == 400


def test_webauthn_login_options_nonexistent_child(client):
    """Login-options returns 404 for nonexistent child."""
    fake_child_id = "999999999999999999"  # Valid Snowflake ID format, but nonexistent
    response = client.post(
        "/api/v1/auth/child/webauthn/login-options",
        json={"child_id": fake_child_id},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Login endpoint tests
# ---------------------------------------------------------------------------


def test_webauthn_login_success(client, db):
    """Login endpoint verifies credential and returns tokens."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    cred_id = _make_credential_id()
    public_key = _make_public_key()
    credential = {
        "id": cred_id,
        "public_key": public_key,
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([credential])
    db.commit()

    fake_auth_credential = {
        "id": cred_id,  # Must match stored credential ID exactly
        "rawId": cred_id,
        "response": {
            "clientDataJSON": "client-data",
            "authenticatorData": "auth-data",
            "signature": "signature",
            "userHandle": child_id,
        },
        "type": "public-key",
    }

    verification_result = {"new_sign_count": 1}

    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.verify_authentication",
        return_value=verification_result,
    ), patch("apps.backend.app.routers.auth._decode_webauthn_challenge", return_value=b"auth-challenge"):
        response = client.post(
            "/api/v1/auth/child/webauthn/login",
            json={
                "child_id": child_id,
                "credential": fake_auth_credential,
                "challenge": "auth-challenge",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data

        # Verify sign_count was updated
        child = db.query(User).filter(User.id == child_id).first()
        stored = json.loads(child.webauthn_credentials)
        assert stored[0]["sign_count"] == 1


def test_webauthn_login_wrong_credential(client, db):
    """Login returns error if credential ID not found."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    credential = {
        "id": _make_credential_id(),
        "public_key": _make_public_key(),
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([credential])
    db.commit()

    # Send wrong credential ID
    response = client.post(
        "/api/v1/auth/child/webauthn/login",
        json={
            "child_id": child_id,
            "credential": {"id": "wrong-cred-id", "response": {}},
            "challenge": "challenge",
        },
    )
    assert response.status_code == 404


def test_webauthn_login_no_credentials(client, db):
    """Login returns error if child has no credentials."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    response = client.post(
        "/api/v1/auth/child/webauthn/login",
        json={
            "child_id": child_id,
            "credential": {"id": "x", "response": {}},
            "challenge": "challenge",
        },
    )
    assert response.status_code == 400


def test_webauthn_login_verification_fails(client, db):
    """Login returns error when WebAuthn verification fails."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    cred_id = _make_credential_id()
    credential = {
        "id": cred_id,
        "public_key": _make_public_key(),
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([credential])
    db.commit()

    with patch(
        "apps.backend.app.routers.auth.webauthn_helper.verify_authentication",
        side_effect=Exception("Invalid signature"),
    ), patch("apps.backend.app.routers.auth._decode_webauthn_challenge", return_value=b"challenge"):
        response = client.post(
            "/api/v1/auth/child/webauthn/login",
            json={
                "child_id": child_id,
                "credential": {"id": cred_id, "response": {}},
                "challenge": "challenge",
            },
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Credential storage tests
# ---------------------------------------------------------------------------


def test_webauthn_credential_storage(db, client):
    """WebAuthn credential is stored in user.webauthn_credentials."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    credential = {
        "id": "test-credential-id",
        "public_key": base64.b64encode(b"test-public-key").decode(),
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([credential])
    db.commit()
    db.refresh(child)

    stored = json.loads(child.webauthn_credentials)
    assert len(stored) == 1
    assert stored[0]["id"] == "test-credential-id"


def test_webauthn_multiple_credentials(db, client):
    """User can have multiple WebAuthn credentials."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    creds = [
        {"id": "cred-1", "public_key": "key-1", "sign_count": 0},
        {"id": "cred-2", "public_key": "key-2", "sign_count": 5},
    ]
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps(creds)
    db.commit()

    stored = json.loads(child.webauthn_credentials)
    assert len(stored) == 2


def test_webauthn_sign_count_increment(db, client):
    """Sign count increments on successful authentication."""
    headers = _register_owner(client)
    child_resp = _create_child(client, headers)
    child_id = child_resp.json()["data"]["id"]

    credential = {
        "id": "test-id",
        "public_key": base64.b64encode(b"test-key").decode(),
        "sign_count": 0,
    }
    child = db.query(User).filter(User.id == child_id).first()
    child.webauthn_credentials = json.dumps([credential])
    db.commit()

    # Simulate auth with higher sign_count
    stored = json.loads(child.webauthn_credentials)
    stored[0]["sign_count"] = 5
    child.webauthn_credentials = json.dumps(stored)
    db.commit()

    assert json.loads(child.webauthn_credentials)[0]["sign_count"] == 5