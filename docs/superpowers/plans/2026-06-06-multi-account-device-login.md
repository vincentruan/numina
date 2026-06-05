# Multi-Account Device Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement robust 4-layer device identification and multi-account device binding with carousel UI for the login flow.

**Architecture:** Frontend persists device_id across cookie/localStorage/IndexedDB/ETag layers. Backend `/device/check` returns all bound users (max 6), new `/device/select` validates captcha and issues temp_token. Frontend LoginPage adds Step 0 with `van-swipe` carousel for account selection.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 (frontend), Python + FastAPI + SQLAlchemy (backend), IndexedDB + ETag (device persistence)

---

## File Map

### Phase 1: Device Identification Robustness

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `frontend/packages/auth/src/utils/deviceIdentity.ts` | Add IndexedDB + async readDeviceId + recoverFromEtag |
| Create | `frontend/packages/auth/src/utils/deviceIdentity.test.ts` | Unit tests for 4-layer persistence |
| Modify | `frontend/packages/auth/src/index.ts` | Re-export new async functions |
| Modify | `server/apps/backend/app/routers/device.py` | Add GET `/auth/device-ping` ETag endpoint |
| Modify | `server/packages/core/settings.py` | Add `DEVICE_TRUST_EXPIRE_DAYS` |
| Modify | `server/apps/backend/app/services/device.py` | Replace hardcoded `timedelta(days=30)` with config |
| Create | `server/apps/backend/tests/test_device_ping.py` | Test ETag endpoint |

### Phase 2: Multi-Account Device Binding

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `server/apps/backend/app/schemas/device.py` | Add DeviceCheckUserItem, DeviceSelectRequest/Response, update DeviceCheckResponse |
| Modify | `server/apps/backend/app/routers/device.py` | Rewrite `check_device`, add `select_device` endpoint |
| Create | `server/apps/backend/tests/test_device_multi_account.py` | Backend tests for multi-account flow |
| Modify | `frontend/apps/main/src/api/device.ts` | Update types + add `selectDeviceUser` |
| Modify | `frontend/apps/main/src/pages/LoginPage.vue` | Add Step 0 carousel UI, async onMounted, ALTCHA for device-select |
| Modify | `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add login.otherAccount, role.* keys |
| Modify | `frontend/apps/main/src/i18n/locales/en-US.ts` | Mirror i18n keys |

---

## Phase 1: Device Identification Robustness

### Task 1: Add DEVICE_TRUST_EXPIRE_DAYS to settings

**Files:**
- Modify: `server/packages/core/settings.py:28` (near REFRESH_TOKEN_EXPIRE_DAYS)

- [ ] **Step 1: Add the setting**

In `server/packages/core/settings.py`, add after line 28 (`REFRESH_TOKEN_EXPIRE_DAYS: int = 7`):

```python
DEVICE_TRUST_EXPIRE_DAYS: int = 30  # Device trust expiry (days since last login)
```

- [ ] **Step 2: Verify lint passes**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run ruff check packages/core/settings.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add server/packages/core/settings.py
git commit -m "feat(settings): add DEVICE_TRUST_EXPIRE_DAYS config (default 30)"
```

---

### Task 2: Replace hardcoded timedelta(days=30) in device service

**Files:**
- Modify: `server/apps/backend/app/services/device.py:24,56`
- Modify: `server/apps/backend/app/routers/device.py:143,217`

- [ ] **Step 1: Update device service to use settings**

In `server/apps/backend/app/services/device.py`, add import at the top:

```python
from packages.core.settings import settings
```

Replace the two occurrences of `timedelta(days=30)`:
- Line 33: `expires_at=now + timedelta(days=30)` → `expires_at=now + timedelta(days=settings.DEVICE_TRUST_EXPIRE_DAYS)`
- Line 56: `expires_at = now + timedelta(days=30)` → `expires_at = now + timedelta(days=settings.DEVICE_TRUST_EXPIRE_DAYS)`

- [ ] **Step 2: Update router cookie max_age to use settings**

In `server/apps/backend/app/routers/device.py`, line 143:

```python
max_age=30 * 24 * 3600,
```

Replace with:

```python
max_age=settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600,
```

Also in `revoke_device` (line 217), replace `ttl_seconds=30 * 24 * 3600` with:

```python
ttl_seconds=settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600,
```

- [ ] **Step 3: Verify lint + type check passes**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run ruff check apps/backend/app/services/device.py apps/backend/app/routers/device.py`
Expected: no errors

- [ ] **Step 4: Run existing device tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/backend/tests/ -v -k "device" 2>&1 | tail -20`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/device.py server/apps/backend/app/routers/device.py
git commit -m "refactor(device): use DEVICE_TRUST_EXPIRE_DAYS instead of hardcoded 30"
```

---

### Task 3: Add ETag device-ping endpoint

**Files:**
- Modify: `server/apps/backend/app/routers/device.py`
- Create: `server/apps/backend/tests/test_device_ping.py`

- [ ] **Step 1: Write the failing test**

Create `server/apps/backend/tests/test_device_ping.py`:

```python
"""Tests for GET /auth/device-ping ETag persistence endpoint."""

import pytest
from fastapi.testclient import TestClient


def test_device_ping_no_etag_returns_null(client: TestClient):
    """Without If-None-Match, returns device_id: null."""
    resp = client.get("/api/v1/auth/device-ping")
    assert resp.status_code == 200
    assert resp.json() == {"device_id": None}
    assert resp.headers.get("cache-control") == "no-store"


def test_device_ping_with_etag_returns_device_id(client: TestClient):
    """With If-None-Match containing a device_id, returns it back for recovery."""
    device_id = "abc123-def456"
    resp = client.get(
        "/api/v1/auth/device-ping",
        headers={"If-None-Match": f'"{device_id}"'},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == device_id
    assert resp.headers.get("etag") == f'"{device_id}"'
    assert "max-age=2592000" in resp.headers.get("cache-control", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/backend/tests/test_device_ping.py -v 2>&1 | tail -15`
Expected: FAIL (endpoint doesn't exist yet)

- [ ] **Step 3: Implement the endpoint**

Add to `server/apps/backend/app/routers/device.py`, before the `check_device` function:

```python
@router.get("/device-ping", include_in_schema=False)
def device_ping(request: Request, response: Response):
    """ETag-based device identity persistence.

    Browser sends If-None-Match with stored device_id.
    Returns the device_id for JS-layer recovery when other storage is cleared.
    """
    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        device_id = if_none_match.strip('"')
        response.headers["ETag"] = f'"{device_id}"'
        response.headers["Cache-Control"] = (
            f"private, max-age={settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600}"
        )
        return {"device_id": device_id}

    response.headers["Cache-Control"] = "no-store"
    return {"device_id": None}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/backend/tests/test_device_ping.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/device.py server/apps/backend/tests/test_device_ping.py
git commit -m "feat(device): add GET /auth/device-ping ETag persistence endpoint"
```

---

### Task 4: Rewrite deviceIdentity.ts with IndexedDB + async

**Files:**
- Modify: `frontend/packages/auth/src/utils/deviceIdentity.ts`

- [ ] **Step 1: Rewrite deviceIdentity.ts with 4-layer persistence**

Replace the full contents of `frontend/packages/auth/src/utils/deviceIdentity.ts`:

```typescript
const COOKIE_NAME = 'numina_device_id'
const LS_KEY = '_numina_device_id'
const IDB_STORE = 'numina_device_store'
const IDB_KEY = 'device_id'

export async function readDeviceId(): Promise<string | null> {
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) {
    const value = decodeURIComponent(match[1])
    localStorage.setItem(LS_KEY, value)
    writeToIdb(value)
    return value
  }

  const lsValue = localStorage.getItem(LS_KEY)
  if (lsValue) {
    writeToIdb(lsValue)
    return lsValue
  }

  const idbValue = await readFromIdb()
  if (idbValue) {
    localStorage.setItem(LS_KEY, idbValue)
    return idbValue
  }

  return null
}

export async function recoverFromEtag(): Promise<string | null> {
  try {
    const resp = await fetch('/api/v1/auth/device-ping', { credentials: 'same-origin' })
    const data = await resp.json()
    if (data.device_id) {
      await writeDeviceId(data.device_id)
      return data.device_id
    }
    return null
  } catch {
    return null
  }
}

export async function writeDeviceId(deviceId: string): Promise<void> {
  localStorage.setItem(LS_KEY, deviceId)
  await writeToIdb(deviceId)
}

export function clearDeviceId(): void {
  localStorage.removeItem(LS_KEY)
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0`
  clearIdb()
}

function openIdb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_STORE, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore('kv')
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function readFromIdb(): Promise<string | null> {
  try {
    const db = await openIdb()
    return new Promise((resolve) => {
      const tx = db.transaction('kv', 'readonly')
      const req = tx.objectStore('kv').get(IDB_KEY)
      req.onsuccess = () => resolve(req.result ?? null)
      req.onerror = () => resolve(null)
    })
  } catch {
    return null
  }
}

async function writeToIdb(value: string): Promise<void> {
  try {
    const db = await openIdb()
    const tx = db.transaction('kv', 'readwrite')
    tx.objectStore('kv').put(value, IDB_KEY)
  } catch {
    // IndexedDB unavailable — silent fallback
  }
}

async function clearIdb(): Promise<void> {
  try {
    const db = await openIdb()
    const tx = db.transaction('kv', 'readwrite')
    tx.objectStore('kv').delete(IDB_KEY)
  } catch {
    // silent
  }
}
```

- [ ] **Step 2: Update @numina/auth package exports**

In `frontend/packages/auth/src/index.ts`, update the export from `deviceIdentity` to include the new async functions. Find the existing `readDeviceId` export line and ensure both `readDeviceId`, `writeDeviceId`, `clearDeviceId`, and `recoverFromEtag` are exported.

- [ ] **Step 3: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/packages/auth && pnpm typecheck`
Expected: passes (may show errors in consuming apps — those are fixed in Task 6)

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/auth/src/utils/deviceIdentity.ts frontend/packages/auth/src/index.ts
git commit -m "feat(auth): rewrite deviceIdentity with IndexedDB + ETag recovery (async)"
```

---

### Task 5: Write deviceIdentity unit tests

**Files:**
- Create: `frontend/packages/auth/src/utils/deviceIdentity.test.ts`

- [ ] **Step 1: Create test file**

Create `frontend/packages/auth/src/utils/deviceIdentity.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock IndexedDB
const mockIdbStore = new Map<string, string>()
const mockObjectStore = {
  get: vi.fn((key: string) => {
    const result = { result: mockIdbStore.get(key) ?? null, onsuccess: null as any, onerror: null as any }
    setTimeout(() => result.onsuccess?.())
    return result
  }),
  put: vi.fn((value: string, key: string) => {
    mockIdbStore.set(key, value)
  }),
  delete: vi.fn((key: string) => {
    mockIdbStore.delete(key)
  }),
}
const mockTransaction = { objectStore: () => mockObjectStore }
const mockDb = {
  transaction: () => mockTransaction,
  createObjectStore: vi.fn(),
}

vi.stubGlobal('indexedDB', {
  open: vi.fn(() => {
    const req = { result: mockDb, onupgradeneeded: null as any, onsuccess: null as any, onerror: null as any }
    setTimeout(() => req.onsuccess?.())
    return req
  }),
})

// Mock fetch for ETag recovery
vi.stubGlobal('fetch', vi.fn())

import { readDeviceId, writeDeviceId, clearDeviceId, recoverFromEtag } from './deviceIdentity'

describe('deviceIdentity', () => {
  beforeEach(() => {
    localStorage.clear()
    document.cookie = 'numina_device_id=; Path=/; Max-Age=0'
    mockIdbStore.clear()
    vi.clearAllMocks()
  })

  it('reads from cookie first and backfills localStorage + IDB', async () => {
    document.cookie = 'numina_device_id=test-uuid-1'
    const result = await readDeviceId()
    expect(result).toBe('test-uuid-1')
    expect(localStorage.getItem('_numina_device_id')).toBe('test-uuid-1')
  })

  it('falls back to localStorage when cookie is missing', async () => {
    localStorage.setItem('_numina_device_id', 'ls-uuid')
    const result = await readDeviceId()
    expect(result).toBe('ls-uuid')
  })

  it('falls back to IndexedDB when cookie and localStorage are missing', async () => {
    mockIdbStore.set('device_id', 'idb-uuid')
    const result = await readDeviceId()
    expect(result).toBe('idb-uuid')
    expect(localStorage.getItem('_numina_device_id')).toBe('idb-uuid')
  })

  it('returns null when all layers are empty', async () => {
    const result = await readDeviceId()
    expect(result).toBeNull()
  })

  it('writeDeviceId writes to localStorage and IDB', async () => {
    await writeDeviceId('write-uuid')
    expect(localStorage.getItem('_numina_device_id')).toBe('write-uuid')
    expect(mockIdbStore.get('device_id')).toBe('write-uuid')
  })

  it('clearDeviceId clears localStorage and cookie', () => {
    localStorage.setItem('_numina_device_id', 'clear-uuid')
    clearDeviceId()
    expect(localStorage.getItem('_numina_device_id')).toBeNull()
  })

  it('recoverFromEtag fetches device-ping and writes the recovered id', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ device_id: 'etag-uuid' }),
    } as Response)

    const result = await recoverFromEtag()
    expect(result).toBe('etag-uuid')
    expect(localStorage.getItem('_numina_device_id')).toBe('etag-uuid')
  })

  it('recoverFromEtag returns null when server has no device_id', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ device_id: null }),
    } as Response)

    const result = await recoverFromEtag()
    expect(result).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/packages/auth && pnpm test:run`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/auth/src/utils/deviceIdentity.test.ts
git commit -m "test(auth): add unit tests for 4-layer deviceIdentity persistence"
```

---

### Task 6: Update LoginPage.vue onMounted to use async readDeviceId

**Files:**
- Modify: `frontend/apps/main/src/pages/LoginPage.vue:176,222-240`

- [ ] **Step 1: Update import to include recoverFromEtag**

In `LoginPage.vue`, line 176, change:

```typescript
import { TrustedDeviceCard, readDeviceId, PixelLoading } from '@numina/auth'
```

to:

```typescript
import { TrustedDeviceCard, readDeviceId, recoverFromEtag, PixelLoading } from '@numina/auth'
```

- [ ] **Step 2: Update onMounted to await readDeviceId + ETag fallback**

Replace the `onMounted` block (lines 222-240) with:

```typescript
onMounted(async () => {
  try {
    let deviceId = await readDeviceId()

    if (!deviceId) {
      deviceId = await recoverFromEtag()
    }

    if (!deviceId) return

    const { data } = await checkDevice(deviceId)
    if (data.trusted && data.temp_token && data.display_name && data.avatar_color) {
      tempToken.value = data.temp_token
      secondFactorType.value = data.second_factor_type ?? 'numeric_pin'
      trustedUser.value = { displayName: data.display_name, avatarColor: data.avatar_color }
      stepLoading.value = true
      setTimeout(() => {
        step.value = 2
        stepLoading.value = false
      }, 700)
    }
  } catch {
    // Device check failure is non-fatal — fall through to normal step 1
  }
})
```

- [ ] **Step 3: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: passes

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/LoginPage.vue
git commit -m "feat(login): use async readDeviceId + ETag recovery on mount"
```

---

### Task 7: Write ETag on device trust

**Files:**
- Modify: `frontend/packages/auth/src/stores/authStore.ts` (or wherever `trustDevice` is handled)

- [ ] **Step 1: Find trustDevice handler**

Locate where `POST /auth/device/trust` response is handled. Likely in `@numina/auth`'s auth store or in the consuming app's store. After a successful trust response that returns `device_id`:

```typescript
// After successful trust response
import { writeDeviceId } from '../utils/deviceIdentity'

// In the trust handler, after receiving data.device_id:
await writeDeviceId(data.device_id)

// Establish ETag in browser HTTP cache
fetch('/api/v1/auth/device-ping', {
  credentials: 'same-origin',
  headers: { 'If-None-Match': `"${data.device_id}"` },
})
```

- [ ] **Step 2: Verify typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/packages/auth && pnpm typecheck`
Expected: passes

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/auth/
git commit -m "feat(auth): write ETag on device trust for cache-based recovery"
```

---

## Phase 2: Multi-Account Device Binding

### Task 8: Update backend schemas for multi-user response

**Files:**
- Modify: `server/apps/backend/app/schemas/device.py`

- [ ] **Step 1: Update schemas**

Replace the content of `server/apps/backend/app/schemas/device.py`:

```python
from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class DeviceTrustResponse(SnowflakeBase):
    session_id: int
    device_id: str
    device_name: str
    expires_at: datetime


class DeviceSessionResponse(SnowflakeBase):
    session_id: int
    device_id: str | None
    device_name: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    is_current: bool


class DeviceCheckRequest(BaseModel):
    device_id: str


class DeviceCheckUserItem(BaseModel):
    user_id: int
    display_name: str
    avatar_color: str
    role: str
    second_factor_type: str | None
    last_seen_at: datetime


class DeviceCheckResponse(BaseModel):
    trusted: bool
    users: list[DeviceCheckUserItem] = []


class DeviceSelectRequest(BaseModel):
    device_id: str
    user_id: str
    altcha: str


class DeviceSelectResponse(BaseModel):
    second_factor_required: bool
    temp_token: str | None = None
    second_factor_type: str | None = None
    display_name: str | None = None
    avatar_color: str | None = None


class DeviceTrustRequest(BaseModel):
    device_id: str | None = None


class FamilyDeviceResponse(SnowflakeBase):
    session_id: int
    device_id: str | None
    user_id: int
    display_name: str
    avatar_color: str
    device_name: str
    last_seen_at: datetime
    created_at: datetime
    is_current: bool
```

- [ ] **Step 2: Verify lint**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run ruff check apps/backend/app/schemas/device.py`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/schemas/device.py
git commit -m "feat(schemas): add DeviceCheckUserItem, DeviceSelectRequest/Response for multi-account"
```

---

### Task 9: Rewrite check_device to return multi-user list

**Files:**
- Modify: `server/apps/backend/app/routers/device.py:276-334`

- [ ] **Step 1: Update imports in device router**

Add `DeviceCheckUserItem` and `DeviceSelectRequest`, `DeviceSelectResponse` to the import from schemas:

```python
from apps.backend.app.schemas.device import (
    DeviceCheckRequest,
    DeviceCheckResponse,
    DeviceCheckUserItem,
    DeviceSelectRequest,
    DeviceSelectResponse,
    DeviceSessionResponse,
    DeviceTrustRequest,
    DeviceTrustResponse,
    FamilyDeviceResponse,
)
```

- [ ] **Step 2: Rewrite check_device endpoint**

Replace the `check_device` function (lines 276-334) with:

```python
@router.post("/device/check", response_model=DeviceCheckResponse)
def check_device(
    req: DeviceCheckRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Check if a device_id is trusted. Returns all bound users (max 6).

    No auth required — used before login. Rate-limited by IP (20/min).
    """
    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    from datetime import datetime

    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    now = datetime.utcnow()
    sessions = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.device_id == req.device_id,
            DeviceSession.is_revoked.is_(False),
            DeviceSession.expires_at > now,
        )
        .order_by(DeviceSession.last_seen_at.desc())
        .limit(6)
        .all()
    )

    if not sessions:
        return DeviceCheckResponse(trusted=False)

    user_ids = [s.user_id for s in sessions]
    users = (
        db.query(User)
        .filter(User.id.in_(user_ids), User.is_active.is_(True))
        .all()
    )
    user_map = {u.id: u for u in users}

    items: list[DeviceCheckUserItem] = []
    for s in sessions:
        user = user_map.get(s.user_id)
        if not user:
            continue

        if user.role == "child" and user.pin_hash:
            second_factor_type = "emoji_pin"
        elif user.second_factor_enabled and user.second_factor_type:
            second_factor_type = user.second_factor_type
        else:
            second_factor_type = None

        items.append(
            DeviceCheckUserItem(
                user_id=user.id,
                display_name=user.display_name,
                avatar_color=user.avatar_color,
                role=user.role,
                second_factor_type=second_factor_type,
                last_seen_at=s.last_seen_at,
            )
        )

    if not items:
        return DeviceCheckResponse(trusted=False)

    return DeviceCheckResponse(trusted=True, users=items)
```

- [ ] **Step 3: Run lint**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run ruff check apps/backend/app/routers/device.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/routers/device.py
git commit -m "feat(device): rewrite /device/check to return multi-user list (max 6)"
```

---

### Task 10: Add POST /device/select endpoint

**Files:**
- Modify: `server/apps/backend/app/routers/device.py`

- [ ] **Step 1: Add select_device endpoint**

Add after the `check_device` function:

```python
@router.post("/device/select", response_model=DeviceSelectResponse)
async def select_device(
    req: DeviceSelectRequest,
    request: Request,
    response: Response,
    _: None = Depends(verify_captcha),
    db: Session = Depends(get_db),
):
    """Select a user from device-bound accounts. Requires ALTCHA captcha.

    If user has second factor: returns temp_token for PIN step.
    If no second factor: sets auth cookies and returns directly.
    """
    client_ip = _get_real_client_ip(request)
    _check_device_check_rate_limit(client_ip)

    from datetime import datetime, timedelta

    from apps.backend.app.auth.deps import create_access_token, create_refresh_token, create_temp_token
    from apps.backend.app.models.device_session import DeviceSession
    from apps.backend.app.models.user import User

    now = datetime.utcnow()
    user_id = int(req.user_id)

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

    # Refresh session last_seen_at + expires_at (rolling window)
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
        return DeviceSelectResponse(
            second_factor_required=True,
            temp_token=temp_token,
            second_factor_type=second_factor_type,
            display_name=user.display_name,
            avatar_color=user.avatar_color,
        )

    # No second factor — issue tokens directly
    claims = {"sub": str(user.id), "fid": str(user.family_id), "role": user.role}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)

    from apps.backend.app.auth.cookies import set_auth_cookies

    set_auth_cookies(response, access_token, refresh_token)

    return DeviceSelectResponse(second_factor_required=False)
```

- [ ] **Step 2: Add the verify_captcha import**

At the top of `device.py`, add:

```python
from apps.backend.app.auth.captcha import verify_captcha
```

- [ ] **Step 3: Verify lint**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run ruff check apps/backend/app/routers/device.py`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/routers/device.py
git commit -m "feat(device): add POST /device/select with captcha + session refresh"
```

---

### Task 11: Write backend tests for multi-account flow

**Files:**
- Create: `server/apps/backend/tests/test_device_multi_account.py`

- [ ] **Step 1: Create test file**

Create `server/apps/backend/tests/test_device_multi_account.py`:

```python
"""Tests for multi-account device binding (/device/check multi-user, /device/select)."""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.backend.app.models.device_session import DeviceSession
from apps.backend.app.models.user import User


def _create_user(db: Session, *, username: str, role: str = "admin", family_id: int, pin_hash: str | None = None) -> User:
    """Helper: create a user for testing."""
    from packages.core.snowflake import generate_id

    user = User(
        id=generate_id(),
        username=username,
        password_hash="$2b$12$fake",
        display_name=username.capitalize(),
        avatar_color="#4ecdc4",
        role=role,
        family_id=family_id,
        is_active=True,
        pin_hash=pin_hash,
        second_factor_enabled=pin_hash is not None,
        second_factor_type="numeric_pin" if pin_hash and role != "child" else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_device_session(db: Session, *, user_id: int, family_id: int, device_id: str) -> DeviceSession:
    """Helper: create a device session for testing."""
    now = datetime.utcnow()
    session = DeviceSession(
        user_id=user_id,
        family_id=family_id,
        device_id=device_id,
        device_name="Test Device",
        refresh_jti=str(uuid.uuid4()),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=30),
        is_revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


class TestDeviceCheckMultiUser:
    def test_returns_multiple_users(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        u1 = _create_user(db, username="dad", role="owner", family_id=family_id)
        u2 = _create_user(db, username="mom", role="admin", family_id=family_id)
        _create_device_session(db, user_id=u1.id, family_id=family_id, device_id=device_id)
        _create_device_session(db, user_id=u2.id, family_id=family_id, device_id=device_id)

        resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["trusted"] is True
        assert len(data["users"]) == 2

    def test_returns_empty_for_unknown_device(self, client: TestClient):
        resp = client.post("/api/v1/auth/device/check", json={"device_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["trusted"] is False
        assert data["users"] == []

    def test_max_6_users(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        for i in range(8):
            u = _create_user(db, username=f"user{i}", family_id=family_id)
            _create_device_session(db, user_id=u.id, family_id=family_id, device_id=device_id)

        resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
        data = resp.json()
        assert data["trusted"] is True
        assert len(data["users"]) == 6

    def test_expired_sessions_excluded(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        u = _create_user(db, username="expired_user", family_id=family_id)
        now = datetime.utcnow()
        session = DeviceSession(
            user_id=u.id,
            family_id=family_id,
            device_id=device_id,
            device_name="Test",
            refresh_jti=str(uuid.uuid4()),
            created_at=now - timedelta(days=31),
            last_seen_at=now - timedelta(days=31),
            expires_at=now - timedelta(days=1),
            is_revoked=False,
        )
        db.add(session)
        db.commit()

        resp = client.post("/api/v1/auth/device/check", json={"device_id": device_id})
        data = resp.json()
        assert data["trusted"] is False


class TestDeviceSelect:
    def test_select_with_second_factor(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        u = _create_user(db, username="pinuser", family_id=family_id, pin_hash="$2b$08$fakehash")
        _create_device_session(db, user_id=u.id, family_id=family_id, device_id=device_id)

        resp = client.post("/api/v1/auth/device/select", json={
            "device_id": device_id,
            "user_id": str(u.id),
            "altcha": "test-captcha",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["second_factor_required"] is True
        assert data["temp_token"] is not None
        assert data["second_factor_type"] == "numeric_pin"

    def test_select_without_second_factor(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        u = _create_user(db, username="nopinuser", family_id=family_id)
        _create_device_session(db, user_id=u.id, family_id=family_id, device_id=device_id)

        resp = client.post("/api/v1/auth/device/select", json={
            "device_id": device_id,
            "user_id": str(u.id),
            "altcha": "test-captcha",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["second_factor_required"] is False

    def test_select_invalid_device_user_combo(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        u = _create_user(db, username="wrongdevice", family_id=family_id)

        resp = client.post("/api/v1/auth/device/select", json={
            "device_id": device_id,
            "user_id": str(u.id),
            "altcha": "test-captcha",
        })
        assert resp.status_code == 404

    def test_select_refreshes_session_expiry(self, client: TestClient, db: Session, family_id: int):
        device_id = str(uuid.uuid4())
        u = _create_user(db, username="refreshuser", family_id=family_id)
        session = _create_device_session(db, user_id=u.id, family_id=family_id, device_id=device_id)
        old_expires = session.expires_at

        resp = client.post("/api/v1/auth/device/select", json={
            "device_id": device_id,
            "user_id": str(u.id),
            "altcha": "test-captcha",
        })
        assert resp.status_code == 200

        db.refresh(session)
        assert session.expires_at > old_expires
```

- [ ] **Step 2: Run tests**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/backend/tests/test_device_multi_account.py -v 2>&1 | tail -30`
Expected: all pass (tests may need fixture adjustments for `client`, `db`, `family_id` — adapt to existing conftest.py patterns)

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/tests/test_device_multi_account.py
git commit -m "test(device): add multi-account device binding test suite"
```

---

### Task 12: Update frontend API types for multi-account

**Files:**
- Modify: `frontend/apps/main/src/api/device.ts`

- [ ] **Step 1: Update types and add selectDeviceUser**

Replace the content of `frontend/apps/main/src/api/device.ts`:

```typescript
import http from './index'

export interface DeviceCheckUser {
  user_id: string
  display_name: string
  avatar_color: string
  role: string
  second_factor_type: string | null
  last_seen_at: string
}

export interface DeviceCheckResponse {
  trusted: boolean
  users: DeviceCheckUser[]
}

export function checkDevice(deviceId: string) {
  return http.post<DeviceCheckResponse>('/auth/device/check', { device_id: deviceId })
}

export interface DeviceSelectResponse {
  second_factor_required: boolean
  temp_token?: string
  second_factor_type?: string
  display_name?: string
  avatar_color?: string
}

export function selectDeviceUser(deviceId: string, userId: string, altcha: string) {
  return http.post<DeviceSelectResponse>('/auth/device/select', {
    device_id: deviceId,
    user_id: userId,
    altcha,
  })
}

export interface DeviceTrustResponse {
  session_id: string
  device_id: string
  device_name: string
  expires_at: string
}

export interface DeviceSession {
  session_id: string
  device_id: string | null
  device_name: string
  created_at: string
  last_seen_at: string
  expires_at: string
  is_current: boolean
}

export function listDevices() {
  return http.get<DeviceSession[]>('/auth/devices')
}

export function revokeDevice(sessionId: string) {
  return http.delete(`/auth/devices/${sessionId}`)
}

export function revokeAllDevices() {
  return http.delete('/auth/devices')
}

export interface FamilyDevice {
  session_id: string
  device_id: string | null
  user_id: string
  display_name: string
  avatar_color: string
  device_name: string
  last_seen_at: string
  created_at: string
  is_current: boolean
}

export async function listFamilyDevices() {
  const { data } = await http.get<FamilyDevice[]>('/auth/devices/family')
  return data
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: type errors in LoginPage.vue (old API shape references) — fixed in next task

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/api/device.ts
git commit -m "feat(api): update device types for multi-user response + add selectDeviceUser"
```

---

### Task 13: Add i18n strings for Step 0

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Add Chinese i18n strings**

In `zh-CN.ts`, add under the appropriate `login` or `device` section (or create a `login` section if not existing):

```typescript
login: {
  otherAccount: '其他账户登录',
  selectAccount: '选择账户',
  verifyToContinue: '验证后继续',
},
role: {
  owner: '管理员',
  admin: '大人',
  child: '儿童',
},
```

- [ ] **Step 2: Add English i18n strings**

In `en-US.ts`, add matching keys:

```typescript
login: {
  otherAccount: 'Other Account',
  selectAccount: 'Select Account',
  verifyToContinue: 'Verify to continue',
},
role: {
  owner: 'Owner',
  admin: 'Adult',
  child: 'Child',
},
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(i18n): add login.otherAccount, role.* strings for account carousel"
```

---

### Task 14: Implement Step 0 carousel in LoginPage.vue

**Files:**
- Modify: `frontend/apps/main/src/pages/LoginPage.vue`

This is the largest task — adds the Step 0 account selection carousel with van-swipe.

- [ ] **Step 1: Update step type and add state variables**

Change the step type from `ref<1 | 2>(1)` to `ref<0 | 1 | 2>(1)` (line 193).

Add new state variables after the existing `trustedUser` ref:

```typescript
interface BoundUser {
  userId: string
  displayName: string
  avatarColor: string
  role: string
  secondFactorType: string | null
}
const boundUsers = ref<BoundUser[]>([])
const selectedUser = ref<BoundUser | null>(null)
const deviceId = ref<string | null>(null)
const selectAltchaRef = ref()
const selectAltcha = ref<string | undefined>(undefined)
```

- [ ] **Step 2: Update imports**

Add `selectDeviceUser` to the device API import:

```typescript
import { checkDevice, selectDeviceUser } from '@/api/device'
import type { DeviceCheckUser } from '@/api/device'
```

- [ ] **Step 3: Rewrite onMounted for multi-user detection**

Replace the `onMounted` block with:

```typescript
onMounted(async () => {
  try {
    let did = await readDeviceId()
    if (!did) {
      did = await recoverFromEtag()
    }
    if (!did) return

    deviceId.value = did
    const { data } = await checkDevice(did)

    if (data.trusted && data.users.length > 0) {
      boundUsers.value = data.users.map((u: DeviceCheckUser) => ({
        userId: String(u.user_id),
        displayName: u.display_name,
        avatarColor: u.avatar_color,
        role: u.role,
        secondFactorType: u.second_factor_type,
      }))
      step.value = 0
    }
  } catch {
    // Non-fatal — fall through to step 1
  }
})
```

- [ ] **Step 4: Add account selection handlers**

Add these functions:

```typescript
function onSelectUser(user: BoundUser) {
  selectedUser.value = user
}

function switchToStep1() {
  step.value = 1
  selectedUser.value = null
  boundUsers.value = []
}

async function onSelectAltchaComplete() {
  if (!selectedUser.value || !deviceId.value || !selectAltcha.value) return
  loading.value = true
  try {
    const { data } = await selectDeviceUser(
      deviceId.value,
      selectedUser.value.userId,
      selectAltcha.value,
    )
    if (data.second_factor_required && data.temp_token) {
      tempToken.value = data.temp_token
      secondFactorType.value = data.second_factor_type ?? 'numeric_pin'
      trustedUser.value = {
        displayName: data.display_name ?? selectedUser.value.displayName,
        avatarColor: data.avatar_color ?? selectedUser.value.avatarColor,
      }
      stepLoading.value = true
      setTimeout(() => {
        step.value = 2
        stepLoading.value = false
      }, 700)
    } else {
      // No second factor — login complete
      await authStore.fetchMe()
      showToast(t('toast.loginSuccess'))
      authStore.showTrustPrompt = true
      const user = authStore.user
      if (user?.role === 'child') {
        const baseUrl = import.meta.env.VITE_MAIN_APP_URL || ''
        window.location.href = `${baseUrl}/child/`
        return
      }
      router.push('/')
    }
  } catch (error: unknown) {
    const axiosError = error as { response?: { data?: { code?: string; message?: string }; status?: number } }
    const code = axiosError.response?.data?.code
    if (code) {
      const i18nKey = `errors.${code}`
      showToast(t(i18nKey) !== i18nKey ? t(i18nKey) : axiosError.response?.data?.message || t('toast.loginFailedGeneric'))
    } else {
      showToast(t('toast.loginFailedGeneric'))
    }
    selectAltchaRef.value?.reset()
    selectAltcha.value = undefined
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 5: Add Step 0 template**

In the template section, wrap the existing Step 1 and Step 2 in a 3-way transition. Add Step 0 before Step 1:

```vue
<!-- Step 0: Account carousel -->
<div v-if="step === 0" key="step0" class="account-select-step">
  <NuminaLogo class="numina-logo" :width="220" />
  <p class="step0-subtitle">{{ t('login.selectAccount') }}</p>

  <van-swipe :loop="false" :width="260" :show-indicators="true" class="account-swipe">
    <van-swipe-item
      v-for="user in boundUsers"
      :key="user.userId"
      @click="onSelectUser(user)"
    >
      <div class="account-card" :class="{ selected: selectedUser?.userId === user.userId }">
        <div class="account-avatar" :style="{ background: user.avatarColor }">
          {{ user.displayName.charAt(0) }}
        </div>
        <p class="account-name">{{ user.displayName }}</p>
        <span class="account-role">{{ t(`role.${user.role}`) }}</span>
      </div>
    </van-swipe-item>

    <van-swipe-item @click="switchToStep1">
      <div class="account-card account-card--other">
        <div class="account-avatar account-avatar--add">+</div>
        <p class="account-name">{{ t('login.otherAccount') }}</p>
      </div>
    </van-swipe-item>
  </van-swipe>

  <!-- ALTCHA captcha shown after selecting a user -->
  <Transition name="step-fade">
    <div v-if="selectedUser" class="select-captcha-area">
      <p class="captcha-hint">{{ t('login.verifyToContinue') }}</p>
      <AltchaWidget
        ref="selectAltchaRef"
        v-model="selectAltcha"
        endpoint="login"
        @complete="onSelectAltchaComplete"
      />
    </div>
  </Transition>
</div>
```

Update the existing `v-if="step === 1"` and `v-else` (step 2) conditionals to use `v-else-if="step === 1"` and `v-else` respectively.

- [ ] **Step 6: Add Step 0 CSS**

Add styles at the bottom of the `<style scoped>` block:

```css
/* Step 0: Account carousel */
.account-select-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 60px;
}

.step0-subtitle {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  margin-bottom: 24px;
}

.account-swipe {
  width: 100%;
  max-width: 340px;
}

.account-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
  border: 2px solid rgba(189, 187, 255, 0.35);
  transition: border-color 0.2s, box-shadow 0.2s;
  min-height: 160px;
  justify-content: center;
}

.account-card.selected {
  border-color: #bdbbff;
  box-shadow: 0 0 20px rgba(189, 187, 255, 0.4);
}

.account-card--other {
  opacity: 0.7;
}

.account-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 12px;
}

.account-avatar--add {
  background: rgba(189, 187, 255, 0.2);
  font-size: 32px;
  font-weight: 300;
}

.account-name {
  color: var(--text-primary, #f5f5f5);
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.account-role {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.select-captcha-area {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.captcha-hint {
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
}

/* Override van-swipe indicators */
.account-swipe :deep(.van-swipe__indicator) {
  background: rgba(189, 187, 255, 0.3);
}

.account-swipe :deep(.van-swipe__indicator--active) {
  background: #bdbbff;
}
```

- [ ] **Step 7: Run typecheck**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm typecheck`
Expected: passes

- [ ] **Step 8: Run lint**

Run: `cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm lint`
Expected: passes

- [ ] **Step 9: Commit**

```bash
git add frontend/apps/main/src/pages/LoginPage.vue
git commit -m "feat(login): add Step 0 account carousel with van-swipe + ALTCHA"
```

---

### Task 15: Manual QA verification checklist

This task has no code — it validates the full flow.

- [ ] **Step 1: Start backend and frontend dev servers**

In separate terminals:
```bash
# Terminal 1
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run uvicorn apps.backend.app.main:app --reload --port 8000

# Terminal 2
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm dev
```

- [ ] **Step 2: Verify no device_id → shows Step 1 directly**

Open incognito browser, navigate to login page. Should show username/password form (Step 1).

- [ ] **Step 3: Verify device trust creates all persistence layers**

Login with a test user, trust the device. Check:
- Cookie `numina_device_id` exists
- `localStorage._numina_device_id` exists
- IndexedDB `numina_device_store` → `kv` → `device_id` exists

- [ ] **Step 4: Verify multi-user binding shows carousel**

Trust device with a second user account. Clear session (logout), refresh login page. Should show Step 0 carousel with both users.

- [ ] **Step 5: Verify account selection + captcha → Step 2 PIN**

Click a user card, complete ALTCHA, verify transition to PIN step.

- [ ] **Step 6: Verify "Other Account" → Step 1**

Click the "+" card, verify transition to username/password form.

- [ ] **Step 7: Verify ETag recovery**

Clear cookies + localStorage (keep browser cache). Refresh login page. Should still detect device via ETag and show carousel.

- [ ] **Step 8: Run full test suite**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/server && uv run pytest apps/backend/tests/ -v -k "device" 2>&1 | tail -30
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/packages/auth && pnpm test:run
cd /Volumes/LexarSSDNQ790/geek_space/github/numina/frontend/apps/main && pnpm typecheck
```

Expected: all pass.

---

## Dependency Graph

```
Task 1 (settings) ← Task 2 (replace hardcode) ← Task 3 (device-ping)
                                                      ↓
Task 4 (deviceIdentity rewrite) ← Task 5 (tests) ← Task 6 (LoginPage async mount) ← Task 7 (ETag on trust)
                                                                                            ↓
Task 8 (schemas) ← Task 9 (check multi-user) ← Task 10 (select endpoint) ← Task 11 (backend tests)
                                                                                    ↓
Task 12 (frontend API types) ← Task 13 (i18n) ← Task 14 (Step 0 carousel) ← Task 15 (QA)
```

Tasks within the same phase can be partially parallelized:
- Phase 1: Tasks 1-3 (backend) can run in parallel with Tasks 4-5 (frontend deviceIdentity)
- Phase 2: Task 8-11 (backend) can run in parallel with Task 12-13 (frontend prep)
