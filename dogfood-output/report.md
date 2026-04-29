# Numina Dogfood Test Report

**Date:** 2026-04-28  
**Branch:** feat/child-frontend-module-split  
**Tester:** Kiro (automated browser testing via Chrome DevTools MCP)

---

## Summary

| Service | Status | Notes |
|---------|--------|-------|
| Adult Frontend (`http://localhost/`) | ✅ Pass | Loads, data renders, no JS errors |
| Child Frontend (`http://localhost/child/`) | ✅ Pass (after fixes) | Renders after 2 bug fixes |
| Backend API | ✅ Healthy | Auth refresh, data APIs all 200 |
| Nginx routing | ✅ Pass (after fix) | `/child/` proxy_pass corrected |
| Agent | ⚠️ Restarting | Pre-existing langgraph incompatibility, unrelated to this branch |

---

## Adult Frontend (`http://localhost/`)

### Dashboard (/)
- **Status:** ✅ Pass
- **Data loaded:** 总资产 ¥3086.89万, 净资产 ¥1539.39万, 31 assets
- **Console errors:** None (401s on initial load are expected — auth refresh resolves them)
- **API calls:** `/api/v1/auth/refresh` → 200, all data APIs → 200 after refresh

### Family Page (/family)
- **Status:** ✅ Pass
- **Data loaded:** Family name, members, 2 children (小宝, 大宝) with balances and stats
- **Console errors:** None
- **Navigation:** Tab bar (总览/心愿/AI/负债/宝贝/设置) renders correctly

### Cross-SPA Navigation
- Adult router correctly redirects child-role users to `/child/` via `window.location.replace`
- `/child` catch-all route in adult router redirects to child SPA

---

## Child Frontend (`http://localhost/child/`)

### Issues Found & Fixed

#### 1. nginx proxy_pass prefix not stripped (FIXED)
- **Symptom:** All `/child/assets/*.js` returned 404
- **Root cause:** `proxy_pass http://frontend-child/child/` preserved the `/child/` prefix, but container serves assets at `/assets/` (root level)
- **Fix:** Changed to `proxy_pass http://frontend-child/` to strip prefix
- **Commit:** `a8e486e`

#### 2. `display_name.charAt(0)` crash on null data (FIXED)
- **Symptom:** `TypeError: Cannot read properties of undefined (reading 'charAt')` — blank page on ChildSelectPage and ChildAuthPage
- **Root cause:** Test data has children with `null` display_name; template called `.charAt(0)` directly
- **Fix:** Added `?? '?'` guard in both pages
- **Commit:** `a8e486e`

### ChildSelectPage (/child/select)
- **Status:** ✅ Pass (after fixes)
- **Data loaded:** 3 children listed (display_name null in test data → shows `?` avatar)
- **API call:** `GET /api/v1/family/children` → 200
- **Console errors:** None after fix

### ChildAuthPage (/child/auth)
- **Status:** ✅ Pass (after fixes)
- **UI:** Emoji PIN grid (12 emojis), delete/clear buttons, WebAuthn button rendered
- **Navigation:** Clicking child card → navigates to `/child/auth` correctly
- **Console errors:** None after fix (422 on empty PIN submit is expected)

### Child SPA Independence
- ✅ Separate Vite bundle at `/child/assets/`
- ✅ Own router with `/select`, `/auth`, `/bind` guest routes
- ✅ Authenticated routes under `ChildLayout`
- ✅ No cross-imports from adult frontend (ESLint boundary enforced)
- ✅ `@numina/auth` shared package resolves correctly

---

## Infrastructure

### Docker Build
- Both `frontend` and `frontend-child` build successfully from monorepo root context
- `packages/auth` devDependencies installed separately for `vue-tsc` type resolution
- `workspace:*` protocol replaced with `file:` path at build time

### Nginx Routing
- `location /` → `http://frontend/` ✅
- `location /child/` → `http://frontend-child/` ✅ (fixed from `/child/child/`)

---

## Screenshots

- `01-adult-home.png` — Adult dashboard
- `02-child-select.png` — Child select page
- `03-child-auth.png` — Child auth (emoji PIN) page
- `04-adult-dashboard.png` — Adult family page

---

## Remaining Known Issues (Pre-existing, Not This Branch)

1. **numina-agent restarting** — `ImportError: cannot import name 'ExecutionInfo' from 'langgraph.runtime'` — langgraph version incompatibility in agent service
2. **frontend TypeScript errors** — `ImportReportPage.vue`, `WhatIfSimulator.vue`, `DashboardPage.vue` have pre-existing type errors that prevent `vue-tsc -b` from passing (Docker build uses `npx vite build` to bypass)
