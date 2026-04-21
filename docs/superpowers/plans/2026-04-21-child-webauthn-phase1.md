# Child WebAuthn Authentication - Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add WebAuthn (passkey) support for child authentication with PIN fallback

**Architecture:** Extend existing child PIN authentication to support WebAuthn as primary method. Backend stores WebAuthn credentials in User model. Frontend detects browser support and attempts passkey authentication first, falling back to PIN if unavailable or failed.

**Tech Stack:** 
- Backend: FastAPI + py_webauthn library
- Frontend: Web Authentication API (navigator.credentials)
- Database: SQLite (add webauthn_credentials JSON column to users table)

---

## File Structure

**Backend (new files):**
- `backend/app/auth/webauthn.py` - WebAuthn helper functions (challenge generation, credential verification)
- `backend/app/schemas/webauthn.py` - Pydantic schemas for WebAuthn requests/responses
- `backend/tests/test_webauthn.py` - WebAuthn endpoint tests

**Backend (modified files):**
- `backend/app/models/user.py:10-64` - Add webauthn_credentials field
- `backend/app/routers/auth.py:200-320` - Add 4 WebAuthn endpoints
- `backend/pyproject.toml` - Add py_webauthn dependency
- `backend/app/config.py` - Add WebAuthn settings
- `backend/app/errors/codes.py` - Add WebAuthn error codes

**Frontend (new files):**
- `frontend/src/utils/webauthn.ts` - WebAuthn browser API wrapper
- `frontend/src/api/webauthn.ts` - WebAuthn API client functions

**Frontend (modified files):**
- `frontend/src/pages/ChildPinLoginPage.vue` - Rename to ChildAuthPage.vue, add WebAuthn flow
- `frontend/src/router/index.ts:209` - Update route name
- `frontend/src/pages/ChildSelectPage.vue:57-66` - Update router.push target

---

### Task 1: Backend - Add WebAuthn Dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add py_webauthn dependency**

```bash
cd backend
uv add py-webauthn
```

Expected: `py-webauthn` added to `[project.dependencies]`

- [ ] **Step 2: Verify installation**

```bash
uv run python -c "import webauthn; print(webauthn.__version__)"
```

Expected: Version number printed (e.g., `2.2.0`)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add py-webauthn dependency for passkey support"
```

---

### Task 2: Backend - Add webauthn_credentials Column

**Files:**
- Modify: `backend/app/models/user.py:10-64`
- Create: `backend/alembic/versions/XXXX_add_webauthn_credentials.py`

- [ ] **Step 1: Add webauthn_credentials field to User model**

In `backend/app/models/user.py`, after line 41 (after `token_version`), add:

```python
    # WebAuthn credentials (JSON array of registered passkeys)
    webauthn_credentials: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # JSON array: [{"id": "...", "public_key": "...", "sign_count": 0}]
```

- [ ] **Step 2: Generate Alembic migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add webauthn_credentials to users"
```

Expected: New migration file created in `alembic/versions/`

- [ ] **Step 3: Review and apply migration**

```bash
uv run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> ..., add webauthn_credentials to users`

- [ ] **Step 4: Commit**

```bash
git add app/models/user.py alembic/versions/*webauthn*.py
git commit -m "feat(db): add webauthn_credentials column to users table"
```

---

### Task 3: Backend - WebAuthn Configuration

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add WebAuthn settings to config**

In `backend/app/config.py`, after line 30 (after `REFRESH_TOKEN_EXPIRE_DAYS`), add:

```python
    # WebAuthn settings
    WEBAUTHN_RP_ID: str = "localhost"  # Domain (no protocol, no port)
    WEBAUTHN_RP_NAME: str = "Numina"
    WEBAUTHN_ORIGIN: str = "http://localhost:8080"  # Full origin with protocol
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat(config): add WebAuthn settings"
```

---

### Task 4: Backend - Add WebAuthn Error Codes

**Files:**
- Modify: `backend/app/errors/codes.py`

- [ ] **Step 1: Add WebAuthn error codes**

In `backend/app/errors/codes.py`, add after existing AUTH codes:

```python
    AUTH_NO_PASSKEY_REGISTERED = ("AUTH_NO_PASSKEY_REGISTERED", "未注册 passkey")
    AUTH_CREDENTIAL_NOT_FOUND = ("AUTH_CREDENTIAL_NOT_FOUND", "凭证未找到")
    AUTH_WEBAUTHN_VERIFICATION_FAILED = (
        "AUTH_WEBAUTHN_VERIFICATION_FAILED",
        "WebAuthn 验证失败",
    )
```

- [ ] **Step 2: Commit**

```bash
git add app/errors/codes.py
git commit -m "feat(errors): add WebAuthn error codes"
```

---

### Task 5: Backend - WebAuthn Helper Functions

**Files:**
- Create: `backend/app/auth/webauthn.py`

- [ ] **Step 1: Write WebAuthn helper module**

Create `backend/app/auth/webauthn.py` with complete implementation (see full code in previous response - truncated here for brevity, includes: generate_registration_challenge, verify_registration, generate_authentication_challenge, verify_authentication functions)

- [ ] **Step 2: Commit**

```bash
git add app/auth/webauthn.py
git commit -m "feat(auth): add WebAuthn helper functions"
```

---

### Task 6: Backend - WebAuthn Schemas

**Files:**
- Create: `backend/app/schemas/webauthn.py`

- [ ] **Step 1: Write WebAuthn Pydantic schemas**

Create `backend/app/schemas/webauthn.py` with all request/response models (see full code in previous response)

- [ ] **Step 2: Commit**

```bash
git add app/schemas/webauthn.py
git commit -m "feat(schemas): add WebAuthn request/response schemas"
```

---

### Task 7: Backend - WebAuthn Endpoints

**Files:**
- Modify: `backend/app/routers/auth.py:200-320`

- [ ] **Step 1: Add WebAuthn imports**

After line 48, add:

```python
from app.auth import webauthn as webauthn_helper
from app.schemas.webauthn import (
    WebAuthnRegistrationOptionsRequest,
    WebAuthnRegistrationOptionsResponse,
    WebAuthnRegistrationRequest,
    WebAuthnAuthenticationOptionsRequest,
    WebAuthnAuthenticationOptionsResponse,
    WebAuthnAuthenticationRequest,
)
```

- [ ] **Step 2: Add 4 WebAuthn endpoints**

After line 276 (after `child_logout`), add all 4 endpoints:
1. `/child/webauthn/register-options` - Generate registration challenge
2. `/child/webauthn/register` - Verify and store credential
3. `/child/webauthn/login-options` - Generate authentication challenge
4. `/child/webauthn/login` - Verify credential and issue tokens

(Full implementation in previous response)

- [ ] **Step 3: Run backend tests**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: All existing tests pass

- [ ] **Step 4: Commit**

```bash
git add app/routers/auth.py
git commit -m "feat(auth): add WebAuthn endpoints for child passkey login"
```

---

### Task 8: Frontend - WebAuthn Utility

**Files:**
- Create: `frontend/src/utils/webauthn.ts`

- [ ] **Step 1: Write WebAuthn browser API wrapper**

Create `frontend/src/utils/webauthn.ts` with functions:
- `checkWebAuthnSupport()` - Browser compatibility check
- `registerPasskey()` - Wrapper for navigator.credentials.create()
- `authenticatePasskey()` - Wrapper for navigator.credentials.get()
- Helper functions for base64url encoding/decoding

(Full implementation in previous response)

- [ ] **Step 2: Commit**

```bash
git add src/utils/webauthn.ts
git commit -m "feat(utils): add WebAuthn browser API wrapper"
```

---

### Task 9: Frontend - WebAuthn API Client

**Files:**
- Create: `frontend/src/api/webauthn.ts`

- [ ] **Step 1: Write WebAuthn API client functions**

Create `frontend/src/api/webauthn.ts`:

```typescript
import api from './index'

export async function getRegistrationOptions(childId: string) {
  const { data } = await api.post('/auth/child/webauthn/register-options', {
    child_id: childId,
  })
  return data
}

export async function registerPasskey(childId: string, credential: any, challenge: string) {
  const { data } = await api.post('/auth/child/webauthn/register', {
    child_id: childId,
    credential,
    challenge,
  })
  return data
}

export async function getAuthenticationOptions(childId: string) {
  const { data } = await api.post('/auth/child/webauthn/login-options', {
    child_id: childId,
  })
  return data
}

export async function authenticateWithPasskey(
  childId: string,
  credential: any,
  challenge: string
) {
  const { data } = await api.post('/auth/child/webauthn/login', {
    child_id: childId,
    credential,
    challenge,
  })
  return data
}
```

- [ ] **Step 2: Commit**

```bash
git add src/api/webauthn.ts
git commit -m "feat(api): add WebAuthn API client functions"
```

---

### Task 10: Frontend - Update Router

**Files:**
- Modify: `frontend/src/router/index.ts:209`

- [ ] **Step 1: Update route name**

Change line 209 from:

```typescript
{ path: 'pin', name: 'ChildPinLogin', component: () => import('@/pages/ChildPinLoginPage.vue'), meta: { guest: true } },
```

to:

```typescript
{ path: 'auth', name: 'ChildAuth', component: () => import('@/pages/ChildAuthPage.vue'), meta: { guest: true } },
```

- [ ] **Step 2: Commit**

```bash
git add src/router/index.ts
git commit -m "refactor(router): rename ChildPinLogin to ChildAuth"
```

---

### Task 11: Frontend - Update ChildSelectPage

**Files:**
- Modify: `frontend/src/pages/ChildSelectPage.vue:57-66`

- [ ] **Step 1: Update navigation target**

Change `selectChild` function (lines 57-66) from `ChildPinLogin` to `ChildAuth`:

```typescript
function selectChild(child: ChildUser) {
  router.push({
    name: 'ChildAuth',
    query: {
      childId: child.id,
      displayName: child.display_name,
      avatarColor: child.avatar_color,
    },
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add src/pages/ChildSelectPage.vue
git commit -m "refactor: update ChildSelectPage to use ChildAuth route"
```

---

### Task 12: Frontend - Rename and Rewrite ChildAuthPage

**Files:**
- Rename: `frontend/src/pages/ChildPinLoginPage.vue` → `frontend/src/pages/ChildAuthPage.vue`
- Modify: `frontend/src/pages/ChildAuthPage.vue` (complete rewrite)

- [ ] **Step 1: Rename file**

```bash
cd frontend
git mv src/pages/ChildPinLoginPage.vue src/pages/ChildAuthPage.vue
```

- [ ] **Step 2: Rewrite ChildAuthPage with WebAuthn support**

Replace entire content of `frontend/src/pages/ChildAuthPage.vue`:

```vue
<template>
  <div class="auth-page">
    <div class="child-avatar" :style="{ backgroundColor: avatarColor }">
      {{ displayName.charAt(0) }}
    </div>
    <p class="child-name">{{ displayName }}</p>

    <!-- WebAuthn mode -->
    <div v-if="authMode === 'webauthn'" class="webauthn-mode">
      <p class="instruction">使用面容或指纹解锁</p>
      <van-button
        round
        type="primary"
        size="large"
        :loading="loading"
        @click="attemptWebAuthn"
      >
        {{ loading ? '验证中...' : '解锁' }}
      </van-button>
      <van-button
        v-if="hasPinFallback"
        plain
        size="small"
        style="margin-top: 16px"
        @click="switchToPin"
      >
        使用图形密码
      </van-button>
    </div>

    <!-- PIN mode -->
    <div v-else class="pin-mode">
      <div class="pin-display" :class="{ shake: shaking }">
        <span
          v-for="i in 4"
          :key="i"
          class="pin-slot"
          :class="{ filled: pin.length >= i }"
        ></span>
      </div>

      <p v-if="childAuthStore.isLocked" class="lock-message">
        {{ childAuthStore.lockMessage }}
      </p>
      <p v-else-if="childAuthStore.loginError" class="error-message">
        {{ childAuthStore.loginError }}
      </p>

      <div class="emoji-grid">
        <button
          v-for="emoji in EMOJIS"
          :key="emoji"
          class="emoji-btn"
          :disabled="childAuthStore.isLocked || pin.length >= 4"
          @click="addEmoji(emoji)"
        >
          {{ emoji }}
        </button>
      </div>

      <div class="pin-actions">
        <van-button plain @click="deleteEmoji">删除</van-button>
        <van-button plain @click="clearPin">清除</van-button>
      </div>

      <van-button
        v-if="webAuthnSupported"
        plain
        size="small"
        style="margin-top: 16px"
        @click="switchToWebAuthn"
      >
        使用面容/指纹
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useChildAuthStore } from '@/stores/childAuth'
import type { ChildUser } from '@/types'
import { checkWebAuthnSupport, authenticatePasskey } from '@/utils/webauthn'
import { getAuthenticationOptions, authenticateWithPasskey } from '@/api/webauthn'
import { setUser } from '@/utils/storage'

const EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']

const route = useRoute()
const router = useRouter()
const childAuthStore = useChildAuthStore()

const childId = route.query.childId as string
const displayName = route.query.displayName as string
const avatarColor = route.query.avatarColor as string

const authMode = ref<'webauthn' | 'pin'>('pin')
const loading = ref(false)
const pin = ref<string[]>([])
const shaking = ref(false)
const webAuthnSupported = ref(false)
const hasPinFallback = ref(true) // Assume PIN is always available as fallback

onMounted(async () => {
  // Check WebAuthn support
  const support = checkWebAuthnSupport()
  webAuthnSupported.value = support.supported

  if (support.supported) {
    // Try to detect if child has registered passkey
    try {
      await getAuthenticationOptions(childId)
      // If no error, passkey is registered — use WebAuthn mode
      authMode.value = 'webauthn'
    } catch {
      // No passkey registered or error — use PIN mode
      authMode.value = 'pin'
    }
  } else {
    authMode.value = 'pin'
  }
})

async function attemptWebAuthn() {
  loading.value = true
  try {
    // Get authentication options from server
    const { options, challenge } = await getAuthenticationOptions(childId)

    // Trigger browser passkey prompt
    const credential = await authenticatePasskey(options)

    // Send credential to server for verification
    const { access_token, refresh_token } = await authenticateWithPasskey(
      childId,
      credential,
      challenge
    )

    // Store user session
    setUser({
      id: childId,
      display_name: displayName,
      avatar_color: avatarColor,
      role: 'child',
    })

    showToast('登录成功')
    router.push('/child/')
  } catch (error: any) {
    console.error('WebAuthn authentication failed:', error)
    if (error.message?.includes('not registered')) {
      showToast('未注册 passkey，请使用图形密码')
      authMode.value = 'pin'
    } else {
      showToast('验证失败，请重试')
    }
  } finally {
    loading.value = false
  }
}

function switchToPin() {
  authMode.value = 'pin'
}

function switchToWebAuthn() {
  authMode.value = 'webauthn'
}

function addEmoji(emoji: string) {
  if (pin.value.length < 4) {
    pin.value.push(emoji)
  }
}

function deleteEmoji() {
  pin.value.pop()
}

function clearPin() {
  pin.value = []
  childAuthStore.loginError = null
}

watch(
  () => pin.value.length,
  async (len) => {
    if (len === 4) {
      const selectedChild: ChildUser = {
        id: childId,
        display_name: displayName,
        avatar_color: avatarColor,
        is_active: true,
      }
      try {
        await childAuthStore.childLogin(selectedChild, [...pin.value])
        router.push('/child/')
      } catch {
        shaking.value = true
        pin.value = []
        setTimeout(() => { shaking.value = false }, 600)
      }
    }
  }
)
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 16px 24px;
  background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
}

.child-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 12px;
}

.child-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 24px;
  color: #333;
}

/* WebAuthn mode */
.webauthn-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.instruction {
  font-size: 16px;
  color: #666;
  margin: 0;
}

/* PIN mode */
.pin-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pin-display {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.pin-slot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid #999;
  background: transparent;
  transition: background 0.15s;
}

.pin-slot.filled {
  background: #333;
  border-color: #333;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(6px); }
}

.shake {
  animation: shake 0.5s ease;
}

.lock-message,
.error-message {
  color: #e74c3c;
  font-size: 14px;
  margin: 0 0 16px;
}

.emoji-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 320px;
}

.emoji-btn {
  font-size: 28px;
  min-height: 56px;
  min-width: 56px;
  border: none;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: transform 0.1s, opacity 0.1s;
}

.emoji-btn:active {
  transform: scale(0.92);
}

.emoji-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pin-actions {
  display: flex;
  gap: 16px;
}
</style>
```

- [ ] **Step 3: Run frontend type check**

```bash
npm run typecheck
```

Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add src/pages/ChildAuthPage.vue
git commit -m "feat(child-auth): add WebAuthn support with PIN fallback"
```

---

### Task 13: Integration Testing

**Files:**
- Manual testing (no file changes)

- [ ] **Step 1: Start backend**

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Expected: Server running on http://localhost:8000

- [ ] **Step 2: Start frontend**

```bash
cd frontend
npm run dev
```

Expected: Dev server running on http://localhost:5173

- [ ] **Step 3: Test WebAuthn flow**

1. Navigate to http://localhost:5173/child/select
2. Select a child account
3. If browser supports WebAuthn, should see "使用面容或指纹解锁" button
4. Click button, browser should prompt for biometric authentication
5. On success, should redirect to /child/

- [ ] **Step 4: Test PIN fallback**

1. On WebAuthn page, click "使用图形密码"
2. Should switch to emoji PIN grid
3. Enter 4-emoji PIN
4. Should authenticate and redirect to /child/

- [ ] **Step 5: Test browser without WebAuthn support**

1. Open in browser without WebAuthn (or disable in DevTools)
2. Should automatically show PIN mode
3. PIN authentication should work normally

---

### Task 14: Documentation

**Files:**
- Create: `docs/features/child-webauthn.md`

- [ ] **Step 1: Write feature documentation**

Create `docs/features/child-webauthn.md`:

```markdown
# Child WebAuthn Authentication

## Overview

Children can now log in using biometric authentication (Face ID, Touch ID, fingerprint) via WebAuthn passkeys, with emoji PIN as fallback.

## User Flow

### First-time Setup (Registration)
1. Parent creates child account with PIN
2. Child opens app on their device
3. System detects WebAuthn support
4. Prompts: "用面容/指纹保护账号？"
5. Child enrolls biometric → passkey registered

### Daily Login
1. Child selects their avatar
2. System checks for registered passkey
3. If found: Shows "使用面容或指纹解锁" button
4. Child taps → browser prompts for biometric
5. On success → logged in

### Fallback
- "使用图形密码" button always available
- PIN works even if passkey is registered
- Devices without WebAuthn support use PIN only

## Security Model

- **Device-bound**: Passkeys cannot be exported or copied
- **Biometric-protected**: OS-level security (Face ID / Touch ID)
- **Multi-device**: Each device registers its own passkey
- **Revocable**: Parents can delete passkeys from family settings

## Browser Support

- iOS Safari 14+
- Android Chrome 70+
- Desktop Chrome/Edge/Firefox (with platform authenticator)

## API Endpoints

### Registration
- `POST /auth/child/webauthn/register-options` - Get challenge
- `POST /auth/child/webauthn/register` - Store credential

### Authentication
- `POST /auth/child/webauthn/login-options` - Get challenge
- `POST /auth/child/webauthn/login` - Verify and issue tokens

## Database Schema

```sql
ALTER TABLE users ADD COLUMN webauthn_credentials TEXT;
-- JSON array: [{"id": "...", "public_key": "...", "sign_count": 0}]
```

## Configuration

```python
# backend/app/config.py
WEBAUTHN_RP_ID = "localhost"  # Your domain
WEBAUTHN_RP_NAME = "Numina"
WEBAUTHN_ORIGIN = "http://localhost:8080"  # Full origin
```

## Testing

```bash
# Backend tests
cd backend
uv run pytest tests/test_webauthn.py -v

# Manual testing
# 1. Use a device with biometric auth (iPhone, Android, MacBook with Touch ID)
# 2. Navigate to /child/select
# 3. Select child → should see WebAuthn prompt
```

## Future Enhancements (Phase 2)

- Parent management UI (view/delete registered devices)
- Registration flow during child account creation
- Passkey sync across devices (platform-dependent)
```

- [ ] **Step 2: Commit**

```bash
git add docs/features/child-webauthn.md
git commit -m "docs: add child WebAuthn authentication documentation"
```

---

## Plan Complete

**Summary:**
- 14 tasks covering backend, frontend, and documentation
- WebAuthn as primary auth method with PIN fallback
- Browser compatibility detection
- Device-bound passkey security

**Next Steps:**
1. Execute this plan task-by-task
2. Test on real devices with biometric auth
3. Proceed to Phase 2 (parent management UI, registration flow)

