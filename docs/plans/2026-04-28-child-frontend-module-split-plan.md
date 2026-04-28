---
date: 2026-04-28
topic: child-frontend-module-split
status: active
origin: docs/brainstorms/2026-04-27-child-frontend-module-split-requirements.md
---

# Plan: Child Frontend Module Split

## Problem Frame

The frontend bundles adult and child UX into a single Vite build with a shared router. This plan splits `frontend-child` into a separate Vite app sharing a `packages/auth` workspace package with the adult app, enforced by ESLint boundary rules and Nginx path routing.

(see origin: `docs/brainstorms/2026-04-27-child-frontend-module-split-requirements.md`)

## Architecture

```
numina/
├── frontend/              # Adult app (existing, thin Vite shell)
├── frontend-child/        # Child app (new, thin Vite shell)
├── packages/
│   └── auth/              # Shared: useAuthStore, useChildAuthStore, User/ChildUser types
├── pnpm-workspace.yaml    # Workspace root (new)
└── nginx.conf             # Updated: adds upstream + location /child/
```

**Nginx routing (gateway):**
- `location /child/` → proxy to `frontend-child` container (trailing slash strips prefix)
- `location /` → proxy to `frontend` container (unchanged)

**Auth package boundary:**
- `packages/auth` exports stores + types only; no Vue Router, no Vant
- Both apps declare `pinia` and `vue` as peer deps in `packages/auth` + `resolve.dedupe` in Vite configs to prevent duplicate Pinia instance

## Key Technical Decisions

- **`packages/auth` is source-only** — `package.json` `exports` points at `./src/index.ts`; no build step needed; Vite bundles it inline; `packages/auth/tsconfig.json` is standalone (does NOT extend `frontend/tsconfig.app.json`) to avoid inheriting `@/` path aliases that don't exist in the package
- **`pinia`/`vue` as peerDependencies** in `packages/auth` — prevents duplicate module instance across workspace symlinks
- **`resolve.dedupe: ['vue', 'pinia']`** in both Vite configs — belt-and-suspenders dedup
- **`server.fs.allow: ['../..']`** in both Vite dev configs — allows Vite to serve files through workspace symlinks
- **`base: '/child/'` + `createWebHistory(import.meta.env.BASE_URL)`** in `frontend-child` — single source of truth for sub-path deployment
- **`auth.ts` logout callback pattern** — `logout()` accepts an optional `onLogout?: () => void` callback; app layer passes `() => router.push('/login')`; store stays router-free
- **`auth.ts` toast callback pattern** — `trustDevice()` accepts `onSuccess?: () => void` and `onError?: () => void`; app layer passes toast calls
- **`FamilyPage.vue` cross-SPA navigation** — `router.push('/child/home')` → `window.location.href = '/child/'`
- **Adult router guard child-user redirect** — `next('/child/')` → `window.location.replace('/child/')` (cross-SPA, not Vue Router)
- **`ChildDayDetailPage` duplicated** — `frontend/src/pages/child/ChildDayDetailPage.vue` stays for adult `baby/calendar/day`; a copy goes to `frontend-child/src/pages/ChildDayDetailPage.vue` for child `calendar/day`
- **`no-restricted-imports` baseline** — no new ESLint plugin; uses native flat config rule matching import specifier strings (works correctly with pnpm symlinks)
- **Two Docker containers** — `frontend-child` service mirrors `frontend` service; gateway Nginx proxies by path prefix

## Implementation Units

---

### Unit 1: pnpm Workspace Root Setup

**Goal:** Establish the monorepo workspace structure.

**Files to create/modify:**
- `pnpm-workspace.yaml` (create)
- `package.json` at repo root (create — workspace root, private, no deps)
- `packages/auth/package.json` (create)
- `packages/auth/src/index.ts` (create — barrel export)
- `packages/auth/tsconfig.json` (create)

**Approach:**
- `pnpm-workspace.yaml` declares `frontend`, `frontend-child`, `packages/*`
- Root `package.json`: `{ "name": "numina-monorepo", "private": true, "engines": { "pnpm": ">=9" } }`
- `packages/auth/package.json`: name `@numina/auth`, `"main": "./src/index.ts"`, `"exports": { ".": "./src/index.ts" }`, `pinia` and `vue` as `peerDependencies`, `devDependencies` for local type-checking
- `packages/auth/tsconfig.json`: standalone strict TS config — do NOT extend `frontend/tsconfig.app.json`; include `"compilerOptions": { "strict": true, "moduleResolution": "bundler", "jsx": "preserve" }` and `"types": ["vite/client"]`; no `paths` aliases (the package has no `@/` alias)

**Patterns to follow:**
- `frontend/package.json` for dep versions (vue 3.5, pinia 3, axios 1.13)
- `frontend/tsconfig.app.json` for TS strictness settings

**Test scenarios:**
- `pnpm install` at repo root resolves without errors
- `node_modules/@numina/auth` symlink exists in both `frontend/node_modules` and `frontend-child/node_modules` after install
- `packages/auth/src/index.ts` is importable from a test file without build step

---

### Unit 2: `packages/auth` — Extract Auth Stores and Types

**Goal:** Move `useAuthStore`, `useChildAuthStore`, `User`, `ChildUser` into the shared package. Remove Vue Router and Vant coupling from `useAuthStore`.

**Files to create:**
- `packages/auth/src/stores/auth.ts`
- `packages/auth/src/stores/childAuth.ts`
- `packages/auth/src/types.ts` (User, ChildUser, ChildBindInfo, ChildPinLoginRequest)
- `packages/auth/src/index.ts` (exports all of the above)

**Files to modify:**
- `frontend/src/stores/auth.ts` → delete after extraction
- `frontend/src/stores/childAuth.ts` → delete after extraction
- `frontend/src/main.ts` → update import path to `@numina/auth`
- `frontend/package.json` → add `"@numina/auth": "workspace:*"`
- `frontend/vite.config.ts` → add `resolve.dedupe: ['vue', 'pinia']` and `server.fs.allow: ['../..']`

**Approach for `useAuthStore` surgery (3 touch points):**

1. `logout()` — remove `router.push('/login')`. Add optional callback:
   ```ts
   // packages/auth/src/stores/auth.ts
   async function logout(options?: { onLogout?: () => void }) {
     // ... existing logout logic ...
     options?.onLogout?.()
   }
   ```
   Callers in `frontend` pass `{ onLogout: () => router.push('/login') }`.

2. `trustDevice()` — remove two `showToast()` calls. Add callbacks. **Important:** the existing `finally` block sets `showTrustPrompt.value = false` — this reactive store state must stay in the `finally` block and is NOT replaced by a callback:
   ```ts
   async function trustDevice(options?: { onSuccess?: () => void; onError?: () => void }) {
     try {
       // ... existing trust API call ...
       options?.onSuccess?.()
     } catch {
       options?.onError?.()
     } finally {
       showTrustPrompt.value = false  // must stay — reactive store state
     }
   }
   ```

3. Remove `import router from '@/router'` and `import { showToast } from 'vant'` from the store.

**`logout()` callers in `frontend` that must be updated (3 call sites):**
- `frontend/src/pages/SettingsPage.vue` line ~351: `authStore.logout()` → `authStore.logout({ onLogout: () => router.push('/login') })`
- `frontend/src/pages/DevicesPage.vue` line ~36: `authStore.logout()` → `authStore.logout({ onLogout: () => router.push('/login') })`
- `frontend/src/pages/DevicesPage.vue` line ~50: `authStore.logout()` → `authStore.logout({ onLogout: () => router.push('/login') })`

**`useChildAuthStore` — no surgery needed.** The store already has no router/toast calls. Hard-coded Chinese strings (`'请让爸爸妈妈帮你解锁'`, `'PIN错误，请重试'`) are replaced with exported error code constants that the app layer maps to i18n keys:
```ts
// packages/auth/src/stores/childAuth.ts
loginError.value = 'PIN_ERROR'   // was: 'PIN错误，请重试'
lockMessage.value = 'ACCOUNT_LOCKED'  // was: '请让爸爸妈妈帮你解锁'
```
App layer in `frontend-child` maps these codes to `t('errors.pinError')` etc.

**Type extraction:**
- `User` and `ChildUser` move from `frontend/src/types/index.ts` to `packages/auth/src/types.ts`
- `frontend/src/types/index.ts` re-exports them: `export type { User, ChildUser } from '@numina/auth'` (preserves existing import paths in adult app during transition)

**Patterns to follow:**
- `frontend/src/stores/auth.ts` (existing behavior — preserve exactly, only remove router/toast coupling)
- `frontend/src/stores/childAuth.ts` (existing behavior — preserve exactly)
- `frontend/CLAUDE.md` emoji i18n convention for error codes

**Test scenarios:**
- `useAuthStore` in `frontend` calls `logout({ onLogout: () => router.push('/login') })` — router navigates to `/login`
- `useAuthStore` in `frontend` calls `trustDevice({ onSuccess: () => showToast(...), onError: () => showToast(...) })` — toasts fire
- `useChildAuthStore` `childLogin()` sets `loginError.value = 'PIN_ERROR'` on 401; app layer displays `t('errors.pinError')`
- `useChildAuthStore` `childLogin()` sets `isLocked.value = true` and `lockMessage.value = 'ACCOUNT_LOCKED'` on 423
- `packages/auth` has zero imports from `vue-router` or `vant` (verify with `grep -r "vue-router\|from 'vant'" packages/auth/src`)
- `npm run typecheck` passes in `frontend` after store files are deleted and imports updated

---

### Unit 3: `frontend-child` App Scaffold

**Goal:** Create the child app as a working Vite + Vue 3 shell with its own router, i18n, and Pinia setup.

**Files to create:**
- `frontend-child/package.json`
- `frontend-child/vite.config.ts`
- `frontend-child/tsconfig.json`
- `frontend-child/tsconfig.app.json`
- `frontend-child/index.html`
- `frontend-child/src/main.ts`
- `frontend-child/src/App.vue`
- `frontend-child/src/router/index.ts`
- `frontend-child/src/i18n/index.ts`
- `frontend-child/src/i18n/locales/zh-CN.ts`
- `frontend-child/src/i18n/locales/en-US.ts`
- `frontend-child/eslint.config.js`
- `frontend-child/nginx.conf` (SPA container internal config)
- `frontend-child/Dockerfile`

**Approach:**

`frontend-child/vite.config.ts`:
```ts
base: '/child/',
resolve: { dedupe: ['vue', 'pinia'], alias: { '@': path.resolve(__dirname, 'src') } },
server: { fs: { allow: ['../..'] }, proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
plugins: [vue(), Components({ resolvers: [VantResolver()] })]
```

`frontend-child/src/router/index.ts`:
- `createWebHistory(import.meta.env.BASE_URL)` — resolves to `/child/` in prod, `/child/` in dev
- Routes: `/` → ChildHomePage, `/wishes` → ChildWishesPage, `/tasks` → ChildTasksPage, `/ledger` → ChildLedgerPage, `/treasures` → ChildTreasuresPage, `/blind-box` → ChildBlindBoxPage, `/calendar/day` → ChildDayDetailPage, `/select` → ChildSelectPage (guest), `/auth` → ChildAuthPage (guest), `/bind` → ChildBindPage (guest)
- Router guard: reads `getUser()` from localStorage; if no child session → redirect to `/select`; if child session → allow; guest routes bypass guard

`frontend-child/nginx.conf` (SPA container):
- Copy `frontend/nginx.conf` verbatim — it serves from `/` internally; the gateway strips `/child/` prefix before proxying

`frontend-child/Dockerfile`:
- Copy `frontend/Dockerfile` verbatim — same `node:20-alpine` build + `nginx:alpine` serve pattern; uses `npm ci` + `npm run build`

`frontend-child/eslint.config.js`:
- Copy `frontend/eslint.config.js` structure
- Add `no-restricted-imports` rule blocking imports from `../frontend/src/**` and any `@numina/` package not in the allowed list
- Include ESLint v9 pitfall fixes: explicit `ignores` block first, `globals.browser` in `languageOptions`

**i18n:** `frontend-child` has its own i18n instance with child-specific keys. Error codes from `packages/auth` (`PIN_ERROR`, `ACCOUNT_LOCKED`) are mapped here.

**Patterns to follow:**
- `frontend/vite.config.ts` (proxy, plugins)
- `frontend/src/main.ts` (app setup order: createApp → createPinia → createRouter → i18n → mount)
- `frontend/eslint.config.js` (flat config structure)
- `frontend/Dockerfile` (build pattern)
- `frontend/nginx.conf` (SPA serving)

**Test scenarios:**
- `npm run build` in `frontend-child` succeeds with `base: '/child/'`; built `index.html` references `/child/assets/...`
- `npm run typecheck` passes
- `npm run lint` passes with boundary rules active
- Router guard redirects unauthenticated user from `/` to `/select`
- Router guard allows child session user to access `/tasks`
- Guest routes (`/select`, `/auth`, `/bind`) accessible without session

---

### Unit 4: Migrate Child Pages and Components to `frontend-child`

**Goal:** Move all child-specific source files from `frontend/src/` to `frontend-child/src/`.

**Files to move** (from `frontend/src/` → `frontend-child/src/`):

Pages:
- `pages/child/ChildHomePage.vue` → `frontend-child/src/pages/ChildHomePage.vue`
- `pages/child/ChildTasksPage.vue` → `frontend-child/src/pages/ChildTasksPage.vue`
- `pages/child/ChildTreasuresPage.vue` → `frontend-child/src/pages/ChildTreasuresPage.vue`
- `pages/child/ChildWishesPage.vue` → `frontend-child/src/pages/ChildWishesPage.vue`
- `pages/child/ChildLedgerPage.vue` → `frontend-child/src/pages/ChildLedgerPage.vue`
- `pages/ChildSelectPage.vue` → `frontend-child/src/pages/ChildSelectPage.vue`
- `pages/ChildAuthPage.vue` → `frontend-child/src/pages/ChildAuthPage.vue`
- `pages/ChildBindPage.vue` → `frontend-child/src/pages/ChildBindPage.vue`

Note: `ChildBlindBoxPage.vue` does not exist in the current codebase — remove from router if referenced.

Layouts:
- `layouts/ChildLayout.vue` → `frontend-child/src/layouts/ChildLayout.vue`

Components:
- `components/child/ChildTabBar.vue` → `frontend-child/src/components/ChildTabBar.vue`
- `components/child/MilestoneCelebration.vue` → `frontend-child/src/components/MilestoneCelebration.vue`
- `components/coins/CopperCoin.vue` → `frontend-child/src/components/coins/CopperCoin.vue`
- `components/coins/SilverCoin.vue` → `frontend-child/src/components/coins/SilverCoin.vue`
- `components/coins/GoldenCoin.vue` → `frontend-child/src/components/coins/GoldenCoin.vue`
- `components/coins/CoinDisplay.vue` → `frontend-child/src/components/coins/CoinDisplay.vue`

API modules (copy, not move — child app needs its own axios instance):
- `api/children.ts` → `frontend-child/src/api/children.ts`
- `api/coins.ts` → `frontend-child/src/api/coins.ts` (used by ChildHomePage, ChildLedgerPage, ChildWishesPage)
- `api/chores.ts` → `frontend-child/src/api/chores.ts` (used by ChildHomePage, ChildTasksPage)
- `api/calendar.ts` → `frontend-child/src/api/calendar.ts` (used by ChildHomePage, ChildDayDetailPage)
- `api/childWishes.ts` → `frontend-child/src/api/childWishes.ts` (used by ChildHomePage)
- `api/treasures.ts` → `frontend-child/src/api/treasures.ts` (used by ChildTreasuresPage)
- `api/milestones.ts` → `frontend-child/src/api/milestones.ts` (used by ChildTasksPage)
- `api/webauthn.ts` → `frontend-child/src/api/webauthn.ts` (used by ChildAuthPage)
- `api/index.ts` → `frontend-child/src/api/index.ts` (copy the axios instance setup; update base URL if needed)

All copied API modules: update `import { http } from '@/api/index'` to reference the local `frontend-child/src/api/index.ts` — the `@/` alias resolves correctly since both apps use `@` → `src/`.

Stores (copy, not move — child app needs `useFamilyStore` for coin conversion rates):
- `stores/family.ts` → `frontend-child/src/stores/family.ts` (used by ChildHomePage, ChildLedgerPage for `coinCopperToSilver`, `coinSilverToGold` rates; copy the store, do not import from `frontend`)

**`ChildDayDetailPage` — duplicate, not move:**
- `frontend/src/pages/child/ChildDayDetailPage.vue` stays in place (serves adult `baby/calendar/day` route)
- Copy to `frontend-child/src/pages/ChildDayDetailPage.vue` (serves child `calendar/day` route)

**`ChildLayout.vue` — one navigation fix:**
- The existing `window.location.href = '/'` calls for cross-SPA return are already correct — no change needed
- Verify no `router.push` calls remain after move

**Import path updates after move:**
- All `@/` imports within moved files remain valid (both apps use `@` → `src/` alias)
- `import { useChildAuthStore } from '@/stores/childAuth'` → `import { useChildAuthStore } from '@numina/auth'`
- `import type { ChildUser } from '@/types'` → `import type { ChildUser } from '@numina/auth'`
- `import { childPinLogin, ... } from '@/api/children'` → stays as `@/api/children` (local copy in child app)

**Patterns to follow:**
- `frontend/src/pages/child/` (existing page structure — preserve all template/script/style)
- `frontend/CLAUDE.md` emoji i18n convention

**Test scenarios:**
- `npm run typecheck` passes in `frontend-child` after all pages are moved and imports updated
- `npm run build` succeeds — no unresolved imports
- Each child page renders without console errors (verify in dev server)
- `ChildLayout.vue` `returnToAdult()` navigates to `/` via `window.location.href` (cross-SPA)

---

### Unit 5: Adult App Cleanup

**Goal:** Remove child routes, child components, and child-user redirect logic from `frontend`.

**Files to modify:**
- `frontend/src/router/index.ts`
- `frontend/src/pages/FamilyPage.vue`
- `frontend/package.json` (add `@numina/auth: workspace:*`, already done in Unit 2)

**Files to delete from `frontend/src/`:**
- `pages/child/ChildHomePage.vue`, `ChildTasksPage.vue`, `ChildTreasuresPage.vue`, `ChildWishesPage.vue`, `ChildLedgerPage.vue`, `ChildBlindBoxPage.vue`
- `pages/ChildSelectPage.vue`, `ChildAuthPage.vue`, `ChildBindPage.vue`
- `layouts/ChildLayout.vue`
- `components/child/ChildTabBar.vue`, `MilestoneCelebration.vue`
- `components/coins/CopperCoin.vue`, `SilverCoin.vue`, `GoldenCoin.vue`, `CoinDisplay.vue`
- `stores/auth.ts`, `stores/childAuth.ts` (replaced by `@numina/auth`)

**`frontend/src/router/index.ts` changes:**
1. Remove the entire `/child` route subtree (lines 244–258 in current file)
2. In `router.beforeEach` guard:
   - Remove `const isChild = user?.role === 'child'`
   - Replace `next(isChild ? '/child/' : '/')` → `next('/')`
   - Replace `if (isChild) { ... next('/child/') ... }` block → `window.location.replace('/child/')` then `return` (handles stale child session in localStorage)
   - Remove the `isChildBindRoute` branch (lines 266–272: `to.path.startsWith('/child/bind')` special guest bypass) — after the split, no adult-app route starts with `/child/bind`; Nginx routes `/child/*` to the child container before the adult router runs, so this branch can never fire
3. Keep `BabyDayDetail` route (`baby/calendar/day` → `ChildDayDetailPage`) — this stays in `frontend`

**`frontend/src/pages/FamilyPage.vue` change:**
- Line 338: `router.push('/child/home')` → `window.location.href = '/child/'`

**`tests/e2e/api-contract.spec.ts`:**
- Audit for any child-route assertions; remove or update references to `/child/*` paths that now 404 on the adult app
- Add assertion: `GET /child/` on adult app origin returns 404 (or verify Nginx handles this — if Nginx routes `/child/` to the child container, the adult app never sees it; document this in the test)

**Patterns to follow:**
- `frontend/src/router/index.ts` existing guard structure (preserve adult auth logic exactly)

**Test scenarios:**
- `npm run typecheck` passes after deletions
- `npm run build` succeeds — no dead imports
- Adult router guard: authenticated adult user hits `/` → renders Dashboard
- Adult router guard: unauthenticated user hits `/` → redirects to `/login`
- Adult router guard: stale child session in localStorage → `window.location.replace('/child/')` fires
- `FamilyPage` "切换视角" button → `window.location.href = '/child/'` (full page navigation)
- `baby/calendar/day` route still renders `ChildDayDetailPage` in adult app

---

### Unit 6: ESLint Boundary Rules

**Goal:** Prevent cross-app imports via `no-restricted-imports` in both apps' ESLint configs.

**Files to modify:**
- `frontend/eslint.config.js`
- `frontend-child/eslint.config.js`

**Approach:**

In `frontend/eslint.config.js`, add to the `src/**/*.{ts,vue}` config block:
```js
'no-restricted-imports': ['error', {
  patterns: [{
    group: ['**/frontend-child/src/**'],
    message: 'Cross-app imports are not allowed. Use @numina/* shared packages instead.'
  }]
}]
```

In `frontend-child/eslint.config.js`, add:
```js
'no-restricted-imports': ['error', {
  patterns: [{
    group: ['**/frontend/src/**'],
    message: 'Cross-app imports are not allowed. Use @numina/* shared packages instead.'
  }]
}]
```

Note: `no-restricted-imports` matches the import specifier string as written in source — not the resolved file path. pnpm workspace symlinks do not affect this matching. Relative path patterns (`**/frontend/src/**`) catch any relative import that traverses into the other app's source tree.

**Patterns to follow:**
- `frontend/eslint.config.js` (existing flat config structure — add rule to existing `files` block, don't create a new one)
- ESLint v9 pitfall: `ignores` block must be first array entry (already present in `frontend/eslint.config.js`)

**Test scenarios:**
- `npm run lint` in `frontend` fails when a file imports from `../../frontend-child/src/anything`
- `npm run lint` in `frontend-child` fails when a file imports from `../../frontend/src/anything`
- `npm run lint` in both apps passes with no cross-app imports present
- Imports from `@numina/auth` are not blocked by the rule

---

### Unit 7: Docker and Nginx Updates

**Goal:** Add `frontend-child` container and update Nginx to route `/child/*` to it.

**Files to create:**
- `frontend-child/Dockerfile` (already covered in Unit 3)
- `frontend-child/nginx.conf` (already covered in Unit 3)

**Files to modify:**
- `docker-compose.yml`
- `nginx.conf` (gateway dev config)
- `nginx.production.conf` (gateway production config)

**`docker-compose.yml` changes:**

Add new service after `frontend`:
```yaml
frontend-child:
  build: ./frontend-child
  container_name: numina-frontend-child
  restart: unless-stopped
  depends_on:
    - backend
```

Update `nginx` service `depends_on` to include `frontend-child`.

**`nginx.conf` (dev gateway) changes:**

Add upstream block after existing `frontend` upstream:
```nginx
upstream frontend_child {
    server frontend-child:80;
}
```

Add location block **before** the catch-all `location /` block:
```nginx
location /child/ {
    proxy_pass http://frontend_child/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The trailing slash on `proxy_pass http://frontend_child/` strips the `/child/` prefix before forwarding to the container. The container's nginx serves from `/` internally (Vite builds assets at `/child/assets/...` but the container receives the request with prefix stripped — this means the container receives `/assets/...` which matches its root). This is the correct pattern matching the existing `frontend` container setup.

**`nginx.production.conf` changes:** Apply the same upstream + location block additions as `nginx.conf`.

**Patterns to follow:**
- Existing `upstream frontend` + `location /` blocks in `nginx.conf` (mirror exactly)
- Existing `frontend` service in `docker-compose.yml` (mirror structure)

**Test scenarios:**
- `docker-compose up --build` completes without errors
- `curl http://localhost/child/` returns the child app's `index.html`
- `curl http://localhost/child/assets/index-*.js` returns JS (asset path resolution works)
- `curl http://localhost/` returns the adult app's `index.html`
- `curl http://localhost/child/tasks` returns child app's `index.html` (SPA deep-link fallback)
- Child app's API calls to `/api/` route correctly to the backend (prefix not double-applied)

---

## Sequencing and Dependencies

```
Unit 1 (workspace root)
    └── Unit 2 (packages/auth)
            ├── Unit 3 (frontend-child scaffold)  ←── Unit 7 (Docker/Nginx) depends on Unit 3
            │       └── Unit 4 (migrate child pages)
            │               └── Unit 5 (adult cleanup)
            │                       └── Unit 6 (ESLint boundaries)
            └── (Unit 5 also depends on Unit 2 for store import updates)
```

Units 1 → 2 → 3 → 4 → 5 → 6 must be sequential. Unit 7 depends on Unit 3 (requires `frontend-child/Dockerfile` to exist for `docker-compose up --build`); it can otherwise run in parallel with Units 4–6 once Unit 3 is complete.

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Duplicate Pinia instance (`getActivePinia()` error) | Medium | `peerDependencies` in `packages/auth` + `resolve.dedupe` in both Vite configs |
| Vite dev server can't resolve workspace symlinks | Medium | `server.fs.allow: ['../..']` in both Vite configs |
| Nginx prefix stripping breaks asset paths | Medium | Trailing slash on `proxy_pass` strips `/child/` before forwarding; verify with `curl` after deploy |
| Stale child session in adult app causes blank page | High | Replace `next('/child/')` with `window.location.replace('/child/')` in adult router guard (Unit 5) |
| `FamilyPage` admin switch broken after split | High | `router.push('/child/home')` → `window.location.href = '/child/'` (Unit 5) |
| `ChildDayDetailPage` diverges between apps | Low | Both copies start identical; document in `frontend/CLAUDE.md` that the adult copy is for `baby/calendar/day` only |
| `no-restricted-imports` doesn't catch all cross-app paths | Low | Rule matches specifier strings; relative paths traversing into other app's `src/` are caught; absolute/package imports are not a risk |

## Deferred to Implementation

- Copy child-relevant i18n keys from `frontend/src/i18n/locales/zh-CN.ts` and `en-US.ts` into `frontend-child/src/i18n/locales/` — both apps use separate i18n instances so key names can be identical; the two `ChildDayDetailPage` copies can share the same key names without conflict
- Confirm `no-restricted-imports` path patterns work with pnpm workspace symlinks in the specific ESLint version in use (`eslint@10`) — if relative path patterns don't fire, fall back to package-name patterns
- Determine whether `frontend-child` needs its own `vitest` test setup or inherits from workspace root
- Audit `frontend/src/stores/family.ts` for any adult-only data (asset totals, liability data) that child pages don't need — the copy in `frontend-child` can be trimmed to only the coin conversion rate fields if desired, but a full copy is safe

## Success Criteria

(from origin document)
- `npm run build` in both `frontend` and `frontend-child` succeeds independently
- `npm run lint` in both apps passes with boundary rules active
- `npm run typecheck` in both apps passes
- Child user navigating to `/child/` is served the child app; adult user navigating to `/` is served the adult app
- Requests to `/child/*` on the adult app's router return 404 (Nginx routes them to child container before adult app sees them)
- Developer adding a new child page only touches `frontend-child/` — no changes to `frontend/`
- `tests/e2e/api-contract.spec.ts` passes after child route references are updated
