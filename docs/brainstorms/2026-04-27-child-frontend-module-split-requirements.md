---
date: 2026-04-27
topic: child-frontend-module-split
---

# Child Frontend Module Split

## Problem Frame

The frontend currently bundles adult and child UX into a single Vite build with a shared router. As child UX diverges (gamified coin system, milestone celebrations, PIN auth), this creates compounding DX pain: no module boundary enforcement, child code bundled with adult code, a single router guard that mixes two auth flows, and no independent deployability for child changes. The goal is to split `frontend-child` into a separate Vite app that shares auth stores and types with the adult app, while keeping both apps in the same monorepo.

## Architecture Overview

```
numina/
├── frontend/           # Adult app (existing)
├── frontend-child/     # Child app (new)
├── packages/
│   └── auth/           # Shared: useAuthStore, useChildAuthStore, User/ChildUser types
└── pnpm-workspace.yaml # Workspace root
```

Both apps are thin Vite shells. A new `frontend-child` Docker container is added alongside the existing `frontend` container. Nginx proxies `/child/*` to `frontend-child` and everything else to `frontend`. ESLint `no-restricted-imports` rules prevent cross-app imports.

## Requirements

**Workspace Setup**
- R1. A `pnpm-workspace.yaml` is added at the repo root declaring `frontend`, `frontend-child`, and `packages/*` as workspace members.
- R2. `frontend-child/` is created as a new pnpm workspace package with its own `package.json`, `vite.config.ts`, `tsconfig.json`, and `src/` tree.
- R3. `frontend-child`'s Vite config sets `base: '/child/'` and its dev server proxies to the backend API matching the pattern in `frontend/vite.config.ts`.
- R4. `frontend-child`'s Vue Router uses `createWebHistory('/child/')` so asset paths resolve correctly when served under the `/child/` prefix.
- R5. The existing `frontend/` package references `packages/auth` via `workspace:*` in its `package.json`.
- R6. A new `frontend-child` Docker service is added to `docker-compose.yml` mirroring the existing `frontend` service structure; both are built as part of `docker-compose up --build`.

**Shared Auth Package (`packages/auth`)**
- R7. `packages/auth` is created as a pnpm workspace package exporting `useAuthStore`, `useChildAuthStore`, and the `User` / `ChildUser` TypeScript types.
- R8. `packages/auth` has no dependency on Vue Router — router navigation (e.g., post-logout redirect to `/login`) is removed from the store and handled by the app layer instead.
- R9. `packages/auth` has no dependency on Vant — toast calls (`showToast`) are removed from the stores; the app layer is responsible for displaying auth error feedback.
- R10. Hard-coded Chinese strings in `useChildAuthStore` (`'请让爸爸妈妈帮你解锁'`, `'PIN错误，请重试'`) are replaced with i18n keys following the emoji-prefixed convention from `frontend/CLAUDE.md` during extraction.
- R11. Both `frontend` and `frontend-child` import auth stores and `User`/`ChildUser` types exclusively from `packages/auth`; the original store files in `frontend/src/stores/auth.ts` and `frontend/src/stores/childAuth.ts` are deleted.
- R12. `packages/auth` has no dependency on any app-specific store or composable — it is a pure Pinia + axios package.

**Child App (`frontend-child`)**
- R13. `frontend-child` contains the child-specific pages (ChildHomePage, ChildTasksPage, ChildTreasuresPage, ChildWishesPage, ChildLedgerPage, ChildBlindBoxPage), layouts (ChildLayout), components (ChildTabBar, MilestoneCelebration, coin system), and child auth pages (ChildSelectPage, ChildAuthPage, ChildBindPage).
- R14. `ChildDayDetailPage` is duplicated: the copy in `frontend/src/pages/child/` serves the adult `baby/calendar/day` route; a separate copy in `frontend-child/src/pages/` serves the child `calendar/day` route. No cross-app import.
- R15. `frontend-child` has its own Vue Router instance covering only the child route surface: `/` (home), `/wishes`, `/tasks`, `/ledger`, `/treasures`, `/blind-box`, `/calendar/day`, `/select`, `/auth`, `/bind`.
- R16. `frontend-child`'s router guard enforces child session auth using `useChildAuthStore` from `packages/auth`; it has no knowledge of adult JWT auth.
- R17. `frontend-child` uses the same Vant 4 component auto-import pattern as `frontend` (via `unplugin-vue-components` + `VantResolver`).
- R18. `frontend-child` follows all conventions from the root `CLAUDE.md`: Chinese UI text, emoji-prefixed toast messages via i18n, `<script setup lang="ts">` only, no `as any`.

**Adult App (`frontend`) Cleanup**
- R19. All child-specific pages (except `ChildDayDetailPage`, per R14), components, and stores are removed from `frontend/src/` after being moved to `frontend-child`.
- R20. The `/child/*` route subtree is removed from `frontend/src/router/index.ts`; the router guard no longer contains `role === 'child'` logic.
- R21. `frontend/src/router/index.ts` no longer redirects child users — that concern moves to Nginx and the child app's own router.
- R22. `tests/lib/routes.ts` and `tests/e2e/auth-guards.spec.ts` are updated to remove child route classifications; a new success criterion verifies that `/child/*` paths return 404 on the adult app (see Success Criteria).

**ESLint Boundary Rules**
- R23. Both `frontend` and `frontend-child` add `no-restricted-imports` rules to their ESLint flat configs forbidding imports from the other app's `src/` directory.
- R24. If `eslint-plugin-boundaries` is evaluated and found compatible with ESLint v9 flat config, it may replace `no-restricted-imports` — but `no-restricted-imports` is the baseline and must work regardless.
- R25. Both apps' `npm run lint` commands enforce boundary rules; CI fails on violations.

**Nginx Routing**
- R26. The Nginx config is updated so requests to `/child/*` are proxied to the `frontend-child` container (same proxy pattern as the existing `frontend` container).
- R27. Requests to all other paths continue to be proxied to the `frontend` container.
- R28. The Nginx routing change is the sole enforcement mechanism for path-based app separation at the infrastructure level.

## Success Criteria

- `npm run build` in both `frontend` and `frontend-child` succeeds independently with no cross-app import errors.
- `npm run lint` in both apps passes with boundary rules active.
- `npm run typecheck` in both apps passes.
- A child user navigating to `/child/` is served the child app; an adult user navigating to `/` is served the adult app.
- Requests to `/child/*` on the adult app's origin return 404 (not a redirect to the child app).
- A developer adding a new child page only touches `frontend-child/` — no changes to `frontend/`.
- The existing `tests/e2e/auth-guards.spec.ts` passes after route classification is updated.

## Scope Boundaries

- **Not in scope:** Turborepo or any build orchestration beyond pnpm workspaces.
- **Not in scope:** `packages/api-types` as a separate package — domain types beyond `User`/`ChildUser` stay co-located in each app's `src/types/`; only auth-related types move to `packages/auth`.
- **Not in scope:** PWA / service worker for `frontend-child`.
- **Not in scope:** Scoped capability tokens or server-side PIN session (auth hardening — separate initiative).
- **Not in scope:** Shared UI component library (`packages/ui-shared`) — extract only when a component is genuinely needed by both apps.
- **Not in scope:** Changes to backend API, FastAPI routers, or database schema.

## Key Decisions

- **pnpm workspaces, not Turborepo:** Right ceiling for a small self-hosted project.
- **`packages/auth` contains stores + types only, not API call functions:** API call functions stay co-located in each app's `api/` folder. Smaller shared surface, easier to version.
- **No `packages/api-types`:** Only `User`/`ChildUser` types are shared (via `packages/auth`). Other domain types stay app-local until a second app genuinely needs them.
- **Router navigation removed from auth stores:** `packages/auth` must be Vue Router-free. Post-auth redirects are the app layer's responsibility.
- **Vant toast calls removed from auth stores:** `packages/auth` must be Vant-free. Auth error display is the app layer's responsibility.
- **`ChildDayDetailPage` duplicated, not shared:** Avoids a cross-app import that would violate boundary rules. The two copies serve different contexts (adult baby calendar vs. child calendar).
- **`frontend-child` base path is `/child/`:** Required for correct asset resolution when served under the `/child/` Nginx prefix.
- **`no-restricted-imports` as the ESLint boundary baseline:** Avoids a new dev dependency with uncertain ESLint v9 flat config compatibility.
- **Two Docker containers, Nginx proxy pattern:** Matches the existing `frontend` container topology; no switch to static file serving needed.

## Dependencies / Assumptions

- The repo uses pnpm as the package manager.
- Docker Compose + Nginx is the deployment target; the planner should locate the exact `nginx.conf` path and current `location` block structure.
- `tests/lib/routes.ts` and `tests/e2e/auth-guards.spec.ts` exist and must be updated (confirmed from past learnings).
- `frontend-child` will use the same Vant 4 version as `frontend` to avoid duplicate Vant bundles.
- `useAuthStore` currently imports `router` from `@/router` and `showToast` from Vant — these calls must be removed during extraction (confirmed by reading `frontend/src/stores/auth.ts`).

## Outstanding Questions

### Resolve Before Planning
_(none — all product decisions resolved)_

### Deferred to Planning
- [Affects R6, R26–R28][Technical] Locate `nginx.conf` and `docker-compose.yml` service definitions; determine the exact proxy target names and port assignments for the new `frontend-child` container.
- [Affects R8, R9][Technical] Audit all `router.push` and `showToast` calls in `frontend/src/stores/auth.ts` and `frontend/src/stores/childAuth.ts`; design the app-layer callback pattern that replaces them.
- [Affects R14][Technical] Verify whether the two `ChildDayDetailPage` copies can share i18n keys and API calls, or whether they will diverge — document the duplication strategy in the plan.
- [Affects R23–R25][Technical] Confirm `no-restricted-imports` path patterns work correctly with pnpm workspace symlinks in ESLint v9 flat config.

## Next Steps

-> `/ce:plan` for structured implementation planning
