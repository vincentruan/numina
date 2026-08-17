---
title: User Avatar - Plan
date: "2026-08-15"
type: feat
topic: user-avatar
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Users (adult and child) can set personal avatars via image upload, 3D icon selection, or emoji, making them visually identifiable across the app. The existing color + first-character rendering stays as the default fallback.
- **Product authority:** Full scope over avatar selection, display, and profile editing for both adult and child users.
- **Execution:** Code — frontend Vue 3 + Vant 4, backend Python FastAPI.

---

## Product Contract

### Summary

A user avatar system where both adult and child users can set personal avatars through three sources: image upload (gallery/camera), 3D icon selection (with recovered character/people/flag/number categories), and emoji. The current color + first-character rendering is preserved as the default fallback when no avatar is set. Adults access avatar editing from a redesigned profile card on the settings page; children access it from a new header card on their settings page. Both cards use a centered avatar layout with display name as the focal point.

### Requirements

**Default avatar optimization**

- R1. The default avatar (shown when no custom avatar is set) renders the first character of `display_name` only — not the full name. The existing `avatar_color` background circle is retained.
- R2. All current avatar rendering points across the app (MemberCard, LoginPage account list, PendingApprovals, LiteracyStatusCard, and any other `charAt(0)` renderers) adopt the first-character optimization. Existing behavior for very short names (single character) is unchanged.

**Avatar data model**

- R3. The User model gains an `avatar_url` field (nullable string) to store the path or identifier of a custom avatar image or selected icon. When `avatar_url` is null/empty, the default first-character avatar (R1) is shown.
- R4. Avatar rendering is unified: any component displaying a user or child avatar checks `avatar_url` first; if present, renders the image/icon; if absent, falls back to the R1 default.

**Adult profile edit page**

- R5. A new profile edit page (route under `/settings/`) supports viewing and editing the user's avatar and display name.
- R6. The profile edit page provides three avatar sources in a bottom-sheet picker: image upload (gallery/camera), 3D icon selection, and emoji selection.
- R7. Display name editing on this page validates for non-empty and max-length constraints. The login `username` is NOT editable here — it remains on the existing `/settings/username` page.

**Avatar picker — image upload**

- R8. Image upload supports selecting from gallery or taking a photo, mirroring the existing asset icon picker's gallery/camera flow.
- R9. Uploaded images are processed (resized/compressed to reasonable dimensions) before storage. Accepted formats: JPEG, PNG, WebP.

**Avatar picker — 3D icon selection**

- R10. The 3D icon picker for user avatars includes five recovered categories beyond the existing asset categories: characters (人物角色), historical figures (历史名人), religion/mythology (宗教神话), flags (旗帜标志), and numbers/symbols (数字符号).
- R11. These five categories are visible ONLY in the user avatar picker — they remain hidden from the asset icon picker (asset avatars continue showing only asset-related categories).
- R12. 3D icon thumbnails in the user avatar picker use smaller sizing (approximately 64x64px) compared to the asset icon picker.

**Avatar picker — emoji selection**

- R13. An emoji tab alongside the 3D icon tab allows users to select an emoji as their avatar, using the system/platform emoji picker.

**Adult settings page redesign**

- R14. The settings page's first card section (currently a flat cell list from family name through invite code) is replaced by a centered profile card:
  - Centered circular avatar (64px) as the focal point — tappable to enter the profile edit page (R5).
  - Display name below the avatar, prominent (16-17px bold).
  - Family name with icon, and display name text as secondary info.
  - The profile card itself is tappable (whole card enters profile edit; no separate edit button to avoid duplicate tap targets).
- R15. The remaining account info cells (username link, role, etc.) stay below the new profile card as a separate cell group, preserving existing navigation links.

**Child settings header card**

- R16. The child app's settings page gains a new header card at the top with the same centered layout:
  - Centered circular child avatar (tappable to enter child profile edit).
  - Child display name (editable via profile edit).
  - Login username shown as small secondary text (read-only, NOT editable this phase).
  - Family name with icon.
- R17. The child profile edit experience mirrors the adult flow: same avatar picker (upload, 3D icons, emoji) and display name editing.

**Cross-cutting**

- R18. Avatar images and selected icons render consistently across all views: settings pages, member cards, login account switcher, approval sections, and any other user-representing component.
- R19. The profile card and header card support dark mode via existing CSS variables (`--color-primary`, `--van-*`).

### Key Decisions

- **Centered profile card layout over horizontal "work badge"** (session-settled: user-directed — chosen over horizontal avatar-left/info-right: centered feels warmer and more personal for a family app, avatar becomes the focal point). Governs R14, R16.
- **Extend existing IconPicker component** rather than building a separate user-avatar picker — one component to maintain, with conditional category visibility for asset vs user contexts. Governs R6, R10, R11, R13.
- **Emoji via system picker** — use the platform's native emoji picker rather than a curated set. Maximum emoji coverage with zero asset maintenance. Governs R13.
- **Display name editable, username not** — the profile page edits `display_name` (昵称), not the login `username`. Username changes remain on the existing dedicated page. Governs R7, R17.

### Key Flows

- F1. Adult edits avatar and display name
  - **Trigger:** User taps avatar or edit action on the settings page profile card.
  - **Steps:** Navigate to profile edit page → tap avatar area → bottom-sheet picker opens with three tabs (Upload / 3D Icons / Emoji) → user selects or uploads → preview updates → user optionally edits display name → tap save → avatar and/or name update across all views.
  - **Covered by:** R5, R6, R7, R8, R10, R13, R14.

- F2. Child edits avatar and display name
  - **Trigger:** Child taps avatar on the child settings header card.
  - **Steps:** Navigate to child profile edit → same picker flow as adult → save → avatar updates in child app views.
  - **Covered by:** R16, R17.

- F3. Default avatar rendering
  - **Trigger:** Any component renders a user or child avatar, and `avatar_url` is null/empty.
  - **Steps:** Fall back to the existing `avatar_color` circle with first character of `display_name`.
  - **Covered by:** R1, R2, R4.

### Acceptance Examples

- AE1. New user sees default avatar
  - **Covers R1, R2, R4.**
  - **Given** a user "王小明" with `avatar_color: "#4F46E5"` and no `avatar_url`.
  - **When** the settings page renders the profile card.
  - **Then** a 64px indigo circle shows "王" (first character only), and the display name "王小明" appears below.

- AE2. Adult sets emoji avatar
  - **Covers R6, R13.**
  - **Given** an adult user on the profile edit page.
  - **When** they tap the avatar, switch to the Emoji tab, select 😊, and save.
  - **Then** the profile card and all avatar views show 😊 as the avatar.

- AE3. Asset picker does NOT show character categories
  - **Covers R11.**
  - **Given** a user editing an asset's icon.
  - **When** the 3D icon tab is open.
  - **Then** only asset-related categories are visible (vehicles, electronics, furniture, etc.) — characters, historical figures, flags, religion/mythology, and numbers are NOT shown.

- AE4. Child settings shows header card
  - **Covers R16.**
  - **Given** a child user "小宝" logged into the child app.
  - **When** they open settings.
  - **Then** a centered profile card appears at the top showing their avatar, display name "小宝", login username as small read-only text, and family name with icon.

### Scope Boundaries

**Deferred for later:**
- Avatar cropping/rotation after upload (v1 accepts the image as-is after resize)
- Animated avatars or GIF support
- Per-family avatar themes or shared family avatars
- Avatar visibility in AI chat messages (separate concern, may follow)

**Outside this feature's identity:**
- Username change flow (existing `/settings/username` page, unchanged)
- Child approval workflow for avatar changes (children change freely)
- Group/family-level avatar or shared profile images

### Dependencies / Assumptions

- **3D icon recovery** — the five deleted categories (人物角色, 历史名人, 宗教神话, 旗帜标志, 数字符号) were removed in commit `6af543eb` but **are recoverable from git history** (parent commit `6af543eb^` contains all five folders with original files). Only the 5 needed categories need to be restored (not all 12 deleted ones). Planning handles the restore and manifest regeneration.
- **File storage abstraction** — the existing `server/packages/storage/` file storage layer is used for avatar image persistence. Planning decides storage path conventions and sizing rules.
- **Emoji rendering** — system emoji picker means rendering varies by OS/device. Acceptable for v1.
- **Orphaned avatar files** - when a user replaces an image avatar, the old file stays in storage (SHA-256 dedup prevents identical re-uploads). Known v1 limitation; no cleanup hook. Revisit if storage growth matters.

### Outstanding Questions

- **Resolved:** Avatar image storage uses existing `POST /upload/image` pipeline (5MB limit, magic bytes validation, SHA-256 dedup). Storage path follows existing convention: `uploads/{family_id}/{user_id}/{date_dir}/{uuid}.ext`.
- **Resolved:** Profile edit page and child profile edit share a single `ProfileEditPage.vue` component with role-based API routing via route props — UI and interactions are identical.

---

## Planning Contract

*Product Contract preserved unchanged — no scope or ID changes.*

### Key Technical Decisions

KTD1. **Reuse existing `POST /upload/image`** for avatar uploads rather than creating a dedicated avatar endpoint. The existing pipeline already handles magic bytes validation, SHA-256 dedup, 5MB limit, auth, and tenant isolation. V1 does not add cropping to square, but **client-side resize is required** (see R9): before calling `uploadImage()`, downscale the image to max 512x512 via canvas to avoid storing full-resolution camera photos. Governs R8, R9.

KTD2. **`avatar_url` stores URLs for uploaded images and 3D icon paths, emoji stored as literal string** in the same field. The UserAvatar component distinguishes: emoji strings (non-URL, not starting with `/`) render as text; URL values render as `<img>`. No separate `avatar_type` column needed. **Backend validation required**: a Pydantic `field_validator` on `UpdateProfileRequest.avatar_url` and `UpdateChildRequest.avatar_url` restricts values to paths starting with `/uploads/` or `/icons/3d/`, or a single emoji grapheme cluster (max 8 bytes). Rejects HTML metacharacters and arbitrary text. Governs R3, R4.

KTD3. **Extend IconPicker with `mode` prop** (`'asset'` default | `'avatar'`). Asset mode shows only asset categories (existing behavior). Avatar mode shows recovered categories (人物角色, 历史名人, 宗教神话, 旗帜标志, 数字符号) plus emoji tab. Governs R6, R10, R11, R13.

KTD4. **Extend `useIconCatalog` composable** with a category filter parameter. The composable currently reads all categories from `iconManifest`. Add an optional `avatarCategories` filter that, when provided, restricts visible categories to the avatar-specific set. Governs R10, R11.

KTD5. **Shared `ProfileEditPage.vue`** for both adult and child profile editing. Route determines context: `/settings/profile` in the **main app** for adult self-edit, `/settings/family/children/:childId/profile` in the **main app** for parent-managed child edit. Same component, different API calls based on route props (`PUT /auth/me` for adult, `PATCH /family/children/{childId}` for child). The child app's settings page (ChildSettingsPage) offers 3D icon + emoji selection only (no image upload — `POST /upload/image` requires `require_adult`). If a child wants a custom image avatar, the parent uploads it from the main app. Governs R5, R17.

KTD6. **Child avatar upload by parent** — parent uploads image via existing `POST /upload/image` (children cannot upload directly per `require_adult` dependency), then sets the resulting URL on the child via `PATCH /family/children/{child_id}`. The child's own profile edit page (in the child app) shows only 3D icon and emoji tabs — no gallery/camera buttons. Governs R17.

### Assumptions

- Recovered 3D icon categories use the same PNG format as existing categories. If thumbnails need regeneration, `pnpm generate:thumbs` handles it incrementally.
- Emoji rendering uses system native emoji. No custom emoji font or image set needed for v1.
- The existing `PUT /auth/me` endpoint (which already updates `display_name` + `avatar_color`) is the natural place to add `avatar_url` — no new endpoint needed for adult self-profile updates.

---

## Implementation Units

### U1. Backend: Add avatar_url to User model + alembic migration

- **Goal:** Add nullable `avatar_url` column to the User table and propagate through all response/update schemas.
- **Requirements:** R3
- **Dependencies:** none
- **Files:**
  - `server/packages/db/models/user.py` — add `avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)`
  - `server/apps/backend/alembic/versions/` — new migration adding `avatar_url` column to `users` table
  - `server/apps/backend/app/schemas/auth.py` — add `avatar_url: str | None = None` to `UserResponse`, `UpdateProfileRequest`, `UpdateMemberInfoRequest`, `LoginStep1Response`; add `field_validator` on `UpdateProfileRequest.avatar_url` (allows `/uploads/...`, `/icons/3d/...`, or single emoji grapheme cluster max 8 bytes; rejects HTML metacharacters and arbitrary text)
  - `server/apps/backend/app/schemas/children.py` — add `avatar_url: str | None = None` to `ChildResponse`, `UpdateChildRequest`; add same `field_validator` on `UpdateChildRequest.avatar_url`
  - `server/apps/backend/app/routers/family.py` — add `avatar_url` handling in `update_member_info` handler (lines 231-238)
  - `server/apps/backend/app/services/auth.py` — pass `avatar_url` in `login_step1` response construction (lines 596, 607)
- **Approach:**
  1. Add `avatar_url` field to User ORM model
  2. Generate alembic migration (`alembic revision --autogenerate -m "add user avatar_url"`)
  3. Add field to all Pydantic schemas (UserResponse, UpdateProfileRequest, UpdateChildRequest, UpdateMemberInfoRequest, LoginStep1Response)
  4. Add `field_validator` on `UpdateProfileRequest.avatar_url` and `UpdateChildRequest.avatar_url`: allow null, paths starting with `/uploads/` or `/icons/3d/`, or single emoji (max 8 bytes, no HTML metacharacters); reject everything else
  5. Update `update_profile` service (`server/apps/backend/app/services/auth.py`) to handle `avatar_url`
  6. Update `update_child` service (`server/apps/backend/app/services/children.py`) to handle `avatar_url`
  7. Update `update_member_info` handler in `family.py` to apply `avatar_url` from `UpdateMemberInfoRequest`
  8. Update `login_step1` service to include `avatar_url` in `LoginStep1Response` construction
- **Patterns to follow:** Existing `avatar_color` field pattern on User model. `SnowflakeBase` for response schemas. `UpdateProfileRequest` at `schemas/auth.py:201-210`.
- **Test scenarios:**
  - User model accepts `avatar_url=None` (default) and `avatar_url="/uploads/..."` without error
  - `UserResponse` serializes `avatar_url` as null when not set, as string when set
  - `PUT /auth/me` with `avatar_url` updates the field; without it, field is unchanged
  - `PATCH /family/children/{id}` with `avatar_url` updates the child's field
  - `LoginStep1Response` includes `avatar_url` (login page account switcher renders custom avatars)
  - Validator: `/uploads/f1/u1/20260815/abc.jpg` accepted; `/icons/3d/characters/x.png` accepted; single emoji accepted; `<script>alert(1)</script>` rejected; `https://evil.com/img.png` rejected; `javascript:alert(1)` rejected
  - `update_member_info` endpoint applies `avatar_url` from request body
  - Alembic migration applies cleanly to existing database and rolls back
- **Verification:** `pytest` passes for auth and children test suites. Migration applies and reverses.

### U2. Frontend: Recover 3D avatar icon categories from git history

- **Goal:** Restore the five deleted 3D icon categories (人物角色, 历史名人, 宗教神话, 旗帜标志, 数字符号) from git history into the `3d-things/` directory, and update the manifest build script to include them.
- **Requirements:** R10
- **Dependencies:** none
- **Files:**
  - `frontend/packages/assets/src/icons/3d-things/` — restore 5 folders from `6af543eb^`
  - `frontend/apps/main/scripts/build-icon-manifest.ts` — add 5 new `CATEGORY_DEFS` entries
  - `frontend/packages/assets/src/icons/icon-manifest.ts` — regenerated (auto)
- **Approach:**
  1. Use `git checkout 6af543eb^ -- <folder>` to restore each of the 5 directories with their Chinese names (人物角色, 历史名人, 宗教神话, 旗帜标志, 数字符号)
  2. Rename folders to English (matching existing convention): `characters`, `historical-figures`, `religion-mythology`, `flags`, `numbers-symbols`
  3. Add 5 entries to `CATEGORY_DEFS` in `build-icon-manifest.ts` with appropriate `nameZh`, `nameEn`, `sortOrder`, and `assetCategoryHints: []` (empty — these are avatar-only)
  4. Run `pnpm build:manifest` to regenerate `icon-manifest.ts`
  5. Generate WebP thumbnails for restored categories via `pnpm generate:thumbs`
- **Patterns to follow:** Existing `CATEGORY_DEFS` entries in `build-icon-manifest.ts:25-42`. English folder naming convention (e.g., `clothing-accessories`, `office-stationery`).
- **Test scenarios:**
  - All 5 restored folders contain PNG files with bilingual naming (`中文名_English Name.png`)
  - `build-icon-manifest.ts` produces a valid manifest including the 5 new categories
  - `icon-manifest.ts` exports the new categories with correct `nameZh`/`nameEn`
  - `assetCategoryHints` is empty for all 5 new categories (they are avatar-only)
- **Verification:** `pnpm build:manifest` succeeds. `icon-manifest.ts` contains 5 new categories. Thumbnail generation completes.

### U3. Frontend: Extend IconPicker and useIconCatalog for avatar mode

- **Goal:** Add a `mode` prop to IconPicker and category filtering to `useIconCatalog` so the picker can show avatar-specific categories and an emoji tab.
- **Requirements:** R6, R11, R12, R13
- **Dependencies:** U2
- **Files:**
  - `frontend/apps/main/src/composables/useIconCatalog.ts` — add `avatarOnly` filter parameter
  - `frontend/apps/main/src/components/asset/IconPicker.vue` — add `mode` prop, emoji tab, conditional category visibility, 64x64 thumbnail sizing for avatar mode
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add i18n keys for emoji tab
  - `frontend/apps/main/src/i18n/locales/en-US.ts` — add i18n keys for emoji tab
- **Approach:**
  1. Extend `useIconCatalog` with an optional `avatarCategories` parameter that filters `iconManifest.categories` to only show the 5 avatar-specific categories when in avatar mode
  2. Add `mode: 'asset' | 'avatar'` prop to IconPicker (default: `'asset'`)
  3. In avatar mode: show 3 tabs (`gallery`, `3d`, `emoji`); in asset mode: show 2 tabs (existing behavior)
  4. Emoji tab: on tap, focus a hidden `<input type="text">` to trigger the OS-native emoji keyboard/input; the selected emoji is captured via the input event and emitted as `select-emoji`. No curated emoji grid.
  5. In avatar mode: use 64x64 grid cells instead of current size; 6-column grid instead of 5
  6. Add new emit: `select-emoji` (emits emoji string) — separate from `select-image`
  7. Pass `avatarCategories` to `useIconCatalog` when `mode === 'avatar'`
- **Patterns to follow:** Existing IconPicker tab structure (`activeTab` ref, lines 24-35). Grid layout (`grid-template-columns`, line 437). `useIconCatalog` composable pattern (lines 1-60).
- **Test scenarios:**
  - Asset mode (default): only asset categories visible, 2 tabs — existing behavior unchanged (Covers R11, AE3)
  - Avatar mode: 3 tabs visible (gallery, 3D, emoji), only 5 avatar categories + "All" in 3D tab
  - Emoji tab: tapping an emoji emits `select-emoji` with the emoji string
  - Avatar mode thumbnails render at ~64x64px (Covers R12)
  - AssetForm still works correctly with default mode prop (no regression)
- **Verification:** Visual check in browser — asset picker unchanged, avatar picker shows correct categories and emoji tab.

### U4. Frontend: Create unified UserAvatar component

- **Goal:** A reusable component that renders user/child avatars — image URL as `<img>`, emoji as text, or first-character fallback with `avatar_color` background.
- **Requirements:** R1, R2, R4, R18, R19
- **Dependencies:** U1
- **Files:**
  - `frontend/apps/main/src/components/common/UserAvatar.vue` — main app component (create)
  - `frontend/apps/child/src/components/common/UserAvatar.vue` — child app component (create) - the two apps are separate Vite builds with different dark-mode mechanisms (main: van-config-provider; child: clay.css + `[data-theme]`), so the component is duplicated with app-local styling; only tokens common to both systems are used
- **Approach:**
  1. Props: `avatarUrl: string | null`, `avatarColor: string`, `displayName: string`, `size: number` (default 36)
  2. Rendering logic: if `avatarUrl` starts with `/` → render `<img>`; if `avatarUrl` is a non-empty non-URL string → render as emoji text; if null/empty → render `avatar_color` circle with `display_name.charAt(0)`
  3. Use CSS variables for dark mode (`var(--color-primary)`, `var(--van-text-color)`)
  4. No inline styles for theme-sensitive properties - use CSS classes. Exception: the fallback circle's `avatar_color` background stays inline (user data, not theme state)
  5. Circular shape via `border-radius: 50%`
  6. `<img>` uses `object-fit: cover` + an `@error` handler that clears the local image-source flag so a broken URL falls back to the first-character rendering
  7. Add `alt`/`aria-label` derived from `displayName` for accessibility
- **Patterns to follow:** Existing avatar rendering in `MemberCard.vue:3-7` (char + color circle). Dark mode: CSS variables per `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`.
- **Test scenarios:**
  - `avatarUrl=null` → renders colored circle with first character of `displayName` (Covers R1, AE1)
  - `avatarUrl="/uploads/..."` → renders `<img>` with the URL
  - `avatarUrl` pointing to a deleted/broken URL -> `@error` fires, falls back to first-character rendering
  - `avatarUrl="😊"` → renders emoji text centered in circle
  - `size=64` → renders at 64px; `size=36` → renders at 36px
  - Dark mode: avatar circle uses CSS variables, no inline style conflicts
  - Single-character `displayName` renders correctly (no truncation issues)
- **Verification:** Component renders correctly in all three modes (fallback, image, emoji). Dark mode compatible.

### U5. Frontend: Profile edit page

- **Goal:** New page for editing user avatar and display name, accessible from settings pages.
- **Requirements:** R5, R6, R7, R8
- **Dependencies:** U1, U3, U4
- **Files:**
  - `frontend/apps/main/src/pages/ProfileEditPage.vue` — new page (create)
  - `frontend/apps/main/src/router/index.ts` - add BOTH routes: `settings/profile` (adult self-edit) and `settings/family/children/:childId/profile` (parent-managed child edit), both lazy-loaded -> `ProfileEditPage.vue` with different route props
  - `frontend/apps/main/src/api/auth.ts` — add `updateProfile()` function calling `PUT /auth/me`
  - `frontend/packages/auth/src/types.ts` — add `avatar_url` to User interface
  - `frontend/packages/auth/src/stores/auth.ts` — update store to carry `avatar_url`
- **Approach:**
  1. Add `avatar_url?: string | null` to frontend `User` type and auth store
  2. Create `ProfileEditPage.vue` with:
     - Top section: large avatar preview (tappable to open picker) + display name field
     - Avatar picker integration: use IconPicker with `mode="avatar"`, handle `select-image`, `select-emoji`, `request-gallery`, `request-camera`
     - Gallery/camera flow: hidden file inputs → upload via `uploadImage()` → set `avatar_url`
     - Display name: `van-field` with validation (non-empty, max 100 chars)
     - Save button: calls `PUT /auth/me` with `{ display_name, avatar_url, avatar_color }` (adult context) or `PATCH /family/children/{childId}` (child context, via route props per KTD5)
     - Client-side resize per KTD1: before `uploadImage()`, downscale via canvas to max 512x512
     - Upload feedback: loading toast during upload (save button disabled), error toast on failure (Vant showLoadingToast/showFailToast)
  3. Add BOTH routes (lazy-loaded, existing pattern): `settings/profile` and `settings/family/children/:childId/profile`
  4. Add `updateProfile()` (PUT /auth/me) and `updateChildProfile()` (PATCH /family/children/{childId}) API functions
- **Test scenarios:**
  - Page loads with current user's avatar and display name
  - Tapping avatar opens picker in avatar mode with 3 tabs
  - Uploading an image updates the preview and saves `avatar_url`
  - Selecting a 3D icon updates the preview and saves `avatar_url`
  - Selecting an emoji updates the preview and saves `avatar_url`
  - Editing display name and saving calls `PUT /auth/me` with correct payload
  - Empty display name shows validation error
  - After save, auth store reflects updated `avatar_url` and `display_name`
  - Child context (route `/settings/family/children/:childId/profile`): page loads the child's profile, saves via `PATCH /family/children/{childId}`
  - Upload failure: error toast shown, save button re-enabled, no partial state saved
  - Upload in progress: loading toast visible, save button disabled
- **Verification:** Navigate to `/settings/profile`, perform all three avatar types, verify display name editing.

### U6. Frontend: Adult settings page redesign + Child settings header card

- **Goal:** Replace the flat account info cells on the adult settings page with a centered profile card. Add a new header card to the child settings page.
- **Requirements:** R14, R15, R16
- **Dependencies:** U4, U5
- **Files:**
  - `frontend/apps/main/src/pages/SettingsPage.vue` — redesign first section: replace van-cell-group account info with centered profile card + remaining cells
  - `frontend/apps/child/src/pages/ChildSettingsPage.vue` — add header card at top
  - `frontend/apps/child/src/router/index.ts` - add child-app self-edit route `child-settings/profile` (child edits own avatar/name; 3D icons + emoji only per KTD6)
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` — i18n keys for profile card
  - `frontend/apps/main/src/i18n/locales/en-US.ts` — i18n keys for profile card
- **Approach:**
  1. **Adult SettingsPage.vue:** Replace the first `van-cell-group` (lines 9-34) with:
     - A centered profile card (whole card tappable -> routes to `/settings/profile`): 64px `UserAvatar` component as focal point, `display_name` below, family name with icon as secondary text
     - Below the card: a separate `van-cell-group` with remaining cells (username link, role display, etc.)
     - Card styling: subtle background, 12px border-radius, CSS variables for dark mode
  2. **Child ChildSettingsPage.vue:** Add a centered header card at the top of `settings-body`:
     - `UserAvatar` component showing child's avatar (tappable → child profile edit)
     - Child `display_name` below avatar
     - Login `username` as small secondary text (read-only)
     - Family name with icon
  3. Child profile editing has two contexts (per KTD5/KTD6): parent-managed edit lives in the MAIN app at `/settings/family/children/:childId/profile` (U5 owns this route); child self-edit lives in the CHILD app at `child-settings/profile` and shows only 3D icon + emoji tabs (no gallery/camera - requires adult auth). The child-app edit page calls `PUT /auth/me` (child session) for display_name + avatar_url
- **Patterns to follow:** Existing `van-cell-group inset` card pattern. Centered layout per UI/UX design consultation. Dark mode CSS variables.
- **Test scenarios:**
  - Adult settings: centered profile card shows avatar, display name, family name (Covers AE1)
  - Tapping avatar navigates to `/settings/profile`
  - Below card: username link, role cell still present and functional
  - Child settings: header card shows child avatar, display name, username (read-only), family name (Covers AE4)
  - Dark mode: cards render correctly with CSS variables
  - Existing settings functionality (theme, language, logout) still works
- **Verification:** Visual check on both settings pages. Navigation to profile edit works. Existing settings items unaffected.

### U7. Frontend: Migrate all avatar rendering to UserAvatar component

- **Goal:** Replace all existing `charAt(0)` + `avatar_color` rendering patterns across the app with the unified `UserAvatar` component.
- **Requirements:** R2, R4, R18
- **Dependencies:** U4
- **Files:**
  - `frontend/apps/main/src/components/family/MemberCard.vue` — replace avatar div with `UserAvatar`
  - `frontend/apps/main/src/pages/LoginPage.vue` — replace avatar divs with `UserAvatar` (account list, PIN step)
  - `frontend/apps/main/src/components/dashboard/PendingApprovalsSection.vue` — replace child avatar with `UserAvatar`
  - `frontend/apps/main/src/components/dashboard/LiteracyStatusCard.vue` — replace child avatar with `UserAvatar`
  - `frontend/apps/child/src/` — any child-app avatar rendering points
  - `frontend/apps/main/src/pages/FamilyPage.vue` - member avatar (line 32, `display_name[0]`) + child avatar (line 110)
  - `frontend/apps/main/src/pages/BabyPage.vue` - 3 child avatar instances (lines 27, 398, 442)
  - `frontend/apps/main/src/pages/BabyChoreTemplatesPage.vue` - assignee avatar (line 61)
  - `frontend/apps/main/src/pages/DevicesPage.vue` - device group avatar (line 213)
  - Pre-implementation sweep: `grep -rn 'charAt(0)' frontend/apps/*/src/` and `grep -rn 'display_name[0]' frontend/apps/*/src/` to catch renderers added since planning
- **Approach:**
  1. For each file, replace the inline avatar `<div>` with `<UserAvatar :avatar-url="..." :avatar-color="..." :display-name="..." :size="..." />`
  2. Pass the correct `avatar_url` from the user/child data (new field from U1)
  3. Preserve existing `size` values per component (MemberCard: 36px, LoginPage: varies, etc.)
  4. Remove the now-redundant `.avatar` / `.child-avatar` CSS classes where fully replaced
- **Patterns to follow:** The new `UserAvatar` component from U4.
- **Test scenarios:**
  - MemberCard: shows image/emoji avatar when set, falls back to char+color when not
  - LoginPage: account switcher shows correct avatars for each user
  - PendingApprovals: child avatars render correctly
  - LiteracyStatusCard: child avatars render correctly
  - FamilyPage member + child lists, BabyPage (3 instances), BabyChoreTemplatesPage assignee, DevicesPage groups: all render via UserAvatar
  - All existing tests pass (no visual regressions for users without custom avatars)
- **Verification:** Full app walkthrough — every avatar rendering point shows correct fallback or custom avatar.

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Backend tests | `cd server && pytest tests/backend/ -x` | auth, children, migration |
| Frontend typecheck | `cd frontend && pnpm typecheck` | All apps + packages |
| Frontend unit tests | `cd frontend && pnpm vitest run` | Component + composable tests |
| Icon manifest build | `cd frontend && pnpm build:manifest` | Manifest generation |
| Visual smoke | Manual browser check | Settings pages, avatar rendering |

---

## Definition of Done

- All 7 implementation units pass their test scenarios
- Backend: `pytest` passes for auth and children suites. Alembic migration applies cleanly.
- Frontend: `typecheck` passes with zero errors. `vitest` passes all existing + new tests.
- 3D icon categories recovered and included in manifest. Thumbnails generated.
- UserAvatar component renders correctly in all three modes (fallback, image, emoji) and dark mode.
- Adult settings page shows centered profile card. Child settings page shows header card.
- All existing `charAt(0)` avatar renderers migrated to UserAvatar component (grep sweep returns zero unmigrated renderers).
- Login page account switcher shows custom avatars (LoginStep1Response carries `avatar_url`).
- No regression: asset icon picker unchanged, settings navigation unchanged, username change flow unchanged.
- Abandoned experimental code removed from diff.
