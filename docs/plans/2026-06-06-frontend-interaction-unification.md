---
type: refactor
status: active
origin: docs/superpowers/specs/2026-06-06-frontend-interaction-unification-design.md
created: 2026-06-06
---

# Frontend Interaction Unification

Unify Icon, Toast/Loading, and Splash Screen across `frontend/apps/main` and `frontend/apps/child` to align with vue3-h5-template practices.

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| SvgIcon for existing sprite icons (not IIcon) | 31 custom business SVGs have no Iconify equivalent; local sprite is the right fit |
| IIcon for future Iconify icons | Standard Iconify usage, wraps `@iconify/vue` |
| No full Toast wrapper | Reference template doesn't wrap Vant; 317 existing calls work correctly |
| Loading helper with refcount | Prevents concurrent requests from prematurely closing toast |
| Replace page-level `van-loading` with loading toast | Aligns with Vant4 feedback practice; removes TikTok-style full-page spinner |
| Splash uses `prefers-color-scheme` | Works before JS loads; no dependency on app theme system |

## Implementation Units

### U1: Icon infrastructure — both apps

**Goal:** Install dependencies, create IIcon and SvgIcon components, configure Vite plugin.

**Files:**
- `frontend/apps/main/package.json` — add `@iconify/vue`, `vite-plugin-svg-icons-ng`
- `frontend/apps/main/vite.config.ts` — add `createSvgIconsPlugin` config
- `frontend/apps/main/src/components/IIcon.vue` — new
- `frontend/apps/main/src/components/SvgIcon.vue` — new
- `frontend/apps/main/src/main.ts` — add `import 'virtual:svg-icons-register'`
- `frontend/apps/child/package.json` — add `@iconify/vue`, `vite-plugin-svg-icons-ng`
- `frontend/apps/child/vite.config.ts` — add `createSvgIconsPlugin` config
- `frontend/apps/child/src/components/IIcon.vue` — new
- `frontend/apps/child/src/components/SvgIcon.vue` — new
- `frontend/apps/child/src/main.ts` — add `import 'virtual:svg-icons-register'`
- `frontend/apps/child/src/icons/svg/.gitkeep` — new (empty dir for future use)

**Approach:**
- Reference vue3-h5-template's `src/components/i-icon/index.vue` and `src/components/svg-icon/index.vue` for component structure
- IIcon wraps `@iconify/vue` Icon with typed props (`icon: string | object`, `size?: string | number`, `color?: string`)
- SvgIcon uses `<svg><use :href="#icon-${name}" /></svg>` with `name`, `size`, `color` props
- Vite plugin config: `iconDirs: [path.resolve(__dirname, 'src/icons/svg')]`, `symbolId: 'icon-[name]'`
- Both components registered globally via unplugin-vue-components (already configured) — no manual registration needed

**Test scenarios:**
- `pnpm typecheck` passes with new components
- `pnpm build` succeeds (vite-plugin-svg-icons-ng resolves virtual module)
- IIcon renders an Iconify icon string
- SvgIcon renders a local SVG by name

**Verification:** `cd frontend/apps/main && pnpm typecheck && pnpm build` + same for child

---

### U2: SVG sprite extraction — main only

**Goal:** Extract 31 symbols from index.html sprite sheet to individual SVG files managed by vite-plugin-svg-icons-ng.

**Files:**
- `frontend/apps/main/index.html` — remove `<div id="svg-sprite-sheet">` block
- `frontend/apps/main/src/icons/svg/` — new directory with 31 `.svg` files
- `frontend/apps/main/src/utils/icon.ts` — update `getIconId` to return bare name (strip `icon-` prefix for SvgIcon compatibility)

**Approach:**
- Parse each `<symbol id="icon-xxx">` from index.html
- Extract inner `<path>` / `<circle>` / etc. into standalone SVG files named `xxx.svg` (without `icon-` prefix since plugin prepends it)
- Each SVG: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="..."><path .../></svg>`
- Keep original viewBox from each symbol
- Update `getIconId()` to return name without `icon-` prefix: `getIconId('icon-home')` → `'home'`
- Preserve `currentColor` usage for CSS color inheritance

**Test scenarios:**
- All 31 SVG files created with correct viewBox
- `getIconId` returns correct names
- Build succeeds with sprite generated from new files
- No references to `#svg-sprite-sheet` remain in index.html

**Verification:** `pnpm build` succeeds; grep confirms no sprite sheet in built index.html

**Depends on:** U1

---

### U3: Icon template migration — main only

**Goal:** Update all pages using `<svg><use :href="#icon-xxx">` to use `<SvgIcon name="xxx" />`.

**Files:**
- `frontend/apps/main/src/components/asset/CategoryGrid.vue`
- `frontend/apps/main/src/components/asset/AssetCard.vue`
- `frontend/apps/main/src/components/asset/AssetListItem.vue`
- `frontend/apps/main/src/components/asset/AssetForm.vue`
- `frontend/apps/main/src/components/liability/LiabilityCard.vue`
- `frontend/apps/main/src/components/liability/LiabilityForm.vue`
- `frontend/apps/main/src/components/dashboard/AlertCards.vue`
- `frontend/apps/main/src/pages/AIHubPage.vue`

**Approach:**
- Replace pattern: `<svg class="icon" aria-hidden="true"><use :href="..." /></svg>` → `<SvgIcon :name="getIconId(xxx)" />`
- Preserve existing CSS sizing via SvgIcon's `size` prop or parent CSS
- Remove `.icon` class definitions if no longer needed
- Keep `aria-hidden="true"` behavior (SvgIcon should include this by default)

**Test scenarios:**
- All pages render icons at same visual size as before
- No `<svg class="icon">` patterns remain in migrated files
- `pnpm typecheck` passes
- Icons respect `currentColor` for theming

**Verification:** `pnpm lint && pnpm typecheck && pnpm build`

**Depends on:** U2

---

### U4: Loading helper + dead code cleanup — both apps

**Goal:** Create `src/utils/loading.ts` with refcounted showLoading/hideLoading. Remove dead loading infrastructure.

**Files:**
- `frontend/apps/main/src/utils/loading.ts` — new
- `frontend/apps/main/src/main.ts` — remove `setupLoadingGuards` + `setupLoadingInterceptor` imports and calls
- `frontend/apps/main/src/plugins/loading.ts` — delete
- `frontend/apps/main/src/router/guards/` — delete empty directory
- `frontend/apps/main/src/composables/__tests__/loading.spec.ts` — update or remove if testing dead code
- `frontend/apps/child/src/utils/loading.ts` — new

**Approach:**
- `showLoading(message?)`: increment counter, show toast only on first call
- `hideLoading()`: decrement counter, close toast only when counter reaches 0
- Default message uses i18n: `t('common.loading')` — but since this is a utility (not a component), pass message as param with a fallback string
- Delete `plugins/loading.ts` (confirmed no-op)
- Remove `setupLoadingGuards` import from main.ts (file already deleted, import is dead)
- Remove `setupLoadingInterceptor` import from main.ts
- Check if `composables/__tests__/loading.spec.ts` tests dead code; if so, repurpose for new utility

**Test scenarios:**
- `showLoading()` shows Vant loading toast
- `hideLoading()` after single `showLoading()` closes toast
- Concurrent: two `showLoading()` → one `hideLoading()` → toast stays; second `hideLoading()` → toast closes
- `hideLoading()` without prior `showLoading()` is safe (no-op)
- Build succeeds with dead imports removed

**Verification:** `pnpm lint && pnpm typecheck && pnpm build`

---

### U5: Page loading replacement — main only

**Goal:** Replace 8 pages' `<van-loading class="page-loading" />` with `showLoading()`/`hideLoading()` during data fetch.

**Files:**
- `frontend/apps/main/src/pages/AssetDetailPage.vue`
- `frontend/apps/main/src/pages/WishDetailPage.vue`
- `frontend/apps/main/src/pages/LiabilityDetailPage.vue`
- `frontend/apps/main/src/pages/FamilyPage.vue`
- `frontend/apps/main/src/pages/AssetSellPage.vue`
- `frontend/apps/main/src/pages/BabyChoreTemplatesPage.vue`
- `frontend/apps/main/src/pages/BabyChoreTemplateEditPage.vue`
- `frontend/apps/main/src/pages/BlindBoxConfigPage.vue`
- `frontend/apps/main/src/pages/DashboardPage.vue` — replace existing showLoadingToast/closeToast

**Approach:**
- Each page currently uses `v-if="loading"` + `<van-loading v-else>`. Replace:
  1. Import `showLoading`, `hideLoading` from `@/utils/loading`
  2. In `onMounted`/fetch function: `showLoading()` before fetch, `hideLoading()` in finally block
  3. Remove `<van-loading class="page-loading" />` template and `.page-loading` CSS
  4. Keep the `loading` ref for conditional rendering (show content only when data is ready), but don't show a spinner — the toast handles the visual feedback
- For DashboardPage: replace `showLoadingToast({ message, forbidClick: true, duration: 0 })` / `closeToast()` with `showLoading(message)` / `hideLoading()`
- Preserve the page's content-ready gating (v-if="data") so pages don't flash empty state

**Test scenarios:**
- Pages show Vant loading toast during initial fetch
- Toast disappears when data loads
- No `.page-loading` CSS remains in modified files
- Error paths still call `hideLoading()` (finally block)
- Pages still gate content rendering on data availability

**Verification:** `pnpm lint && pnpm typecheck && pnpm build`

**Depends on:** U4

---

### U6: Splash screen — both apps

**Goal:** Add pure HTML+CSS spinner inside `#app` div in both index.html files. Supports dark mode via `prefers-color-scheme`.

**Files:**
- `frontend/apps/main/index.html` — add spinner inside `#app` div
- `frontend/apps/child/index.html` — add spinner inside `#app` div

**Approach:**
- Main: purple primary (`#7c5cfc` light, `#bdbbff` dark), dark bg `#010120`
- Child: Clay palette (`#0a0a0a` light, `#e8b94a` dark), warm cream bg `#fffaf0`, dark bg `#0a1a1a`
- Use cube-shadow-spinner animation from vue3-h5-template
- Inline `<style>` inside `#app` div — gets replaced when Vue mounts
- CSS class names prefixed with `__` to avoid conflicts
- No JS, no external resources, no image files

**Test scenarios:**
- Opening index.html directly in browser shows spinner (no JS needed)
- Dark mode respected via media query
- After Vue mounts, spinner is gone (replaced by app content)
- No FOUC (flash of unstyled content)
- Existing meta viewport, favicon, title preserved

**Verification:** `pnpm build` succeeds; open built index.html in browser shows spinner

---

## Sequencing

```
U1 (Icon infra) ──→ U2 (Sprite extraction) ──→ U3 (Template migration)
U4 (Loading helper) ──→ U5 (Page loading replacement)
U6 (Splash) — independent
```

Recommended execution order: U1 → U4 → U6 → U2 → U3 → U5

Rationale: U1 and U4 establish infrastructure (can be parallel). U6 is independent and quick. U2/U3 are the largest change set. U5 depends on U4 being stable.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| SVG extraction loses viewBox or path data | Validate each extracted SVG renders identically to original sprite |
| SvgIcon not auto-imported by unplugin-vue-components | Register manually in main.ts if needed; check resolver config |
| Page loading replacement changes UX feel | Loading toast is brief and non-blocking; content gates remain |
| vite-plugin-svg-icons-ng version compatibility | Pin to latest stable; check Vite 5.x compatibility |

## Verification (all units)

```bash
cd frontend/apps/main && pnpm lint && pnpm typecheck && pnpm build
cd frontend/apps/child && pnpm lint && pnpm typecheck && pnpm build
```
