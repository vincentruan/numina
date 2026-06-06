# WebAuthn 设备信任改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the multi-layer software device identity (cookie + localStorage + IndexedDB + ETag) with WebAuthn hardware-bound credentials for trusted device verification, while keeping ALTCHA as fallback for devices that don't support WebAuthn.

**Architecture:** WebAuthn credentials (stored in OS keychain/Secure Enclave) prove device ownership cryptographically. A single `numina_device_id` cookie remains for device _discovery_ (finding which accounts are bound). After discovery, WebAuthn replaces ALTCHA as the identity verification step. For non-WebAuthn devices, ALTCHA remains the gatekeeper. FingerprintJS is removed entirely.

**Tech Stack:** py_webauthn (already installed), Web Authentication API (navigator.credentials), FastAPI, Vue 3 + TypeScript, SQLAlchemy

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Simplify | `frontend/packages/auth/src/utils/deviceIdentity.ts` | Reduce to cookie-only read/write (remove IDB, localStorage, ETag) |
| Delete endpoint | `server/apps/backend/app/routers/device.py` → `/device-ping` | Remove ETag recovery endpoint |
| Modify schema | `server/apps/backend/app/schemas/device.py` | Add `has_passkey` to `DeviceCheckUserItem`; add WebAuthn auth schemas |
| Add endpoint | `server/apps/backend/app/routers/device.py` | `POST /device/webauthn/auth-options` and `POST /device/webauthn/verify` |
| Modify endpoint | `server/apps/backend/app/routers/device.py` → `/device/trust` | Add optional WebAuthn registration during trust |
| Add schemas | `server/apps/backend/app/schemas/device.py` | `DeviceWebAuthnAuthOptionsRequest`, `DeviceWebAuthnVerifyRequest`, `DeviceTrustRequest` extension |
| Modify | `frontend/apps/main/src/api/device.ts` | Add WebAuthn auth API calls; add `has_passkey` to types |
| Modify | `frontend/apps/main/src/pages/LoginPage.vue` | Integrate WebAuthn branch in Step 0 |
| Modify | `frontend/apps/main/src/pages/LoginPage.vue` | ALTCHA auto-solve on mount for non-WebAuthn path |
| Remove dep | `frontend/packages/auth/package.json` | Remove `@fingerprintjs/fingerprintjs` if present |
| Add test | `server/tests/backend/test_device_webauthn.py` | WebAuthn device auth flow tests |
| Modify test | `server/tests/backend/test_device_multi_account.py` | Update for simplified device_id + has_passkey field |

---

## Task 1: Simplify `deviceIdentity.ts` — Cookie Only

**Files:**
- Modify: `frontend/packages/auth/src/utils/deviceIdentity.ts`

The current file has ~100 lines managing cookie + localStorage + IndexedDB + ETag recovery. Replace with a minimal cookie-only implementation.

- [ ] **Step 1: Rewrite deviceIdentity.ts to cookie-only**

```typescript
const COOKIE_NAME = 'numina_device_id'

export function readDeviceId(): string | null {
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export function writeDeviceId(deviceId: string): void {
  // Cookie is set by the server via Set-Cookie on /device/trust.
  // This is a JS-side mirror for cases where we need to write client-side.
  const maxAge = 90 * 24 * 3600
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(deviceId)}; path=/; max-age=${maxAge}; samesite=lax`
}

export function clearDeviceId(): void {
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`
}
```

- [ ] **Step 2: Remove recoverFromEtag export**

Remove the `recoverFromEtag` function entirely. Search all imports of `recoverFromEtag` in the frontend and remove them.

- [ ] **Step 3: Remove getDeviceFingerprint if exported from @numina/auth**

Check `frontend/packages/auth/src/index.ts` for `getDeviceFingerprint` export. Remove it and any FingerprintJS dependency from `package.json`.

- [ ] **Step 4: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend && pnpm -r typecheck`
Expected: PASS (fix any broken imports referencing removed functions)

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/auth/
git commit -m "$(cat <<'EOF'
refactor(auth): simplify deviceIdentity to cookie-only

Remove IndexedDB, localStorage, and ETag recovery layers.
WebAuthn credentials in OS keychain replace multi-layer persistence.
Remove FingerprintJS dependency.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Remove `/device-ping` ETag Endpoint

**Files:**
- Modify: `server/apps/backend/app/routers/device.py` (remove `device_ping` function, lines ~258-275)

- [ ] **Step 1: Delete the endpoint**

Remove the `device_ping` route handler from `device.py`:

```python
# DELETE THIS ENTIRE BLOCK:
@router.get("/device-ping", include_in_schema=False)
def device_ping(request: Request, response: Response):
    ...
```

- [ ] **Step 2: Run backend tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/backend/tests/ -v -k "device" 2>&1 | tail -30`
Expected: PASS (any test referencing `/device-ping` should be removed or updated)

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/routers/device.py
git commit -m "$(cat <<'EOF'
refactor(device): remove /device-ping ETag recovery endpoint

No longer needed — WebAuthn credentials survive browser data clearing.
Single cookie is sufficient for device discovery.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Backend — Add `has_passkey` to Device Check Response

**Files:**
- Modify: `server/apps/backend/app/schemas/device.py`
- Modify: `server/apps/backend/app/routers/device.py` (in `check_device`)
- Test: `server/tests/backend/test_device_multi_account.py`

- [ ] **Step 1: Write the failing test**

In `server/tests/backend/test_device_webauthn.py` (new file):

```python
"""WebAuthn device trust integration tests."""

import json

import pytest
from fastapi.testclient import TestClient


def test_device_check_returns_has_passkey(client: TestClient, db_session):
    """Device check response includes has_passkey for each user."""
    from tests.backend.conftest import create_trusted_device_user

    user, device_id = create_trusted_device_user(db_session, display_name="Alice")

    # No WebAuthn credentials yet
    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["trusted"] is True
    assert data["users"][0]["has_passkey"] is False

    # Add a WebAuthn credential
    user.webauthn_credentials = json.dumps([
        {"id": "abc123", "public_key": "def456", "sign_count": 0}
    ])
    db_session.commit()

    resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
    data = resp.json()
    assert data["users"][0]["has_passkey"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_webauthn.py::test_device_check_returns_has_passkey -v`
Expected: FAIL (field `has_passkey` not in response / test helper not found)

- [ ] **Step 3: Add `has_passkey` to schema**

In `server/apps/backend/app/schemas/device.py`, add the field to `DeviceCheckUserItem`:

```python
class DeviceCheckUserItem(SnowflakeBase):
    user_id: int
    display_name: str
    avatar_color: str
    role: str
    second_factor_type: str | None
    has_passkey: bool
    last_seen_at: datetime
```

- [ ] **Step 4: Populate `has_passkey` in the router**

In `server/apps/backend/app/routers/device.py`, in the `check_device` function, after fetching users, add passkey detection:

```python
# Inside the loop building items:
has_passkey = bool(user.webauthn_credentials and user.webauthn_credentials.strip() != "[]")

items.append(
    DeviceCheckUserItem(
        user_id=user.id,
        display_name=user.display_name,
        avatar_color=user.avatar_color,
        role=user.role,
        second_factor_type=second_factor_type,
        has_passkey=has_passkey,
        last_seen_at=s.last_seen_at,
    )
)
```

- [ ] **Step 5: Create test helper if needed and run test**

Ensure `tests/backend/conftest.py` has a helper to create a user with a trusted device session. If missing, add one. Then run:

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_webauthn.py::test_device_check_returns_has_passkey -v`
Expected: PASS

- [ ] **Step 6: Update existing device tests for new field**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_multi_account.py -v`

If any tests fail because response now includes `has_passkey`, update assertions to include it.

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/schemas/device.py server/apps/backend/app/routers/device.py server/tests/backend/test_device_webauthn.py
git commit -m "$(cat <<'EOF'
feat(device): add has_passkey field to device check response

Frontend uses this to decide whether to trigger WebAuthn or ALTCHA
after user selects an account from the carousel.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Backend — WebAuthn Device Auth Endpoints

**Files:**
- Modify: `server/apps/backend/app/schemas/device.py` (add request/response schemas)
- Modify: `server/apps/backend/app/routers/device.py` (add two endpoints)
- Test: `server/tests/backend/test_device_webauthn.py`

These endpoints allow a user to authenticate via WebAuthn from Step 0 (no prior auth needed, similar to `/device/select`).

- [ ] **Step 1: Add schemas**

In `server/apps/backend/app/schemas/device.py`:

```python
from typing import Any

class DeviceWebAuthnAuthOptionsRequest(BaseModel):
    """Request challenge for WebAuthn device authentication."""
    device_id: str
    user_id: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v.isdigit() or len(v) > 20:
            raise ValueError("invalid user_id")
        return v


class DeviceWebAuthnAuthOptionsResponse(BaseModel):
    """WebAuthn authentication challenge."""
    options: dict[str, Any]
    challenge: str


class DeviceWebAuthnVerifyRequest(BaseModel):
    """Submit WebAuthn authentication response."""
    device_id: str
    user_id: str
    credential: dict[str, Any]
    challenge: str

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v.isdigit() or len(v) > 20:
            raise ValueError("invalid user_id")
        return v


class DeviceWebAuthnVerifyResponse(BaseModel):
    """Result after WebAuthn verification — same shape as DeviceSelectResponse."""
    second_factor_required: bool
    temp_token: str | None = None
    second_factor_type: str | None = None
    display_name: str | None = None
    avatar_color: str | None = None
```

- [ ] **Step 2: Write the failing test for auth-options**

In `server/tests/backend/test_device_webauthn.py`:

```python
def test_webauthn_auth_options_returns_challenge(client: TestClient, db_session):
    """POST /device/webauthn/auth-options returns a challenge when user has passkey."""
    from tests.backend.conftest import create_trusted_device_user

    user, device_id = create_trusted_device_user(db_session, display_name="Alice")
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff", "sign_count": 0}
    ])
    db_session.commit()

    resp = client.post("/api/v1/auth/device/webauthn/auth-options", json={
        "device_id": device_id,
        "user_id": str(user.id),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "options" in data
    assert "challenge" in data
    assert data["options"]["allowCredentials"][0]["id"] is not None


def test_webauthn_auth_options_rejects_no_passkey(client: TestClient, db_session):
    """POST /device/webauthn/auth-options returns 404 when user has no passkey."""
    from tests.backend.conftest import create_trusted_device_user

    user, device_id = create_trusted_device_user(db_session, display_name="Bob")
    # No webauthn_credentials set

    resp = client.post("/api/v1/auth/device/webauthn/auth-options", json={
        "device_id": device_id,
        "user_id": str(user.id),
    })
    assert resp.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_webauthn.py -v -k "auth_options"`
Expected: FAIL (endpoint not found → 404 or 405)

- [ ] **Step 4: Implement `POST /device/webauthn/auth-options`**

In `server/apps/backend/app/routers/device.py`:

```python
@router.post("/device/webauthn/auth-options", response_model=DeviceWebAuthnAuthOptionsResponse)
def device_webauthn_auth_options(
    req: DeviceWebAuthnAuthOptionsRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate WebAuthn authentication challenge for device-bound user.

    No auth required — used in Step 0 before login. Rate-limited by IP.
    """
    import base64
    import json as json_module

    from apps.backend.app.auth.webauthn import generate_authentication_challenge
    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    from datetime import datetime
    now = datetime.utcnow()
    user_id = int(req.user_id)

    # Verify device session exists for this user
    session = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    # Parse stored credentials
    credentials = json_module.loads(user.webauthn_credentials or "[]")
    if not credentials:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    options = generate_authentication_challenge(credentials)
    challenge = options.get("challenge", "")

    return DeviceWebAuthnAuthOptionsResponse(options=options, challenge=challenge)
```

- [ ] **Step 5: Run auth-options tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_webauthn.py -v -k "auth_options"`
Expected: PASS

- [ ] **Step 6: Write the failing test for verify**

In `server/tests/backend/test_device_webauthn.py`:

```python
from unittest.mock import patch


def test_webauthn_verify_success_no_2fa(client: TestClient, db_session):
    """POST /device/webauthn/verify issues tokens when user has no 2FA."""
    from tests.backend.conftest import create_trusted_device_user

    user, device_id = create_trusted_device_user(db_session, display_name="Alice")
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff0011", "sign_count": 1}
    ])
    db_session.commit()

    mock_credential = {"id": "aabbcc", "rawId": "aabbcc", "type": "public-key", "response": {}}

    with patch("apps.backend.app.routers.device.verify_authentication") as mock_verify:
        mock_verify.return_value = {"new_sign_count": 2}
        resp = client.post("/api/v1/auth/device/webauthn/verify", json={
            "device_id": device_id,
            "user_id": str(user.id),
            "credential": mock_credential,
            "challenge": "dGVzdC1jaGFsbGVuZ2U",  # base64url("test-challenge")
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["second_factor_required"] is False


def test_webauthn_verify_success_with_2fa(client: TestClient, db_session):
    """POST /device/webauthn/verify returns temp_token when user has 2FA."""
    from tests.backend.conftest import create_trusted_device_user

    user, device_id = create_trusted_device_user(db_session, display_name="Alice")
    user.webauthn_credentials = json.dumps([
        {"id": "aabbcc", "public_key": "ddeeff0011", "sign_count": 1}
    ])
    user.second_factor_enabled = True
    user.second_factor_type = "numeric_pin"
    db_session.commit()

    mock_credential = {"id": "aabbcc", "rawId": "aabbcc", "type": "public-key", "response": {}}

    with patch("apps.backend.app.routers.device.verify_authentication") as mock_verify:
        mock_verify.return_value = {"new_sign_count": 2}
        resp = client.post("/api/v1/auth/device/webauthn/verify", json={
            "device_id": device_id,
            "user_id": str(user.id),
            "credential": mock_credential,
            "challenge": "dGVzdC1jaGFsbGVuZ2U",
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["second_factor_required"] is True
    assert data["temp_token"] is not None
    assert data["second_factor_type"] == "numeric_pin"
```

- [ ] **Step 7: Implement `POST /device/webauthn/verify`**

In `server/apps/backend/app/routers/device.py`:

```python
@router.post("/device/webauthn/verify", response_model=DeviceWebAuthnVerifyResponse)
def device_webauthn_verify(
    req: DeviceWebAuthnVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Verify WebAuthn authentication — replaces ALTCHA for passkey-enabled users.

    On success: same behavior as /device/select (issue tokens or temp_token).
    No ALTCHA required — biometric IS the proof of presence.
    """
    import base64
    import json as json_module
    from datetime import datetime, timedelta

    from apps.backend.app.auth.cookies import set_auth_cookies
    from apps.backend.app.auth.deps import (
        create_access_token,
        create_refresh_token,
        create_temp_token,
    )
    from apps.backend.app.auth.webauthn import verify_authentication
    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    now = datetime.utcnow()
    user_id = int(req.user_id)

    # Verify device session exists
    session = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)

    # Find the matching credential
    credentials = json_module.loads(user.webauthn_credentials or "[]")
    credential_id = req.credential.get("id", "")
    matched = next((c for c in credentials if c["id"] == credential_id), None)
    if not matched:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # Verify the WebAuthn assertion
    expected_challenge = base64.urlsafe_b64decode(req.challenge + "==")
    try:
        result = verify_authentication(
            credential=req.credential,
            expected_challenge=expected_challenge,
            credential_public_key=bytes.fromhex(matched["public_key"]),
            credential_current_sign_count=matched["sign_count"],
        )
    except Exception:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # Update sign_count
    matched["sign_count"] = result["new_sign_count"]
    user.webauthn_credentials = json_module.dumps(credentials)

    # Refresh device session
    session.last_seen_at = now
    session.expires_at = now + timedelta(days=settings.DEVICE_TRUST_EXPIRE_DAYS)
    db.commit()

    # Determine second factor
    if user.role == "child" and user.pin_hash:
        second_factor_type = "emoji_pin"
    elif user.second_factor_enabled and user.second_factor_type:
        second_factor_type = user.second_factor_type
    else:
        second_factor_type = None

    if second_factor_type:
        temp_token = create_temp_token(user.id, user.role)
        return DeviceWebAuthnVerifyResponse(
            second_factor_required=True,
            temp_token=temp_token,
            second_factor_type=second_factor_type,
            display_name=user.display_name,
            avatar_color=user.avatar_color,
        )

    # No 2FA — issue tokens directly
    claims = {"sub": str(user.id), "fid": str(user.family_id), "role": user.role}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)
    set_auth_cookies(response, access_token, refresh_token)

    return DeviceWebAuthnVerifyResponse(second_factor_required=False)
```

- [ ] **Step 8: Run all WebAuthn device tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_webauthn.py -v`
Expected: PASS

- [ ] **Step 9: Run full device test suite**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/ -v -k "device" 2>&1 | tail -30`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add server/apps/backend/app/schemas/device.py server/apps/backend/app/routers/device.py server/tests/backend/test_device_webauthn.py
git commit -m "$(cat <<'EOF'
feat(device): add WebAuthn device authentication endpoints

POST /device/webauthn/auth-options — generate challenge for passkey user
POST /device/webauthn/verify — verify biometric, issue tokens or temp_token

Replaces ALTCHA for users with registered passkeys on trusted devices.
Same response shape as /device/select for seamless frontend integration.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Backend — WebAuthn Registration During Device Trust

**Files:**
- Modify: `server/apps/backend/app/schemas/device.py` (`DeviceTrustRequest`)
- Modify: `server/apps/backend/app/routers/device.py` (`trust_device`)
- Add schemas for registration flow: `DeviceTrustWebAuthnRegisterRequest`, `DeviceTrustWebAuthnRegisterResponse`
- Test: `server/tests/backend/test_device_webauthn.py`

After login, when user clicks "trust this device", the frontend can optionally register a WebAuthn credential in the same flow.

- [ ] **Step 1: Add registration schemas**

In `server/apps/backend/app/schemas/device.py`:

```python
class DeviceTrustWebAuthnOptionsResponse(BaseModel):
    """Registration options for WebAuthn during device trust."""
    options: dict[str, Any]
    challenge: str


class DeviceTrustWebAuthnRegisterRequest(BaseModel):
    """Complete WebAuthn registration during device trust."""
    credential: dict[str, Any]
    challenge: str
```

- [ ] **Step 2: Write the failing test**

```python
def test_device_trust_webauthn_register_options(authed_client: TestClient):
    """POST /device/trust/webauthn/register-options returns registration challenge."""
    resp = authed_client.post("/api/v1/auth/device/trust/webauthn/register-options")
    assert resp.status_code == 200
    data = resp.json()
    assert "options" in data
    assert "challenge" in data


def test_device_trust_webauthn_register(authed_client: TestClient, db_session):
    """POST /device/trust/webauthn/register stores credential on user."""
    mock_credential = {
        "id": "new-cred-id",
        "rawId": "bmV3LWNyZWQtaWQ",
        "type": "public-key",
        "response": {
            "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
            "attestationObject": "o2NmbXRkbm9uZQ",
        },
    }

    with patch("apps.backend.app.routers.device.verify_registration") as mock_verify:
        mock_verify.return_value = {
            "id": "aabb",
            "public_key": "ccdd",
            "sign_count": 0,
        }
        resp = authed_client.post("/api/v1/auth/device/trust/webauthn/register", json={
            "credential": mock_credential,
            "challenge": "dGVzdC1jaGFsbGVuZ2U",
        })

    assert resp.status_code == 200
    assert resp.json()["registered"] is True
```

- [ ] **Step 3: Implement registration endpoints**

In `server/apps/backend/app/routers/device.py`:

```python
@router.post("/device/trust/webauthn/register-options", response_model=DeviceTrustWebAuthnOptionsResponse)
def device_trust_webauthn_register_options(
    request: Request,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Generate WebAuthn registration options for the authenticated user."""
    import json as json_module

    from apps.backend.app.auth.webauthn import generate_registration_challenge
    from apps.backend.app.models.user import User

    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    existing = json_module.loads(user.webauthn_credentials or "[]")
    options = generate_registration_challenge(
        user_id=str(user.id),
        display_name=user.display_name,
        existing_credentials=existing,
    )
    challenge = options.get("challenge", "")
    return DeviceTrustWebAuthnOptionsResponse(options=options, challenge=challenge)


@router.post("/device/trust/webauthn/register")
def device_trust_webauthn_register(
    req: DeviceTrustWebAuthnRegisterRequest,
    request: Request,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Complete WebAuthn registration — store credential on user."""
    import base64
    import json as json_module

    from apps.backend.app.auth.webauthn import verify_registration
    from apps.backend.app.models.user import User

    payload = _get_user_payload(access_token_cookie, child_access_token_cookie, request)
    user_id = int(payload["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    expected_challenge = base64.urlsafe_b64decode(req.challenge + "==")
    try:
        verified = verify_registration(
            credential=req.credential,
            expected_challenge=expected_challenge,
        )
    except Exception:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS)

    # Append to existing credentials
    existing = json_module.loads(user.webauthn_credentials or "[]")
    existing.append(verified)
    user.webauthn_credentials = json_module.dumps(existing)
    db.commit()

    return {"registered": True}
```

- [ ] **Step 4: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest tests/backend/test_device_webauthn.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/schemas/device.py server/apps/backend/app/routers/device.py server/tests/backend/test_device_webauthn.py
git commit -m "$(cat <<'EOF'
feat(device): add WebAuthn registration during device trust flow

POST /device/trust/webauthn/register-options — generate reg challenge
POST /device/trust/webauthn/register — verify and store passkey

Authenticated user can register a passkey when trusting a device.
Enables biometric login on subsequent visits.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Frontend — Device API Layer for WebAuthn

**Files:**
- Modify: `frontend/apps/main/src/api/device.ts`

- [ ] **Step 1: Add WebAuthn types and API functions**

```typescript
// Add to existing types:
export interface DeviceCheckUser {
  user_id: string
  display_name: string
  avatar_color: string
  role: string
  second_factor_type: string | null
  has_passkey: boolean  // NEW
  last_seen_at: string
}

// Add new API functions:
export interface WebAuthnAuthOptionsResponse {
  options: Record<string, unknown>
  challenge: string
}

export function getDeviceWebAuthnAuthOptions(deviceId: string, userId: string) {
  return http.post<WebAuthnAuthOptionsResponse>('/auth/device/webauthn/auth-options', {
    device_id: deviceId,
    user_id: userId,
  })
}

export function verifyDeviceWebAuthn(
  deviceId: string,
  userId: string,
  credential: Record<string, unknown>,
  challenge: string,
) {
  return http.post<DeviceSelectResponse>('/auth/device/webauthn/verify', {
    device_id: deviceId,
    user_id: userId,
    credential,
    challenge,
  })
}

export interface WebAuthnRegisterOptionsResponse {
  options: Record<string, unknown>
  challenge: string
}

export function getDeviceTrustWebAuthnOptions() {
  return http.post<WebAuthnRegisterOptionsResponse>('/auth/device/trust/webauthn/register-options')
}

export function registerDeviceTrustWebAuthn(
  credential: Record<string, unknown>,
  challenge: string,
) {
  return http.post<{ registered: boolean }>('/auth/device/trust/webauthn/register', {
    credential,
    challenge,
  })
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend && pnpm -r typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/api/device.ts
git commit -m "$(cat <<'EOF'
feat(api): add WebAuthn device auth and registration API functions

- getDeviceWebAuthnAuthOptions: request challenge for biometric login
- verifyDeviceWebAuthn: submit signed assertion
- getDeviceTrustWebAuthnOptions: request registration challenge
- registerDeviceTrustWebAuthn: submit new passkey credential
- Add has_passkey field to DeviceCheckUser type

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — LoginPage WebAuthn Integration

**Files:**
- Modify: `frontend/apps/main/src/pages/LoginPage.vue`

This is the core UX change. The flow becomes:

1. Page loads → read `device_id` cookie → call `/device/check`
2. If trusted: show carousel. ALTCHA starts auto-solving in background.
3. User taps account card:
   - If `has_passkey` + WebAuthn supported → call `/device/webauthn/auth-options` → trigger biometric → call `/device/webauthn/verify`
   - If no passkey → wait for ALTCHA to finish → call `/device/select` (existing flow)

- [ ] **Step 1: Add WebAuthn imports and support detection**

In `<script setup>` section of `LoginPage.vue`, add:

```typescript
import { checkWebAuthnSupport, authenticatePasskey } from '@/utils/webauthn'
import { getDeviceWebAuthnAuthOptions, verifyDeviceWebAuthn } from '@/api/device'

const webauthnSupported = ref(false)

onMounted(async () => {
  const { supported } = checkWebAuthnSupport()
  webauthnSupported.value = supported
  // ... existing device check logic
})
```

- [ ] **Step 2: Modify `onSelectUser` to branch on WebAuthn**

Replace the current `onSelectUser` + ALTCHA watch flow with a branching function:

```typescript
async function onSelectUser(user: BoundUser) {
  selectedUser.value = user

  if (user.hasPasskey && webauthnSupported.value) {
    // WebAuthn path — trigger biometric immediately
    await authenticateWithWebAuthn(user)
  }
  // Non-WebAuthn path: ALTCHA widget is shown, auto-solves,
  // triggers onSelectAltchaComplete when done
}

async function authenticateWithWebAuthn(user: BoundUser) {
  if (!deviceIdRef.value) return
  loading.value = true
  try {
    // 1. Get challenge from server
    const { data: authOptions } = await getDeviceWebAuthnAuthOptions(
      deviceIdRef.value,
      user.userId,
    )

    // 2. Trigger biometric prompt
    const credential = await authenticatePasskey(authOptions.options)

    // 3. Verify on server
    const { data } = await verifyDeviceWebAuthn(
      deviceIdRef.value,
      user.userId,
      credential,
      authOptions.challenge,
    )

    // 4. Handle response (same as onSelectAltchaComplete)
    if (data.second_factor_required && data.temp_token) {
      tempToken.value = data.temp_token
      secondFactorType.value = data.second_factor_type ?? 'numeric_pin'
      trustedUser.value = {
        displayName: data.display_name ?? user.displayName,
        avatarColor: data.avatar_color ?? user.avatarColor,
      }
      stepLoading.value = true
      setTimeout(() => {
        step.value = 2
        stepLoading.value = false
      }, 700)
    } else {
      await authStore.fetchMe()
      showToast(t('toast.loginSuccess'))
      authStore.showTrustPrompt = true
      const authUser = authStore.user
      if (authUser?.role === 'child') {
        const baseUrl = import.meta.env.VITE_MAIN_APP_URL || ''
        window.location.href = `${baseUrl}/child/`
        return
      }
      router.push('/')
    }
  } catch {
    // WebAuthn failed (user cancelled, hardware error) — fall back to ALTCHA
    showToast(t('toast.webauthnFailed'))
    // Let ALTCHA widget appear for this user
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 3: Update BoundUser interface to include hasPasskey**

```typescript
interface BoundUser {
  userId: string
  displayName: string
  avatarColor: string
  role: string
  secondFactorType: string | null
  hasPasskey: boolean  // NEW
}

// In onMounted, update the mapping:
boundUsers.value = data.users.map((u: DeviceCheckUser) => ({
  userId: String(u.user_id),
  displayName: u.display_name,
  avatarColor: u.avatar_color,
  role: u.role,
  secondFactorType: u.second_factor_type,
  hasPasskey: u.has_passkey,  // NEW
}))
```

- [ ] **Step 4: Modify Step 0 template for conditional ALTCHA**

Replace the `select-captcha-area` section:

```html
<Transition name="step-fade">
  <div v-if="selectedUser && !(selectedUser.hasPasskey && webauthnSupported)" class="select-captcha-area">
    <p class="captcha-hint">{{ t('login.verifyToContinue') }}</p>
    <AltchaWidget
      ref="selectAltchaRef"
      v-model="selectAltcha"
      endpoint="login"
    />
  </div>
</Transition>
```

When `hasPasskey && webauthnSupported`, the ALTCHA widget is hidden — the WebAuthn biometric prompt is triggered directly by `onSelectUser`.

- [ ] **Step 5: Update `readDeviceId` import**

Change from:
```typescript
import { readDeviceId, recoverFromEtag } from '@numina/auth'
```
To:
```typescript
import { readDeviceId } from '@numina/auth'
```

And update the `onMounted` logic to remove the `recoverFromEtag` fallback:

```typescript
onMounted(async () => {
  const { supported } = checkWebAuthnSupport()
  webauthnSupported.value = supported

  try {
    const deviceId = readDeviceId()
    if (!deviceId) return

    deviceIdRef.value = deviceId
    const { data } = await checkDevice(deviceId)
    // ... rest unchanged
  } catch {
    // Non-fatal
  }
})
```

- [ ] **Step 6: Add i18n key for WebAuthn failure toast**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`:
```typescript
toast: {
  // ... existing
  webauthnFailed: '⚠️ 生物识别验证失败，请使用验证码登录',
}
```

In `frontend/apps/main/src/i18n/locales/en-US.ts`:
```typescript
toast: {
  // ... existing
  webauthnFailed: '⚠️ Biometric verification failed, please use captcha',
}
```

- [ ] **Step 7: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend && pnpm -r typecheck`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/apps/main/src/pages/LoginPage.vue frontend/apps/main/src/i18n/
git commit -m "$(cat <<'EOF'
feat(login): integrate WebAuthn biometric in Step 0 account selection

- If user has passkey + device supports WebAuthn: trigger biometric on tap
- If biometric succeeds: proceed to Step 2 (PIN) or login complete
- If biometric fails/cancelled: fall back to ALTCHA verification
- ALTCHA widget only shown for users without passkey
- Remove recoverFromEtag dependency (no longer needed)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Frontend — WebAuthn Registration in Trust Flow

**Files:**
- Modify: The component that handles "Trust this device" prompt (likely in `@numina/auth` package or a page component)

After login, when user confirms "Trust this device", optionally register a WebAuthn credential.

- [ ] **Step 1: Find the trust device UI component**

Search for where `authStore.showTrustPrompt` is consumed and the trust API is called. This is where we add the WebAuthn registration step.

- [ ] **Step 2: Add WebAuthn registration after trust**

After the existing `/device/trust` call succeeds:

```typescript
import { checkWebAuthnSupport, registerPasskey } from '@/utils/webauthn'
import { getDeviceTrustWebAuthnOptions, registerDeviceTrustWebAuthn } from '@/api/device'

async function onTrustDevice() {
  // ... existing trust logic (POST /device/trust)
  await trustDevice()

  // Attempt WebAuthn registration
  const { supported } = checkWebAuthnSupport()
  if (supported) {
    try {
      const { data: regOptions } = await getDeviceTrustWebAuthnOptions()
      const credential = await registerPasskey(regOptions.options)
      await registerDeviceTrustWebAuthn(credential, regOptions.challenge)
    } catch {
      // User declined biometric or hardware unavailable — non-fatal.
      // Device is still trusted via cookie, just without passkey.
    }
  }
}
```

- [ ] **Step 3: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend && pnpm -r typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "$(cat <<'EOF'
feat(trust): register WebAuthn passkey during device trust flow

After confirming trust, attempts to register a platform authenticator.
If user declines or device lacks support, trust still works via cookie.
Passkey enables biometric login on subsequent visits.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Cleanup — Remove FingerprintJS References

**Files:**
- Search entire frontend for `fingerprint`, `getDeviceFingerprint`, `@fingerprintjs`
- Modify: any files that import or reference these

- [ ] **Step 1: Search for all references**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend
grep -r "fingerprint\|fingerprintjs\|getDeviceFingerprint" --include="*.ts" --include="*.vue" -l
```

- [ ] **Step 2: Remove all references**

Delete imports, function calls, and any dependency declarations. The `browser_fingerprint` column on `DeviceSession` can remain (nullable, will be `None` going forward) — no migration needed.

- [ ] **Step 3: Remove from package.json if present**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/packages/auth
# Check if @fingerprintjs/fingerprintjs is in dependencies
cat package.json | grep fingerprint
# If found: pnpm remove @fingerprintjs/fingerprintjs
```

- [ ] **Step 4: Run typecheck and tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend && pnpm -r typecheck && pnpm -r test:run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "$(cat <<'EOF'
refactor(auth): remove FingerprintJS dependency entirely

WebAuthn hardware binding replaces browser fingerprinting.
No longer used as any signal in device identification.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Full Integration Test Pass

- [ ] **Step 1: Run all backend tests**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server
uv run pytest tests/backend/ -v 2>&1 | tail -40
```
Expected: ALL PASS

- [ ] **Step 2: Run frontend typecheck**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend
pnpm -r typecheck
```
Expected: PASS

- [ ] **Step 3: Run frontend tests**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend
pnpm -r test:run
```
Expected: PASS

- [ ] **Step 4: Run backend lint**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server
uv run ruff check apps/backend/ 2>&1 | tail -20
```
Expected: No errors

---

## Summary of Changes

| Before | After |
|--------|-------|
| 4-layer device_id persistence (cookie + LS + IDB + ETag) | Single cookie for discovery |
| ALTCHA required for every Step 0 account selection | WebAuthn biometric replaces ALTCHA for passkey users |
| FingerprintJS as signal layer | Removed entirely |
| No passkey for adults | Adults register passkey during "Trust this device" |
| Child-only WebAuthn endpoints | Shared WebAuthn helpers; device-auth endpoints for all roles |
| `/device-ping` ETag endpoint | Removed |

## Security Model

```
┌─────────────────────────────────────────────────────────┐
│ Device has WebAuthn passkey                              │
│                                                         │
│  cookie (device_id) → find accounts                     │
│  WebAuthn assertion → prove identity (hardware-bound)   │
│  PIN (if 2FA) → knowledge factor                        │
│                                                         │
│  Threat: stolen cookie → attacker sees usernames        │
│  but CANNOT authenticate (no biometric/hardware key)    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Device without WebAuthn (fallback)                       │
│                                                         │
│  cookie (device_id) → find accounts                     │
│  ALTCHA → proof of work (anti-bot, not identity)        │
│  PIN (if 2FA) → knowledge factor                        │
│                                                         │
│  Threat: stolen cookie + ALTCHA solve → attacker can    │
│  reach PIN step. PIN protects final access.             │
└─────────────────────────────────────────────────────────┘
```
