# Unified Auth System Design

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Unify the adult (frontend/apps/main) and child (frontend/apps/child) login systems with trusted-device fast login, family device management, and removal of the child-view-switch feature.

**Architecture:** Shared `AuthStep1Form` component in `@numina/auth` package; trusted-device check on page load skips Step 1 entirely; child devices managed by parents in the adult DevicesPage.

**Tech Stack:** Vue 3, TypeScript, Pinia (`@numina/auth`), FastAPI backend, httpOnly cookie auth.

---

## Current State

| Dimension | Adult (main) | Child (child) |
|-----------|-------------|---------------|
| Login page | `LoginPage.vue` — standalone | `ChildAuthPage.vue` — standalone |
| Step 1 | username + password + ALTCHA | username + password |
| Step 2 | 6-digit numeric PIN | 4-emoji PIN or WebAuthn |
| Auth store | `useAuthStore` | `useChildAuthStore` |
| Device trust | Full (DevicesPage) | None |
| Trusted-device fast login | No | No |

---

## T1: Backend — Extend `/auth/device/check`

**File:** `backend/app/routers/device.py` + `backend/app/services/device.py`

When fingerprint matches a trusted device, return a pre-issued `temp_token` so the frontend can skip Step 1 entirely.

**Request:** `POST /auth/device/check`
```json
{ "fingerprint": "<sha256>" }
```

**Response (trusted):**
```json
{
  "trusted": true,
  "temp_token": "<jwt>",
  "display_name": "Vincent",
  "avatar_color": "#6366f1",
  "second_factor_type": "numeric_pin",
  "user_id": 1
}
```

**Response (not trusted):**
```json
{ "trusted": false }
```

Backend logic:
1. Look up `DeviceSession` by `browser_fingerprint` (active, not expired, not revoked)
2. If found: load the associated `User`, call `create_temp_token(user)` (same as step1 success path), return full response
3. If not found: return `{ trusted: false }`

---

## T2: Backend — `GET /auth/devices/family`

**File:** `backend/app/routers/device.py`

Returns all active device sessions for every member of the caller's family. Only `owner` or `admin` role may call this.

**Response:**
```json
[
  {
    "id": 42,
    "user_id": 3,
    "display_name": "小宝",
    "avatar_color": "#f59e0b",
    "device_name": "iPhone · Safari",
    "last_seen_at": "2026-05-01T12:00:00Z",
    "created_at": "2026-04-15T08:00:00Z",
    "is_current": false
  }
]
```

Revoke via existing `DELETE /auth/devices/{device_id}` — backend already validates ownership.

---

## T3: Frontend — `AuthStep1Form` shared component

**File:** `frontend/packages/auth/src/components/AuthStep1Form.vue`

Props:
- `showAltcha: boolean` — show ALTCHA widget (adult only)
- `loading: boolean`

Emits:
- `submit(username: string, password: string, altchaToken?: string)`

Contains: username input, password input, conditional ALTCHA, submit button. No store calls — pure form.

Export from `frontend/packages/auth/src/index.ts`.

---

## T4: Frontend — `TrustedDeviceCard` component

**File:** `frontend/packages/auth/src/components/TrustedDeviceCard.vue`

Props:
- `displayName: string`
- `avatarColor: string`
- `loading: boolean`

Emits:
- `confirm` — user tapped the card, proceed to Step 2
- `switchAccount` — user wants to log in as someone else

UI: avatar circle (color + initials) + display name + "点击登录" hint + "切换账户" link below.

Export from `frontend/packages/auth/src/index.ts`.

---

## T5: Frontend — `LoginPage.vue` fast login

**File:** `frontend/apps/main/src/pages/LoginPage.vue`

On `onMounted`:
1. Call `getDeviceFingerprint()` then `POST /auth/device/check`
2. If `trusted: true` → store `temp_token`, set `step = 2`, render `TrustedDeviceCard` above the PIN pad
3. If `trusted: false` → render existing Step 1 form (no change)

Step 2 (numeric PIN) unchanged. After PIN success, existing device-trust prompt flow unchanged.

---

## T6: Frontend — `ChildAuthPage.vue` fast login

**File:** `frontend/apps/child/src/pages/ChildAuthPage.vue`

Same pattern as T5:
1. On mount: call device/check
2. Trusted → show `TrustedDeviceCard`, skip to Step 2 (emoji PIN or WebAuthn)
3. Not trusted → existing Step 1 form

---

## T7: Frontend — `DevicesPage.vue` family devices tab

**File:** `frontend/apps/main/src/pages/DevicesPage.vue`

Add two tabs: 「我的设备」(existing) and 「儿童设备」(new).

「儿童设备」tab:
- Calls `GET /auth/devices/family`
- Groups results by `display_name`
- Each row: avatar + name + device_name + last_seen + revoke button
- Only shown if current user is `owner` or `admin`

---

## T8: Frontend — Remove child-view-switch entries

**Files to change:**
1. `frontend/apps/main/src/pages/LoginPage.vue` — remove "儿童登录" link
2. Find and remove "切换视角" button in child management page (likely `ChildManagePage.vue` or `FamilyMembersPage.vue` under settings)

Do NOT remove backend `POST /auth/admin/switch-child/{child_id}` — may be used elsewhere.

---

## Implementation Order

```
T1 (backend device/check) ──┐
T2 (backend family devices) ─┤── parallel
                              │
T3 (AuthStep1Form) ──────────┤── parallel with backend
T4 (TrustedDeviceCard) ──────┘
                              │
T5 (LoginPage fast login) ───┐── depends on T1 + T4
T6 (ChildAuthPage fast login)┘
                              │
T7 (DevicesPage family tab) ─── depends on T2
T8 (remove switch entries) ──── independent
```
