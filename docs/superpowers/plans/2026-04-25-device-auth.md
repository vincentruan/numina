# Device Trust Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unified 30-day trusted device sessions for both parent and child accounts, with post-login opt-in prompt and a device management page.

**Architecture:** Extend the existing JWT refresh token system with a new `DeviceSession` DB table. On trust, a 30-day refresh token is issued and its JTI is stored in `DeviceSession`. Token rotation updates the JTI in-place. Revocation marks the record and adds the JTI to `RevokedToken`.

**Tech Stack:** Python/FastAPI backend, SQLAlchemy + Alembic, `user-agents` library, Vue 3 + TypeScript + Vant 4 frontend.

---

## File Map

**New files:**
- `backend/app/models/device_session.py` — DeviceSession ORM model
- `backend/app/schemas/device.py` — Pydantic request/response schemas
- `backend/app/services/device.py` — device trust/list/revoke business logic
- `backend/app/routers/device.py` — 4 new endpoints
- `backend/tests/test_device_auth.py` — all backend tests
- `frontend/src/api/device.ts` — API client functions
- `frontend/src/pages/DevicesPage.vue` — device management page

**Modified files:**
- `backend/app/models/__init__.py` — import DeviceSession
- `backend/pyproject.toml` — add `user-agents` dependency
- `backend/app/config.py` — change CHILD_REFRESH_TOKEN_EXPIRE_DAYS to 30
- `backend/app/auth/deps.py` — update create_child_refresh_token expiry
- `backend/app/auth/cookies.py` — update child cookie max_age
- `backend/app/routers/auth.py` — register device router
- `backend/app/scheduler.py` — add device_session_cleanup_job
- `backend/tests/conftest.py` — import DeviceSession model
- `backend/app/errors/codes.py` — add AUTH_DEVICE_NOT_FOUND error code
- `backend/app/errors/locales/zh-CN.json` — Chinese error message
- `backend/app/errors/locales/en-US.json` — English error message
- `frontend/src/api/auth.ts` — no change needed (device endpoints are separate)
- `frontend/src/stores/auth.ts` — add trustDevice() and showTrustPrompt ref
- `frontend/src/router/index.ts` — add /settings/devices route
- `frontend/src/i18n/locales/zh-CN.ts` — add device-related toast/label strings
- `frontend/src/i18n/locales/en-US.ts` — English equivalents

---

## Task 1: Add `user-agents` dependency and update child token expiry

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Modify: `backend/app/auth/deps.py`
- Modify: `backend/app/auth/cookies.py`

- [ ] **Step 1: Add `user-agents` to pyproject.toml**

In `backend/pyproject.toml`, add to the `dependencies` list:
```toml
"user-agents>=2.2.0",
```

- [ ] **Step 2: Install the dependency**

```bash
cd backend && uv sync
```
Expected: resolves and installs `user-agents` and its `ua-parser` dependency.

- [ ] **Step 3: Change CHILD_REFRESH_TOKEN_EXPIRE_DAYS in config.py**

In `backend/app/config.py`, change line:
```python
CHILD_REFRESH_TOKEN_EXPIRE_DAYS: int = 3650  # ~10 years for child sessions
```
to:
```python
CHILD_REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days, same as trusted adult sessions
```

- [ ] **Step 4: Update child cookie max_age in cookies.py**

In `backend/app/auth/cookies.py`, the child refresh cookie currently hardcodes `400 * 24 * 60 * 60`. Change it to use the setting:
```python
# Child refresh token cookie (30 days, same as trusted adult sessions)
response.set_cookie(
    key=CHILD_REFRESH_TOKEN_COOKIE,
    value=refresh_token,
    max_age=settings.CHILD_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    httponly=True,
    secure=settings.ENVIRONMENT == "production",
    samesite="strict",
    path="/",
)
```

- [ ] **Step 5: Commit**

```bash
cd backend && git add pyproject.toml app/config.py app/auth/deps.py app/auth/cookies.py && git commit -m "feat(auth): reduce child refresh token expiry to 30 days, add user-agents dep"
```

---

## Task 2: Create DeviceSession model and migration

**Files:**
- Create: `backend/app/models/device_session.py`
- Modify: `backend/app/models/__init__.py` (if it imports models)
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_device_auth.py` (new file):
```python
from app.models.device_session import DeviceSession


def test_device_session_model_exists(db):
    """DeviceSession table is created and can be queried."""
    count = db.query(DeviceSession).count()
    assert count == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_device_auth.py::test_device_session_model_exists -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.device_session'`

- [ ] **Step 3: Create `backend/app/models/device_session.py`**

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class DeviceSession(Base):
    """Trusted device session record.

    Created when a user opts in to "remember this device" after login.
    refresh_jti links this record to the live JWT refresh token.
    Revocation sets is_revoked=True and adds refresh_jti to RevokedToken.
    """

    __tablename__ = "device_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    refresh_jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_device_sessions_user_active", "user_id", "is_revoked", "expires_at"),
        Index("ix_device_sessions_family", "family_id"),
    )
```

- [ ] **Step 4: Import DeviceSession in conftest.py**

In `backend/tests/conftest.py`, add after the other model imports:
```python
from app.models.device_session import DeviceSession  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_device_auth.py::test_device_session_model_exists -v
```
Expected: PASS

- [ ] **Step 6: Create Alembic migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add device_sessions table"
```
Expected: new file in `alembic/versions/` with `op.create_table('device_sessions', ...)`.

- [ ] **Step 7: Apply migration**

```bash
cd backend && uv run alembic upgrade head
```
Expected: `Running upgrade ... -> ..., add device_sessions table`

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/models/device_session.py tests/conftest.py alembic/versions/ && git commit -m "feat(auth): add DeviceSession model and migration"
```

---

## Task 3: Add error code and schemas

**Files:**
- Modify: `backend/app/errors/codes.py`
- Modify: `backend/app/errors/locales/zh-CN.json`
- Modify: `backend/app/errors/locales/en-US.json`
- Create: `backend/app/schemas/device.py`

- [ ] **Step 1: Add AUTH_DEVICE_NOT_FOUND to ErrorCode enum**

In `backend/app/errors/codes.py`, add after `AUTH_WEBAUTHN_VERIFICATION_FAILED`:
```python
AUTH_DEVICE_NOT_FOUND = "AUTH_DEVICE_NOT_FOUND"  # Device session not found or not owned by user
```

And in the `ERROR_STATUS_MAP` dict, add:
```python
ErrorCode.AUTH_DEVICE_NOT_FOUND: 404,
```

- [ ] **Step 2: Add Chinese error message**

In `backend/app/errors/locales/zh-CN.json`, add after `AUTH_WEBAUTHN_VERIFICATION_FAILED`:
```json
"AUTH_DEVICE_NOT_FOUND": "设备不存在或无权操作",
```

- [ ] **Step 3: Add English error message**

In `backend/app/errors/locales/en-US.json`, add after `AUTH_WEBAUTHN_VERIFICATION_FAILED`:
```json
"AUTH_DEVICE_NOT_FOUND": "Device not found or access denied",
```

- [ ] **Step 4: Create `backend/app/schemas/device.py`**

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceTrustResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    device_name: str
    expires_at: datetime


class DeviceSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_name: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    is_current: bool
```

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/errors/codes.py app/errors/locales/ app/schemas/device.py && git commit -m "feat(auth): add device error code and schemas"
```

---

## Task 4: Device service — trust, list, revoke

**Files:**
- Create: `backend/app/services/device.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_device_auth.py`:
```python
from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.device_session import DeviceSession
from app.models.user import User
from app.models.family import Family
from app.services import device as device_service


def _make_user(db, family_id: int, role: str = "owner") -> User:
    from app.utils.snowflake import next_id
    import bcrypt
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


def _make_family(db) -> Family:
    from app.utils.snowflake import next_id
    family = Family(id=next_id(), name="TestFamily", invite_code="XXXXXX")
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


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
    from app.errors import AppError
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_device_auth.py -v -k "device_session"
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.device'`

- [ ] **Step 3: Create `backend/app/services/device.py`**

```python
"""Device session service — trust, list, revoke, rotate."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.errors import AppError, ErrorCode
from app.models.device_session import DeviceSession


def create_device_session(
    db: Session,
    *,
    user_id: int,
    family_id: int,
    refresh_jti: str,
    device_name: str,
) -> DeviceSession:
    """Create a new trusted device session (30-day expiry)."""
    now = datetime.utcnow()
    session = DeviceSession(
        user_id=user_id,
        family_id=family_id,
        refresh_jti=refresh_jti,
        device_name=device_name,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=30),
        is_revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_device_sessions(db: Session, *, user_id: int) -> list[DeviceSession]:
    """Return active (non-revoked, non-expired) device sessions for a user."""
    now = datetime.utcnow()
    return (
        db.query(DeviceSession)
        .filter(
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .order_by(DeviceSession.last_seen_at.desc())
        .all()
    )


def revoke_device_session(db: Session, *, device_id: int, user_id: int) -> DeviceSession:
    """Revoke a device session. Raises AUTH_DEVICE_NOT_FOUND if not owned by user."""
    session = db.query(DeviceSession).filter(
        DeviceSession.id == device_id,
        DeviceSession.user_id == user_id,
        DeviceSession.is_revoked.is_(False),
    ).first()
    if session is None:
        raise AppError(ErrorCode.AUTH_DEVICE_NOT_FOUND)
    session.is_revoked = True
    db.commit()
    db.refresh(session)
    return session


def revoke_all_device_sessions(db: Session, *, user_id: int) -> list[str]:
    """Revoke all active device sessions for a user. Returns list of revoked JTIs."""
    now = datetime.utcnow()
    sessions = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.user_id == user_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .all()
    )
    jtis = []
    for s in sessions:
        s.is_revoked = True
        jtis.append(s.refresh_jti)
    db.commit()
    return jtis


def rotate_device_session_jti(db: Session, *, old_jti: str, new_jti: str) -> DeviceSession | None:
    """Update refresh_jti after token rotation. Returns None if no matching session."""
    session = db.query(DeviceSession).filter(
        DeviceSession.refresh_jti == old_jti,
        DeviceSession.is_revoked.is_(False),
    ).first()
    if session is None:
        return None
    session.refresh_jti = new_jti
    session.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def get_device_session_by_jti(db: Session, *, jti: str) -> DeviceSession | None:
    """Look up an active device session by its current refresh JTI."""
    now = datetime.utcnow()
    return db.query(DeviceSession).filter(
        DeviceSession.refresh_jti == jti,
        DeviceSession.is_revoked.is_(False),
        DeviceSession.expires_at > now,
    ).first()


def cleanup_expired_device_sessions(db: Session) -> int:
    """Mark expired sessions as revoked. Called by scheduler."""
    now = datetime.utcnow()
    updated = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.expires_at < now,
            DeviceSession.is_revoked.is_(False),
        )
        .update({"is_revoked": True})
    )
    db.commit()
    return updated


def delete_old_revoked_sessions(db: Session) -> int:
    """Hard-delete revoked sessions older than 7 days. Called by scheduler."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    deleted = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.is_revoked.is_(True),
            DeviceSession.last_seen_at < cutoff,
        )
        .delete()
    )
    db.commit()
    return deleted
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_device_auth.py -v -k "device_session"
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/device.py tests/test_device_auth.py && git commit -m "feat(auth): add device session service with trust/list/revoke/rotate"
```

---

## Task 5: Device router — 4 endpoints

**Files:**
- Create: `backend/app/routers/device.py`
- Modify: `backend/app/routers/auth.py` (register router)

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_device_auth.py`:
```python
import pytest


def test_trust_device_endpoint(client, auth_headers):
    """POST /auth/device/trust creates a DeviceSession and returns device info."""
    response = client.post(
        "/api/v1/auth/device/trust",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "device_id" in data
    assert "device_name" in data
    assert "expires_at" in data


def test_list_devices_endpoint(client, auth_headers):
    """GET /auth/devices returns list of trusted devices."""
    # Trust a device first
    client.post("/api/v1/auth/device/trust", headers=auth_headers)
    response = client.get("/api/v1/auth/devices", headers=auth_headers)
    assert response.status_code == 200
    devices = response.json()["data"]
    assert isinstance(devices, list)
    assert len(devices) >= 1
    assert "device_name" in devices[0]
    assert "is_current" in devices[0]


def test_revoke_device_endpoint(client, auth_headers):
    """DELETE /auth/devices/{id} revokes a device session."""
    trust_resp = client.post("/api/v1/auth/device/trust", headers=auth_headers)
    device_id = trust_resp.json()["data"]["device_id"]

    response = client.delete(
        f"/api/v1/auth/devices/{device_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200

    # Device should no longer appear in list
    list_resp = client.get("/api/v1/auth/devices", headers=auth_headers)
    ids = [d["id"] for d in list_resp.json()["data"]]
    assert device_id not in ids


def test_revoke_all_devices_endpoint(client, auth_headers):
    """DELETE /auth/devices revokes all device sessions."""
    client.post("/api/v1/auth/device/trust", headers=auth_headers)
    client.post("/api/v1/auth/device/trust", headers=auth_headers)

    response = client.delete("/api/v1/auth/devices", headers=auth_headers)
    assert response.status_code == 200

    list_resp = client.get("/api/v1/auth/devices", headers=auth_headers)
    assert list_resp.json()["data"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_device_auth.py -v -k "endpoint"
```
Expected: FAIL with 404 (routes not registered yet)

- [ ] **Step 3: Create `backend/app/routers/device.py`**

```python
"""Device trust management endpoints."""

from fastapi import APIRouter, Cookie, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.cookies import clear_auth_cookies, clear_child_auth_cookies
from app.auth.deps import (
    ACCESS_TOKEN_COOKIE,
    CHILD_ACCESS_TOKEN_COOKIE,
    CHILD_REFRESH_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    _verify_token,
    create_refresh_token,
    create_child_refresh_token,
)
from app.auth.revoke_jti import revoke_jti
from app.config import settings
from app.database import get_db
from app.schemas.device import DeviceTrustResponse, DeviceSessionResponse
from app.services import device as device_service

router = APIRouter(prefix="/auth", tags=["device"])


def _parse_device_name(request: Request) -> str:
    """Parse User-Agent header into a human-readable device name."""
    from user_agents import parse
    ua_string = request.headers.get("user-agent", "")
    ua = parse(ua_string)
    device = ua.device.family
    browser = ua.browser.family
    os = ua.os.family
    if device and device != "Other":
        name = f"{device} · {browser}"
    else:
        name = f"{os} · {browser}"
    return name or "未知设备"


def _get_refresh_jti_from_cookie(
    refresh_token_cookie: str | None,
    child_refresh_token_cookie: str | None,
) -> tuple[str, str]:
    """Extract JTI and token type from whichever refresh cookie is present.

    Returns (jti, token_type) where token_type is 'adult' or 'child'.
    Raises ValueError if no valid refresh token found.
    """
    for cookie, token_type in [
        (refresh_token_cookie, "adult"),
        (child_refresh_token_cookie, "child"),
    ]:
        if cookie:
            payload = _verify_token(cookie, "refresh")
            if payload and payload.get("jti"):
                return payload["jti"], token_type
    raise ValueError("no valid refresh token")


def _get_user_payload(
    access_token_cookie: str | None,
    child_access_token_cookie: str | None,
) -> dict:
    """Verify whichever access cookie is present and return its payload."""
    payload = None
    if access_token_cookie:
        payload = _verify_token(access_token_cookie, "access")
    if payload is None and child_access_token_cookie:
        payload = _verify_token(child_access_token_cookie, "access")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法验证凭据")
    return payload


@router.post("/device/trust")
def trust_device(
    request: Request,
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Trust the current device — issue 30-day refresh token and create DeviceSession."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie)
    user_id = int(payload["sub"])
    family_id = int(payload["fid"])
    role = payload["role"]

    try:
        old_jti, _ = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少刷新令牌")

    claims = {"sub": str(user_id), "fid": str(family_id), "role": role}
    if role == "child":
        new_refresh = create_child_refresh_token(claims)
    else:
        new_refresh = create_refresh_token(claims)

    new_payload = _verify_token(new_refresh, "refresh")
    new_jti = new_payload["jti"]

    revoke_jti(old_jti, ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

    device_name = _parse_device_name(request)
    session = device_service.create_device_session(
        db, user_id=user_id, family_id=family_id,
        refresh_jti=new_jti, device_name=device_name,
    )

    cookie_name = CHILD_REFRESH_TOKEN_COOKIE if role == "child" else REFRESH_TOKEN_COOKIE
    response.set_cookie(
        key=cookie_name,
        value=new_refresh,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        path="/",
    )

    return {
        "code": "OK", "message": "success",
        "data": DeviceTrustResponse(
            device_id=str(session.id),
            device_name=session.device_name,
            expires_at=session.expires_at,
        ),
    }


@router.get("/devices")
def list_devices(
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """List trusted devices for the current user."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie)
    user_id = int(payload["sub"])

    current_jti = None
    try:
        current_jti, _ = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)
    except ValueError:
        pass

    sessions = device_service.list_device_sessions(db, user_id=user_id)
    return {
        "code": "OK",
        "message": "success",
        "data": [
            DeviceSessionResponse(
                id=str(s.id),
                device_name=s.device_name,
                created_at=s.created_at,
                last_seen_at=s.last_seen_at,
                expires_at=s.expires_at,
                is_current=(s.refresh_jti == current_jti),
            )
            for s in sessions
        ],
    }


@router.delete("/devices/{device_id}")
def revoke_device(
    device_id: str,
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    refresh_token_cookie: str | None = Cookie(None, alias=REFRESH_TOKEN_COOKIE),
    child_refresh_token_cookie: str | None = Cookie(None, alias=CHILD_REFRESH_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Revoke a specific trusted device session."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie)
    user_id = int(payload["sub"])
    role = payload["role"]

    session = device_service.revoke_device_session(db, device_id=int(device_id), user_id=user_id)
    revoke_jti(session.refresh_jti, ttl_seconds=30 * 24 * 3600)

    current_jti = None
    try:
        current_jti, _ = _get_refresh_jti_from_cookie(refresh_token_cookie, child_refresh_token_cookie)
    except ValueError:
        pass

    if current_jti == session.refresh_jti:
        if role == "child":
            clear_child_auth_cookies(response)
        else:
            clear_auth_cookies(response)

    return {"code": "OK", "message": "success", "data": None}


@router.delete("/devices")
def revoke_all_devices(
    response: Response,
    access_token_cookie: str | None = Cookie(None, alias=ACCESS_TOKEN_COOKIE),
    child_access_token_cookie: str | None = Cookie(None, alias=CHILD_ACCESS_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    """Revoke all trusted device sessions for the current user."""
    payload = _get_user_payload(access_token_cookie, child_access_token_cookie)
    user_id = int(payload["sub"])
    role = payload["role"]

    jtis = device_service.revoke_all_device_sessions(db, user_id=user_id)
    for jti in jtis:
        revoke_jti(jti, ttl_seconds=30 * 24 * 3600)

    if role == "child":
        clear_child_auth_cookies(response)
    else:
        clear_auth_cookies(response)

    return {"code": "OK", "message": "success", "data": None}
```

- [ ] **Step 4: Register device router in `backend/app/main.py`**

Find where `auth.router` is included (search for `include_router`) and add the device router alongside it:
```python
from app.routers.device import router as device_router
app.include_router(device_router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_device_auth.py -v -k "endpoint"
```
Expected: all 4 endpoint tests PASS

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/routers/device.py app/main.py tests/test_device_auth.py && git commit -m "feat(auth): add device trust/list/revoke endpoints"
```

---

## Task 6: Token refresh — DeviceSession JTI rotation

**Files:**
- Modify: `backend/app/services/auth.py` (refresh logic)
- Modify: `backend/app/routers/auth.py` (refresh endpoint)

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_device_auth.py`:
```python
def test_refresh_rotates_device_session_jti(client, auth_headers, db):
    """Token refresh updates DeviceSession.refresh_jti in-place."""
    # Trust device
    trust_resp = client.post("/api/v1/auth/device/trust", headers=auth_headers)
    assert trust_resp.status_code == 200

    # Refresh token (cookie sent automatically by TestClient)
    refresh_resp = client.post("/api/v1/auth/refresh", data=None)
    assert refresh_resp.status_code == 200

    # Device session should still exist (not revoked)
    list_resp = client.get("/api/v1/auth/devices", headers=auth_headers)
    assert len(list_resp.json()["data"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_device_auth.py::test_refresh_rotates_device_session_jti -v
```
Expected: FAIL (refresh doesn't update DeviceSession yet)

- [ ] **Step 3: Update refresh logic in `backend/app/services/auth.py`**

Find the `refresh_token` function (search for `def refresh_token`). After the existing JTI revocation call (`revoke_jti(old_jti, ...)`), add a call to rotate the DeviceSession JTI:

```python
# After: revoke_jti(old_jti, ttl_seconds=...)
# Add:
from app.services.device import rotate_device_session_jti
new_jti = new_payload.get("jti")
if new_jti:
    rotate_device_session_jti(db, old_jti=old_jti, new_jti=new_jti)
```

The `db` session must be available in the refresh function. If it isn't already a parameter, add `db: Session` to the function signature and pass it from the router.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_device_auth.py::test_refresh_rotates_device_session_jti -v
```
Expected: PASS

- [ ] **Step 5: Run full auth test suite to check for regressions**

```bash
cd backend && uv run pytest tests/test_auth.py tests/test_auth_security.py tests/test_device_auth.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/services/auth.py app/routers/auth.py tests/test_device_auth.py && git commit -m "feat(auth): rotate DeviceSession JTI on token refresh"
```

---

## Task 7: Scheduler — device session cleanup

**Files:**
- Modify: `backend/app/scheduler.py`

- [ ] **Step 1: Add cleanup job to `backend/app/scheduler.py`**

After the `revoked_token_cleanup_job` function, add:

```python
def device_session_cleanup_job() -> None:
    """APScheduler job: expire stale DeviceSessions and purge old revoked ones."""
    from app.services.device import cleanup_expired_device_sessions, delete_old_revoked_sessions

    db = SessionLocal()
    try:
        expired = cleanup_expired_device_sessions(db)
        purged = delete_old_revoked_sessions(db)
        if expired > 0 or purged > 0:
            logger.info(f"设备会话清理: 过期 {expired} 条，删除 {purged} 条")
    except Exception as e:
        logger.exception(f"设备会话清理失败: {e}")
    finally:
        db.close()
```

- [ ] **Step 2: Register the job in `setup_revoked_token_cleanup_schedule`**

In `backend/app/scheduler.py`, update `setup_revoked_token_cleanup_schedule` to also schedule the device cleanup (reuse the same hourly slot):

```python
def setup_device_session_cleanup_schedule() -> None:
    """Schedule hourly cleanup of expired device sessions."""
    scheduler.add_job(
        device_session_cleanup_job,
        trigger="cron",
        minute=15,  # offset from revoked_token_cleanup at :00
        id="device_session_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("设备会话清理任务已配置（每小时 :15）")
```

- [ ] **Step 3: Call setup in `backend/app/main.py`**

Find where `setup_revoked_token_cleanup_schedule()` is called and add below it:
```python
from app.scheduler import setup_device_session_cleanup_schedule
setup_device_session_cleanup_schedule()
```

- [ ] **Step 4: Verify app starts without error**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/scheduler.py app/main.py && git commit -m "feat(auth): add hourly device session cleanup scheduler job"
```

---

## Task 8: Frontend — API client and i18n strings

**Files:**
- Create: `frontend/src/api/device.ts`
- Modify: `frontend/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Create `frontend/src/api/device.ts`**

```typescript
import http from './index'

export interface DeviceTrustResponse {
  device_id: string
  device_name: string
  expires_at: string
}

export interface DeviceSession {
  id: string
  device_name: string
  created_at: string
  last_seen_at: string
  expires_at: string
  is_current: boolean
}

export function trustDevice() {
  return http.post<DeviceTrustResponse>('/auth/device/trust')
}

export function listDevices() {
  return http.get<DeviceSession[]>('/auth/devices')
}

export function revokeDevice(deviceId: string) {
  return http.delete(`/auth/devices/${deviceId}`)
}

export function revokeAllDevices() {
  return http.delete('/auth/devices')
}
```

- [ ] **Step 2: Add i18n strings to `frontend/src/i18n/locales/zh-CN.ts`**

In the `toast` section, add:
```typescript
deviceTrustSuccess: '✅ 已记住此设备（30 天）',
deviceRevokeSuccess: '🗑️ 已退出该设备',
deviceRevokeAllSuccess: '🗑️ 已退出所有设备',
deviceTrustFailed: '❌ 记住设备失败，请重试',
```

In the `device` section (create if not exists):
```typescript
device: {
  title: '已登录设备',
  currentDevice: '当前设备',
  lastSeen: '最近活跃',
  expiresAt: '到期时间',
  revoke: '撤销',
  revokeThis: '退出此设备',
  revokeAll: '退出所有其他设备',
  trustPromptTitle: '保持登录状态？',
  trustPromptMessage: '在此设备上保持登录 30 天',
  trustConfirm: '保持登录',
  trustCancel: '暂不',
  sessionExpiredTitle: '登录已过期',
  sessionExpiredMessage: '请重新登录以继续',
  sessionExpiredConfirm: '重新登录',
},
```

- [ ] **Step 3: Add i18n strings to `frontend/src/i18n/locales/en-US.ts`**

In the `toast` section, add:
```typescript
deviceTrustSuccess: '✅ Device remembered (30 days)',
deviceRevokeSuccess: '🗑️ Device signed out',
deviceRevokeAllSuccess: '🗑️ All devices signed out',
deviceTrustFailed: '❌ Failed to remember device',
```

In the `device` section:
```typescript
device: {
  title: 'Signed-in Devices',
  currentDevice: 'This device',
  lastSeen: 'Last active',
  expiresAt: 'Expires',
  revoke: 'Revoke',
  revokeThis: 'Sign out this device',
  revokeAll: 'Sign out all other devices',
  trustPromptTitle: 'Stay signed in?',
  trustPromptMessage: 'Stay signed in on this device for 30 days',
  trustConfirm: 'Stay signed in',
  trustCancel: 'Not now',
  sessionExpiredTitle: 'Session expired',
  sessionExpiredMessage: 'Please sign in again to continue',
  sessionExpiredConfirm: 'Sign in',
},
```

- [ ] **Step 4: Run typecheck**

```bash
cd frontend && npm run typecheck
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/api/device.ts src/i18n/locales/ && git commit -m "feat(auth): add device API client and i18n strings"
```

---

## Task 9: Frontend — post-login trust prompt

**Files:**
- Modify: `frontend/src/stores/auth.ts`

- [ ] **Step 1: Add `showTrustPrompt` ref and `trustDevice` action to auth store**

In `frontend/src/stores/auth.ts`, add after the `user` ref:
```typescript
import * as deviceApi from '@/api/device'

const showTrustPrompt = ref(false)
```

Update the `login` function to set `showTrustPrompt` after success:
```typescript
async function login(data: LoginRequest) {
  await authApi.login(data)
  await fetchMe()
  showTrustPrompt.value = true  // trigger post-login prompt
}
```

Do the same for child login (if there's a `childLogin` action — add `showTrustPrompt.value = true` after `fetchMe()`).

Add a `trustDevice` action:
```typescript
async function trustDevice() {
  try {
    await deviceApi.trustDevice()
    showToast(t('toast.deviceTrustSuccess'))
  } catch {
    showToast(t('toast.deviceTrustFailed'))
  } finally {
    showTrustPrompt.value = false
  }
}

function dismissTrustPrompt() {
  showTrustPrompt.value = false
}
```

Return `showTrustPrompt`, `trustDevice`, and `dismissTrustPrompt` from the store.

- [ ] **Step 2: Add trust prompt dialog to `frontend/src/App.vue` or the main layout**

Find the root component that wraps all pages (likely `App.vue` or a layout component). Add a Vant `Dialog` that reacts to `showTrustPrompt`:

```vue
<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useI18n } from 'vue-i18n'

const authStore = useAuthStore()
const { t } = useI18n()
</script>

<template>
  <!-- existing content -->

  <van-dialog
    v-model:show="authStore.showTrustPrompt"
    :title="t('device.trustPromptTitle')"
    :message="t('device.trustPromptMessage')"
    :confirm-button-text="t('device.trustConfirm')"
    :cancel-button-text="t('device.trustCancel')"
    show-cancel-button
    @confirm="authStore.trustDevice()"
    @cancel="authStore.dismissTrustPrompt()"
  />
</template>
```

- [ ] **Step 3: Run typecheck**

```bash
cd frontend && npm run typecheck
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/stores/auth.ts src/App.vue && git commit -m "feat(auth): add post-login device trust prompt"
```

---

## Task 10: Frontend — device management page

**Files:**
- Create: `frontend/src/pages/DevicesPage.vue`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Create `frontend/src/pages/DevicesPage.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog } from 'vant'
import { listDevices, revokeDevice, revokeAllDevices, type DeviceSession } from '@/api/device'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const authStore = useAuthStore()
const router = useRouter()

const devices = ref<DeviceSession[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await listDevices()
    devices.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleRevoke(device: DeviceSession) {
  const confirmMsg = device.is_current
    ? t('device.revokeThis')
    : `${t('device.revoke')} ${device.device_name}？`
  await showConfirmDialog({ message: `⚠️ ${confirmMsg}` })
  await revokeDevice(device.id)
  showToast(t('toast.deviceRevokeSuccess'))
  if (device.is_current) {
    authStore.logout()
  } else {
    await load()
  }
}

async function handleRevokeAll() {
  await showConfirmDialog({ message: `⚠️ ${t('device.revokeAll')}？` })
  await revokeAllDevices()
  showToast(t('toast.deviceRevokeAllSuccess'))
  authStore.logout()
}

function formatRelativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

onMounted(load)
</script>

<template>
  <van-nav-bar :title="t('device.title')" left-arrow @click-left="router.back()" />

  <van-pull-refresh v-model="loading" @refresh="load">
    <van-list>
      <van-cell
        v-for="device in devices"
        :key="device.id"
        :title="device.device_name"
        :label="`${t('device.lastSeen')}: ${formatRelativeTime(device.last_seen_at)}`"
      >
        <template #right-icon>
          <van-tag v-if="device.is_current" type="primary" style="margin-right: 8px">
            {{ t('device.currentDevice') }}
          </van-tag>
          <van-button
            size="small"
            type="danger"
            plain
            @click="handleRevoke(device)"
          >
            {{ device.is_current ? t('device.revokeThis') : t('device.revoke') }}
          </van-button>
        </template>
      </van-cell>
    </van-list>
  </van-pull-refresh>

  <div style="padding: 16px" v-if="devices.length > 1">
    <van-button block type="warning" plain @click="handleRevokeAll">
      {{ t('device.revokeAll') }}
    </van-button>
  </div>
</template>
```

- [ ] **Step 2: Add route to `frontend/src/router/index.ts`**

Find the settings-related routes and add:
```typescript
{
  path: '/settings/devices',
  name: 'Devices',
  component: () => import('@/pages/DevicesPage.vue'),
},
```

- [ ] **Step 3: Add entry point in settings page**

Find the settings page (likely `SettingsPage.vue` or similar). Add a `van-cell` entry:
```vue
<van-cell
  :title="t('device.title')"
  is-link
  @click="router.push('/settings/devices')"
/>
```

- [ ] **Step 4: Run typecheck**

```bash
cd frontend && npm run typecheck
```
Expected: no errors

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/pages/DevicesPage.vue src/router/index.ts && git commit -m "feat(auth): add device management page"
```

---

## Task 11: Frontend — update 401 interceptor for session-expired dialog

**Files:**
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: Update the refresh failure handler in `frontend/src/api/index.ts`**

Find the block starting with:
```typescript
// Refresh endpoint failure = session expired
if (originalRequest.url?.includes('/auth/refresh')) {
  clearAuth()
  router.push('/login')
  showToast(...)
  return Promise.reject(error)
}
```

Replace with a dialog instead of a silent redirect:
```typescript
// Refresh endpoint failure = session expired
if (originalRequest.url?.includes('/auth/refresh')) {
  clearAuth()
  showDialog({
    title: t('device.sessionExpiredTitle'),
    message: t('device.sessionExpiredMessage'),
    confirmButtonText: t('device.sessionExpiredConfirm'),
  }).then(() => {
    router.push('/login')
  })
  return Promise.reject(error)
}
```

Add the import at the top of the file if not already present:
```typescript
import { showToast, showDialog } from 'vant'
```

- [ ] **Step 2: Run typecheck**

```bash
cd frontend && npm run typecheck
```
Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/api/index.ts && git commit -m "feat(auth): show dialog on session expiry instead of silent redirect"
```

---

## Task 12: Run full test suite and verify

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && uv run pytest tests/ -v --ignore=tests/integration
```
Expected: all PASS, no regressions in `test_auth.py`, `test_auth_security.py`, `test_device_auth.py`

- [ ] **Step 2: Run frontend typecheck and lint**

```bash
cd frontend && npm run typecheck && npm run lint
```
Expected: no errors

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -p && git commit -m "fix(auth): address review feedback from device auth implementation"
```

