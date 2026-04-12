---
title: "fix: Resolve P0-P2 UI Accessibility and SEO Issues"
type: fix
status: active
date: 2026-04-11
---

# fix: Resolve P0-P2 UI Accessibility and SEO Issues

## Overview

A Lighthouse audit and manual UI review identified 9 issues across P0–P2 severity in the frontend. This plan addresses all of them in priority order: P0 (critical, blocks screen readers), P1 (meaningful degradation), P2 (SEO and polish). No backend changes are required.

## Problem Frame

The Lighthouse audit surfaced accessibility violations (invalid ARIA attributes, missing roles, contrast failures) and SEO gaps (missing meta description, robots.txt serving HTML). Manual review found additional UX gaps (disabled button with no hint, inconsistent icon rendering in WishListPage). These issues affect screen reader users, search engine indexing, and general usability.

## Requirements Trace

- R1. Favicon loads without 403 error
- R2. No invalid ARIA attributes on any element (aria-selected removed from listitem)
- R3. WishListPage list container has role="list" and items have role="listitem"
- R4. All interactive text meets WCAG AA contrast ratio (≥4.5:1)
- R5. Bottom nav add button has an accessible label
- R6. Category icons render consistently in WishListPage (same pattern as AssetCard)
- R7. Disabled "Save Config" button has visible hint explaining why it is disabled
- R8. index.html has a meta description tag
- R9. /robots.txt returns valid robots.txt content, not HTML

## Scope Boundaries

- No backend changes
- No new third-party packages or build plugins (adding small internal utility modules such as `frontend/src/utils/icon.ts` is allowed)
- No dark-mode-specific contrast overrides (existing dark mode patterns are not broken)
- No changes to AssetListPage role="list" (already present per research)
- No Open Graph / Twitter Card tags (out of scope for this fix)
- No performance or PWA work

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/asset/AssetCard.vue:10–13` — `role="listitem"` + `:aria-selected="selected"` (invalid combination; aria-selected only valid on option/row/tab/treeitem)
- `frontend/src/pages/WishListPage.vue:33` — icon rendered as raw text interpolation `{{ wish.category.icon }}` instead of SVG sprite
- `frontend/src/components/common/AppTabBar.vue:5–12` — add button `van-tabbar-item` has empty `<span></span>` label, no aria-label
- `frontend/src/pages/AIConfigPage.vue:33–40` — `<van-button :disabled="!canSave">` with no hint; existing `.tip` div pattern (lines 68–71) uses `van-icon name="info-o"` + span
- `frontend/index.html` — only charset + viewport meta; no description tag
- `frontend/public/` — no robots.txt file; nginx try_files falls through to index.html
- `frontend/nginx.conf` — single `location /` with `try_files $uri $uri/ /index.html`; no explicit static asset location block
- `frontend/src/pages/AssetListPage.vue:313` — `.selection-bar` uses `background: var(--van-primary-color)` (#1989fa) with `color: #fff` (~2.9:1 contrast ratio)
- `frontend/src/components/common/AppTabBar.vue:63` — `.add-btn` uses `background: #1989fa` with `color: #fff` (same contrast issue)
- SVG sprite pattern in AssetCard: `<svg class="icon-svg" aria-hidden="true"><use :href="\`#${getIconId(asset.category?.icon)}\`" /></svg>`

### Institutional Learnings

- No relevant docs/solutions/ entries for ARIA or nginx static file issues

## Key Technical Decisions

- **favicon fix via nginx explicit location, not file permissions**: The frontend nginx `try_files` rule already handles static files correctly for most assets. The 403 is most likely caused by missing explicit cache/MIME handling for image types. Adding a `location ~* \.(png|svg|ico)$` block with `expires` and no `try_files` fallback is the minimal, targeted fix. Alternatively, verifying Docker build file permissions is a fallback.
- **Remove aria-selected from listitem, do not change to role="option"**: The asset list is not a selection widget in the ARIA sense (it's a navigational list). Removing the invalid attribute is correct. The visual selection state (checkbox + CSS class) is sufficient for AT users in selection mode.
- **WishListPage icon: reuse getIconId() composable, not inline emoji**: AssetCard already has the correct pattern. WishListPage should import and use the same `getIconId()` helper to ensure consistent rendering across both emoji and `icon-*` sprite IDs.
- **Contrast fix: darken selection-bar background, not change text color**: White text is the correct choice for dark backgrounds. The fix is to use a darker blue (e.g. `#0d6efd` or `#1565c0`, both ≥4.5:1 with white) for the selection-bar and add-btn backgrounds, not to change text to dark.
- **robots.txt as static file in public/**: The current HTML response for `/robots.txt` happens because the file does not exist — nginx's `try_files` falls through to `index.html`. Once `frontend/public/robots.txt` is created, Vite copies it verbatim to `dist/` and the existing `try_files $uri` rule serves it directly. No nginx config change is needed.
- **meta description as static tag in index.html**: No SEO plugin needed for a self-hosted private app. A single static `<meta name="description">` tag is sufficient.

## Open Questions

### Resolved During Planning

- **Is AssetListPage role="list" already present?** Yes — research confirmed `role="list" aria-label="资产卡片列表"` is already on the container. No fix needed there.
- **Does robots.txt need nginx config?** No — placing it in `frontend/public/` is sufficient; Vite copies it to `dist/` and nginx serves it via `try_files $uri`.
- **Should favicon fix be nginx or Dockerfile?** Nginx explicit location block is preferred — it's visible, testable, and doesn't require rebuilding the image to verify.

### Deferred to Implementation

- **Exact contrast-safe blue value**: Implementer should verify the chosen hex against a contrast checker (e.g. WebAIM) to confirm ≥4.5:1 with #ffffff before committing.
- **getIconId extraction**: `getIconId` is a local function defined inline in `AssetCard.vue` (not exported from any composable). Unit P1-C must extract it to `frontend/src/utils/icon.ts`, export it, and update both `AssetCard.vue` and `WishListPage.vue` to import from there.
- **Favicon 403 root cause confirmation**: If the nginx location block fix does not resolve the 403, the implementer should check Docker image file permissions (`ls -la` inside the container) as a fallback.

## Implementation Units

All units are independent — none depends on another. P0, P1, and P2 units can be implemented in any order or in parallel. The priority labels (P0/P1/P2) indicate severity, not sequencing.

---

- [ ] **Unit P0-A: Fix favicon 403 via nginx explicit static asset location**

**Goal:** `/favicon.png` returns 200 with correct MIME type instead of 403.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `frontend/nginx.conf`

**Approach:**
- Add a `location ~* \.(png|svg|ico|webp)$` block before the catch-all `location /` block
- Add `expires 30d;` and a separate `add_header Cache-Control "public, immutable";` directive (nginx `expires` sets max-age but does not add the `immutable` directive — both lines are required)
- Do not add a `try_files` fallback in this block — let nginx serve the file directly from `root /usr/share/nginx/html`
- This ensures image requests are handled before the SPA fallback rule

**Patterns to follow:**
- Existing `gzip_types` in `frontend/nginx.conf` for the list of static types to handle

**Test scenarios:**
- Happy path: `curl -I http://localhost/favicon.png` returns `200 OK` with `Content-Type: image/png`
- Happy path: browser tab shows favicon after hard refresh
- Edge case: `/nonexistent.png` returns 404, not 200 with HTML body

**Verification:**
- `curl -I http://localhost/favicon.png` returns HTTP 200
- No 403 errors in browser DevTools Network tab for favicon

---

- [ ] **Unit P0-B: Remove invalid aria-selected from AssetCard listitem**

**Goal:** `role="listitem"` elements no longer carry `aria-selected`, eliminating the ARIA validity violation.

**Requirements:** R2

**Dependencies:** None

**Files:**
- Modify: `frontend/src/components/asset/AssetCard.vue`
- Test: `frontend/src/components/asset/AssetCard.vue` (visual regression via screenshot)

**Approach:**
- Remove the `:aria-selected="selected"` binding from the root `<div>` element (line 12)
- The `role="listitem"` and `aria-label` bindings remain unchanged
- Selection state is already communicated via the `van-checkbox` inside `.selection-overlay` (which has `aria-hidden="true"` — this is fine since the checkbox is decorative; the listitem's aria-label conveys the asset identity)
- If selection state needs to be programmatically queryable by AT, add `aria-checked` to the listitem instead — but only if the selection mode is confirmed to behave like a multi-select list. Defer this decision to implementation.

**Patterns to follow:**
- `frontend/src/pages/AssetListPage.vue` — existing `role="list"` container pattern

**Test scenarios:**
- Happy path: rendered AssetCard DOM has no `aria-selected` attribute in normal mode
- Happy path: rendered AssetCard DOM has no `aria-selected` attribute in selection mode
- Edge case: screen reader announces asset name and value from aria-label without mentioning selection state (manual AT test)

**Verification:**
- Browser DevTools Elements panel shows no `aria-selected` on `.asset-card` elements
- Lighthouse accessibility score does not flag aria-selected violation

---

- [ ] **Unit P0-C: Add role="list" and role="listitem" to WishListPage**

**Goal:** WishListPage list container and items have correct ARIA list semantics.

**Requirements:** R3

**Dependencies:** None

**Files:**
- Modify: `frontend/src/pages/WishListPage.vue`

**Approach:**
- Add `role="list"` to the `<div class="list-content">` container
- Add `role="listitem"` to each `<div class="wish-card">` element
- Add `aria-label` to the list container: `aria-label="心愿清单"`

**Patterns to follow:**
- `frontend/src/pages/AssetListPage.vue` — `role="list" aria-label="资产卡片列表"` on the container div

**Test scenarios:**
- Happy path: DOM has `role="list"` on `.list-content` and `role="listitem"` on each `.wish-card`
- Happy path: screen reader announces "心愿清单, list, N items" when navigating to the list

**Verification:**
- Lighthouse accessibility audit passes list semantics check for WishListPage
- DevTools Elements panel confirms roles are present

---

- [ ] **Unit P1-A: Fix color contrast on selection-bar and add-btn**

**Goal:** Interactive elements using #1989fa background with white text meet WCAG AA contrast ratio (≥4.5:1).

**Requirements:** R4

**Dependencies:** None

**Files:**
- Modify: `frontend/src/pages/AssetListPage.vue`
- Modify: `frontend/src/components/common/AppTabBar.vue`

**Approach:**
- In `AssetListPage.vue`, change `.selection-bar` background from `var(--van-primary-color)` to a darker blue that achieves ≥4.5:1 with white (e.g. `#1565c0` or `#0d6efd` — implementer to verify exact value)
- In `AppTabBar.vue`, change `.add-btn` background from `#1989fa` to the same darker blue
- Do not change `color: #fff` — white text on dark blue is the correct pattern
- Do not introduce a new CSS variable unless the same value is used in 3+ places

**Patterns to follow:**
- Existing `[data-theme='dark']` override pattern in `AssetCard.vue` lines 175, 189, 279 — follow the same scoping approach if dark mode needs a separate override

**Test scenarios:**
- Happy path: WebAIM contrast checker confirms chosen blue + white ≥4.5:1
- Happy path: selection bar is visually distinguishable from the page background
- Edge case: dark mode — verify the override does not break dark mode appearance

**Verification:**
- Lighthouse accessibility audit reports no contrast failures for these elements
- Visual inspection confirms the selection bar and add button remain clearly blue

---

- [ ] **Unit P1-B: Add aria-label to AppTabBar add button**

**Goal:** The bottom navigation add button has an accessible name for screen readers.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Modify: `frontend/src/components/common/AppTabBar.vue`

**Approach:**
- Add `aria-label="添加资产"` to the `van-tabbar-item` element that contains the add button
- Alternatively, add it to the inner `<div class="add-btn">` if `van-tabbar-item` does not pass through aria attributes — implementer to verify Vant 4 behavior

**Patterns to follow:**
- Other `van-tabbar-item` elements in the same file that use text labels

**Test scenarios:**
- Happy path: screen reader announces "添加资产" when focus lands on the add button
- Happy path: `aria-label` attribute is present in rendered DOM

**Verification:**
- DevTools accessibility tree shows "添加资产" as the accessible name for the add button element

---

- [ ] **Unit P1-C: Fix category icon rendering in WishListPage**

**Goal:** Category icons in WishListPage render using the same SVG sprite pattern as AssetCard, not raw text interpolation.

**Requirements:** R6

**Dependencies:** None

**Files:**
- Create: `frontend/src/utils/icon.ts` (extract `getIconId` from AssetCard)
- Modify: `frontend/src/components/asset/AssetCard.vue` (import from utils/icon.ts)
- Modify: `frontend/src/pages/WishListPage.vue`

**Approach:**
- Extract `getIconId()` from `AssetCard.vue` to `frontend/src/utils/icon.ts` and export it; update `AssetCard.vue` to import from there
- In `WishListPage.vue`, import `getIconId` from `frontend/src/utils/icon.ts`
- Replace `{{ wish.category.icon }} {{ wish.category.name }}` with the full SVG sprite block: a colored `<div class="card-icon">` containing `<svg class="icon-svg" aria-hidden="true"><use :href="..."/></svg>`, followed by `{{ wish.category.name }}`
- Apply `wish.category?.color` as the icon background (same as AssetCard's `:style="{ background: asset.category?.color || '#1989fa' }"`)

**Patterns to follow:**
- `frontend/src/components/asset/AssetCard.vue:27–31` — SVG sprite + getIconId pattern

**Test scenarios:**
- Happy path: wish card with `icon-*` category shows SVG icon, not raw "icon-house" text
- Happy path: wish card with emoji category (e.g. "🚗") shows emoji correctly
- Edge case: wish with null category renders gracefully (no crash, fallback icon or empty)

**Verification:**
- WishListPage renders category icons visually consistent with AssetListPage
- No raw `icon-*` strings visible in the UI

---

- [ ] **Unit P1-D: Add hint text for disabled Save Config button**

**Goal:** When the "Save Config" button is disabled, a visible hint explains why.

**Requirements:** R7

**Dependencies:** None

**Files:**
- Modify: `frontend/src/pages/AIConfigPage.vue`

**Approach:**
- Add a conditional `<div class="tip" id="save-config-hint">` below the save button, shown when `!canSave`
- Content: `<van-icon name="info-o" /> <span>请选择 AI 提供商并填写 API Key</span>`
- Add `aria-describedby="save-config-hint"` to the `van-button` element so screen readers announce the hint when focus lands on the disabled button
- Use the existing `.tip` CSS class already defined in the file (lines 68–71 pattern)
- No tooltip library needed — inline hint text is sufficient

**Patterns to follow:**
- `frontend/src/pages/AIConfigPage.vue:68–71` — existing `.tip` div with `van-icon name="info-o"`

**Test scenarios:**
- Happy path: hint text is visible when provider is unselected and API key is empty
- Happy path: hint text disappears when both provider and API key are filled
- Edge case: hint text is visible when only one of the two fields is filled (canSave is still false)

**Verification:**
- Disabled state shows hint text below the button
- Filled state hides hint text

---

- [ ] **Unit P2-A: Add meta description to index.html**

**Goal:** `/` returns an HTML page with a `<meta name="description">` tag.

**Requirements:** R8

**Dependencies:** None

**Files:**
- Modify: `frontend/index.html`

**Approach:**
- Add `<meta name="description" content="Numina — 家庭资产可视化管理系统，私有部署，安全追踪家庭资产与负债">` in the `<head>` section after the viewport meta tag
- Keep it concise and in Chinese to match the app's language

**Test scenarios:**
- Happy path: `curl http://localhost/ | grep 'meta name="description"'` returns the tag
- Happy path: browser DevTools shows description in page source

**Verification:**
- Lighthouse SEO audit passes meta description check

---

- [ ] **Unit P2-B: Create robots.txt in public/**

**Goal:** `/robots.txt` returns valid robots.txt content with `text/plain` MIME type.

**Requirements:** R9

**Dependencies:** None

**Files:**
- Create: `frontend/public/robots.txt`

**Approach:**
- Create `frontend/public/robots.txt` with content:
  ```
  User-agent: *
  Disallow: /api/
  ```
- This disallows crawling of the API but allows the SPA itself (appropriate for a self-hosted private app)
- Vite copies `public/` verbatim to `dist/` — no nginx or build config changes needed

**Test scenarios:**
- Happy path: `curl http://localhost/robots.txt` returns `User-agent: *` with `Content-Type: text/plain`
- Happy path: response is not HTML (no `<!DOCTYPE html>` in body)

**Verification:**
- `curl -I http://localhost/robots.txt` returns `Content-Type: text/plain`
- Lighthouse SEO audit passes robots.txt check

---

## System-Wide Impact

- **Interaction graph:** All changes are isolated to frontend static files and Vue components. No callbacks, middleware, or backend routes are affected.
- **Error propagation:** N/A — no async operations introduced.
- **State lifecycle risks:** None — no state management changes.
- **API surface parity:** None — no API changes.
- **Integration coverage:** The nginx location block change (P0-A) affects all static asset requests. Verify that JS/CSS bundles still load correctly after the change.
- **Unchanged invariants:** Backend API, authentication flow, all data operations, and existing Vant component behavior are unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Nginx location block order breaks JS/CSS serving | Test with `curl` for a known JS bundle path after the change; the new block only matches image/icon types |
| Darker blue for contrast breaks brand consistency | Choose a blue in the same hue family as #1989fa (e.g. #1565c0); verify visually before committing |
| getIconId is a local function in AssetCard (not exported) | Extract to `frontend/src/utils/icon.ts` as part of P1-C; update AssetCard import |
| Docker rebuild required for nginx change | Yes — `docker-compose up -d --build` needed after `frontend/nginx.conf` change |

## Documentation / Operational Notes

- After implementing P0-A, rebuild the frontend Docker image: `docker-compose up -d --build`
- All other units (P0-B through P2-B) take effect after `npm run build` + container restart
- Run `npm run build` from `frontend/` after all changes to verify TypeScript types pass
- Lighthouse audit should be re-run after all units are complete to confirm score improvement

## Sources & References

- Related code: `frontend/src/components/asset/AssetCard.vue`
- Related code: `frontend/src/pages/WishListPage.vue`
- Related code: `frontend/src/components/common/AppTabBar.vue`
- Related code: `frontend/src/pages/AIConfigPage.vue`
- Related code: `frontend/nginx.conf`
- Related code: `frontend/index.html`
- WCAG AA contrast requirement: 4.5:1 for normal text
- ARIA spec: aria-selected is only valid on option, row, gridcell, tab, treeitem, columnheader, rowheader
