# Frontend Interaction Unification Design

Created: 2026-06-06

## Goal

Unify Icon, Toast/Loading, and Splash Screen implementations across `apps/main` and `apps/child` to align with `yulimchen/vue3-h5-template` practices. Minimum necessary changes — no business logic rewrites.

## Current State

| Area | apps/main | apps/child |
|------|-----------|------------|
| Icon | SVG sprite sheet in index.html (31 symbols) + ~127 inline SVG across 45 files | No icon system (5 decorative SVGs) |
| Toast | Direct Vant calls (317 occurrences / 68 files) | Direct Vant calls (17 / 8 files) |
| Loading helper | Manual showLoadingToast/closeToast in DashboardPage | None |
| Splash | None (white flash) | None (white flash) |

## Design

### 1. Icon System

#### New Dependencies

| Package | Purpose |
|---------|---------|
| `@iconify/vue` | IIcon component runtime |
| `vite-plugin-svg-icons-ng` | Build-time SVG sprite generation for SvgIcon |

#### New Components

**`src/components/IIcon.vue`** (both apps)
- Wraps `@iconify/vue` Icon component
- Props: `icon` (string or IconifyIcon object), `size`, `color`
- Usage: `<IIcon icon="fa6-solid:heart" />`

**`src/components/SvgIcon.vue`** (both apps)
- Uses `<svg><use :href="#icon-${name}" /></svg>` against build-time generated sprite
- Props: `name`, `size`, `color`
- Usage: `<SvgIcon name="home" />`

#### Vite Config

```ts
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons-ng'

createSvgIconsPlugin({
  iconDirs: [path.resolve(__dirname, 'src/icons/svg')],
  symbolId: 'icon-[name]',
})
```

#### Migration (main app)

1. Extract 31 `<symbol>` elements from `index.html` → individual `.svg` files in `src/icons/svg/`
2. Remove `<div id="svg-sprite-sheet">` from `index.html`
3. Add `import 'virtual:svg-icons-register'` to `main.ts`
4. Update templates: `<svg><use :href="#icon-xxx" /></svg>` → `<SvgIcon name="xxx" />`
5. Keep `src/utils/icon.ts` (`getIconId`) — update to return name string for SvgIcon

#### NOT migrated this round

- Inline SVG components (AIBrainIcon, CurrencyIcon, coins, NuminaLogo, etc.)
- Child app has almost no icons — just install deps + add components for future use

### 2. Toast / Loading

#### Approach: Minimal — Loading Helper Only

No full Toast wrapper. Reference template doesn't wrap Vant either. Direct `showToast()` calls remain.

**New file:** `src/utils/loading.ts` (both apps)

```ts
import { showLoadingToast, closeToast } from 'vant'

let loadingCount = 0

export function showLoading(message = '⏳ 加载中...'): void {
  loadingCount++
  if (loadingCount === 1) {
    showLoadingToast({ message, forbidClick: true, duration: 0 })
  }
}

export function hideLoading(): void {
  loadingCount = Math.max(0, loadingCount - 1)
  if (loadingCount === 0) {
    closeToast()
  }
}
```

Reference counting prevents concurrent requests from prematurely closing loading.

#### Migration

- Replace `showLoadingToast({ ..., duration: 0 })` / `closeToast()` pairs → `showLoading()` / `hideLoading()`
- Only 2 existing call sites in DashboardPage
- NOT touching the 317 `showToast()` calls — they work correctly as-is

#### Page-Level Loading Replacement

Current pattern (8 pages use `<van-loading class="page-loading" />`):
```vue
<van-loading v-else class="page-loading" />
```

Replace with Vant loading toast during initial data fetch:
```ts
showLoading()
await fetchData()
hideLoading()
```

Affected pages: AssetDetailPage, WishDetailPage, LiabilityDetailPage, FamilyPage, AssetSellPage, BabyChoreTemplatesPage, BabyChoreTemplateEditPage, BlindBoxConfigPage.

For pages showing detail data (where skeleton makes more sense), keep `<van-skeleton>` — only replace the plain spinner.

#### Dead Code Cleanup

- Remove `setupLoadingGuards` import + call from `main.ts` (file already deleted)
- Remove `setupLoadingInterceptor` import + call from `main.ts`
- Delete `src/plugins/loading.ts` (no-op)
- Delete empty `src/router/guards/` directory

#### Constraints

- Stream/SSE requests: NO loading toast (these are long-running by nature)
- Query-type requests: NO global loading interceptor
- No axios interceptor for global loading — page-level control only

### 3. Splash Screen

#### Approach: Pure HTML+CSS spinner inside `#app`

Vue replaces `#app` innerHTML on mount — spinner disappears automatically.

**apps/main** — uses project's purple primary color:
```html
<div id="app">
  <style>
    html, body, #app { height: 100%; margin: 0; padding: 0; }
    .__spinner-container { height: 100%; display: flex; align-items: center; justify-content: center; }
    .__spinner { width: 68px; height: 68px; background-color: var(--van-primary-color, #7c5cfc);
      animation: cube-shadow-spinner 1.8s cubic-bezier(0.75, 0, 0.5, 1) infinite; }
    @keyframes cube-shadow-spinner {
      50% { border-radius: 50%; transform: scale(0.5) rotate(360deg); }
      100% { transform: scale(1) rotate(720deg); }
    }
    @media (prefers-color-scheme: dark) {
      html, body, #app { background: #010120; }
      .__spinner { background-color: #bdbbff; }
    }
  </style>
  <div class="__spinner-container"><div class="__spinner"></div></div>
</div>
```

**apps/child** — uses Clay warm palette:
```html
<div id="app">
  <style>
    html, body, #app { height: 100%; margin: 0; padding: 0; background: #fffaf0; }
    .__spinner-container { height: 100%; display: flex; align-items: center; justify-content: center; }
    .__spinner { width: 68px; height: 68px; background-color: #0a0a0a;
      animation: cube-shadow-spinner 1.8s cubic-bezier(0.75, 0, 0.5, 1) infinite; }
    @keyframes cube-shadow-spinner {
      50% { border-radius: 50%; transform: scale(0.5) rotate(360deg); }
      100% { transform: scale(1) rotate(720deg); }
    }
    @media (prefers-color-scheme: dark) {
      html, body, #app { background: #0a1a1a; }
      .__spinner { background-color: #e8b94a; }
    }
  </style>
  <div class="__spinner-container"><div class="__spinner"></div></div>
</div>
```

Delete any existing TikTok-style or conflicting splash animation.

## Files to Modify

### apps/main

| File | Action |
|------|--------|
| `package.json` | Add @iconify/vue, vite-plugin-svg-icons-ng |
| `vite.config.ts` | Add createSvgIconsPlugin config |
| `src/main.ts` | Add `import 'virtual:svg-icons-register'` |
| `index.html` | Remove sprite sheet div, add splash spinner |
| `src/components/IIcon.vue` | New — Iconify wrapper |
| `src/components/SvgIcon.vue` | New — local SVG sprite |
| `src/icons/svg/*.svg` | New — 31 extracted SVG files |
| `src/utils/icon.ts` | Update to work with SvgIcon |
| `src/utils/loading.ts` | New — showLoading/hideLoading |
| `src/plugins/loading.ts` | Delete (no-op) |
| `src/router/guards/` | Delete (empty directory) |
| Pages using `<svg><use>` | Update to `<SvgIcon>` |
| `DashboardPage.vue` | Replace loading toast boilerplate |
| 8 pages with `<van-loading class="page-loading">` | Replace with showLoading/hideLoading |

### apps/child

| File | Action |
|------|--------|
| `package.json` | Add @iconify/vue, vite-plugin-svg-icons-ng |
| `vite.config.ts` | Add createSvgIconsPlugin config |
| `src/main.ts` | Add `import 'virtual:svg-icons-register'` |
| `index.html` | Add splash spinner |
| `src/components/IIcon.vue` | New |
| `src/components/SvgIcon.vue` | New |
| `src/icons/svg/` | New (empty dir, ready for future use) |
| `src/utils/loading.ts` | New |

## Scope Boundaries

### IN scope
- IIcon + SvgIcon component creation
- vite-plugin-svg-icons-ng setup
- Sprite sheet extraction → individual SVG files
- Template `<svg><use>` → `<SvgIcon>` migration
- Loading helper utility
- Splash screen for both apps

### OUT of scope
- Inline SVG component migration (AIBrainIcon, CurrencyIcon, coins, etc.)
- Mass showToast() replacement (317 calls stay as-is)
- Axios interceptor for global loading
- Business logic changes
- SSE/stream request loading
- New UI libraries

## Verification

```bash
cd frontend/apps/main && pnpm lint && pnpm typecheck && pnpm build
cd frontend/apps/child && pnpm lint && pnpm typecheck && pnpm build
```
