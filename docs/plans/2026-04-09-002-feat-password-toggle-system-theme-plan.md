---
title: "feat: Add password visibility toggle and default system theme"
type: feat
status: completed
date: 2026-04-09
---

# feat: Add password visibility toggle and default system theme

## Overview

Two small UX improvements:
1. Add an eye-icon toggle to password fields on the login page (and join-family page) so users can reveal their password while typing.
2. Change the app's default theme fallback from `'light'` to `'system'` so first-time or logged-out users get a theme that matches their OS preference.

## Problem Frame

- **Password toggle**: The register page already has a working eye-icon toggle pattern using Vant's `#right-icon` slot. The login page and join-family page use hardcoded `type="password"` with no toggle, creating an inconsistent experience.
- **System theme default**: The app fully supports `'system'` theme resolution (media query listener, `resolvedTheme` computed, `van-config-provider` binding) but the fallback when no user preference is set is hardcoded to `'light'`. Users who prefer dark mode see a flash of light theme until they manually change it in settings.

## Requirements Trace

- R1. Login page password field has an eye-icon toggle that reveals/hides the password, matching the existing register page pattern.
- R2. JoinFamilyPage password field has the same eye-icon toggle.
- R3. The app defaults to the OS color scheme preference when no user theme preference is stored (i.e., unauthenticated or first login).
- R4. No regression to existing theme switching behavior in SettingsPage or the authenticated user flow.

## Scope Boundaries

- No changes to the backend `User.theme` field or API.
- No changes to `SettingsPage.vue` theme picker UI — the existing `'light'` / `'dark'` / `'system'` options remain as-is.
- `useSettingsStore` localStorage-based theme logic is out of scope — it is unused by `App.vue` and touching it risks unintended side effects.
- Register page password toggle is already correct — no changes needed there.

## Context & Research

### Relevant Code and Patterns

- **Reference implementation**: `frontend/src/pages/RegisterPage.vue` — complete eye-icon toggle using `#right-icon` slot, `van-icon` with `eye-o` / `closed-eye` names, `ref(false)` state, and `.password-field-wrapper :deep(.van-field__right-icon)` CSS.
- **Login page gap**: `frontend/src/pages/LoginPage.vue` — `type="password"` hardcoded, no `#right-icon` slot.
- **JoinFamily page gap**: `frontend/src/pages/JoinFamilyPage.vue` — `type="password"` hardcoded on password field(s), no toggle.
- **Theme fallback**: `frontend/src/App.vue` — `authStore.user?.theme || 'light'` is the only change point. `resolvedTheme` computed and `mediaQuery` listener are already wired for `'system'`.

### Institutional Learnings

- No prior documented solutions for password toggle or theme default in `docs/solutions/`.

## Key Technical Decisions

- **Mirror RegisterPage pattern exactly**: Use `#right-icon` slot with `van-icon` (`eye-o` / `closed-eye`), a local `ref(false)` per field, and the same `:deep(.van-field__right-icon)` CSS. This avoids introducing a new abstraction for a two-file change.
- **Single-line theme default change**: Change `|| 'light'` to `|| 'system'` in `App.vue`. The system detection infrastructure is already complete — no new logic needed.
- **Scope includes JoinFamilyPage**: It has the same gap as LoginPage and is a natural inclusion for consistency, even though the user's request mentioned only login and register.

## Open Questions

### Resolved During Planning

- **Does RegisterPage already have the toggle?** Yes — it is the reference implementation. No changes needed there.
- **Is the system theme infrastructure already in place?** Yes — `resolvedTheme` computed, `mediaQuery` listener, and `van-config-provider` binding are all wired. Only the fallback string needs updating.
- **Should JoinFamilyPage be included?** Yes — it has the same gap and the fix is identical. Excluding it would leave an inconsistency.

### Deferred to Implementation

- **Exact number of password fields in JoinFamilyPage**: The page may have one or two password fields (invite code is not a password). Implementer should read the file and apply the toggle only to fields with `type="password"`.

## Implementation Units

- [ ] **Unit 1: Add password visibility toggle to LoginPage**

**Goal:** Match the eye-icon toggle pattern from RegisterPage on the login password field.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `frontend/src/pages/LoginPage.vue`

**Approach:**
- Add a `showPassword` ref initialized to `false` in `<script setup>`
- Change the password `van-field` from `type="password"` to `:type="showPassword ? 'text' : 'password'"`
- Add `#right-icon` slot with `<van-icon :name="showPassword ? 'eye-o' : 'closed-eye'" @click="showPassword = !showPassword" />`
- Add `.password-field-wrapper :deep(.van-field__right-icon)` CSS scoped to this component

**Patterns to follow:**
- `frontend/src/pages/RegisterPage.vue` — exact same slot, icon names, ref pattern, and CSS

**Test scenarios:**
- Happy path: User clicks eye icon on login page → password text becomes visible; icon changes to `eye-o`; clicking again hides it and icon reverts to `closed-eye`
- Edge case: Password field is empty → toggle still works without error
- Edge case: User submits form while password is visible → form submission uses the actual password value regardless of visibility state

**Verification:**
- Login page password field shows eye icon on the right
- Clicking the icon toggles between visible and hidden password text
- Visual appearance matches the register page toggle

---

- [ ] **Unit 2: Add password visibility toggle to JoinFamilyPage**

**Goal:** Apply the same eye-icon toggle to password field(s) on the join-family page.

**Requirements:** R2

**Dependencies:** None (parallel with Unit 1)

**Files:**
- Modify: `frontend/src/pages/JoinFamilyPage.vue`

**Approach:**
- Read the file first to identify which fields use `type="password"`
- Apply the same ref + slot + CSS pattern from RegisterPage to each password field
- Use separate refs per field if there are multiple (e.g., `showPassword`, `showConfirmPassword`)

**Patterns to follow:**
- `frontend/src/pages/RegisterPage.vue` — same pattern, including separate refs for multiple fields

**Test scenarios:**
- Happy path: Eye icon appears on join-family password field(s); clicking toggles visibility
- Edge case: If two password fields exist, each toggle operates independently

**Verification:**
- All `type="password"` fields on JoinFamilyPage have a working eye-icon toggle
- No visual regression on the rest of the form

---

- [ ] **Unit 3: Change default theme fallback to `'system'`**

**Goal:** Unauthenticated users and users with no stored theme preference see the OS color scheme by default.

**Requirements:** R3, R4

**Dependencies:** None (independent of Units 1–2)

**Files:**
- Modify: `frontend/src/App.vue`

**Approach:**
- Locate the line `authStore.user?.theme || 'light'` (currently the theme resolution fallback)
- Change `'light'` to `'system'`
- No other changes — `resolvedTheme` computed already handles `'system'` by reading `window.matchMedia('(prefers-color-scheme: dark)')`

**Patterns to follow:**
- Existing `resolvedTheme` computed in `App.vue` — the `'system'` branch is already implemented

**Test scenarios:**
- Happy path (OS dark): User visits app without being logged in on a device with dark mode → app renders in dark theme
- Happy path (OS light): Same scenario with light mode OS → app renders in light theme
- Edge case: Authenticated user with `theme: 'light'` stored → still gets light theme (fallback not reached)
- Edge case: Authenticated user with `theme: 'system'` stored → resolves to OS preference (existing behavior, unchanged)
- Integration: User changes OS theme while app is open and no user preference is set → app theme updates reactively (media query listener already handles this)

**Verification:**
- Opening the app in a browser with dark mode OS preference shows dark theme before login
- Opening with light mode OS preference shows light theme before login
- Authenticated users with explicit theme preferences are unaffected

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Users who previously relied on the light default may see an unexpected dark theme after this change | Low impact — this only affects unauthenticated state and users with no stored preference; authenticated users are unaffected |
| `useSettingsStore` localStorage theme logic could conflict if something reads it | Out of scope; `App.vue` does not read from `useSettingsStore`, so no conflict |

## Sources & References

- Related code: `frontend/src/pages/RegisterPage.vue` (reference implementation for password toggle)
- Related code: `frontend/src/App.vue` (theme fallback, `resolvedTheme` computed)
- Related code: `frontend/src/pages/LoginPage.vue`
- Related code: `frontend/src/pages/JoinFamilyPage.vue`
