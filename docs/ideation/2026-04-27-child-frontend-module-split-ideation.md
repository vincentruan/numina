---
date: 2026-04-27
topic: child-frontend-module-split
focus: 将儿童视图拆分为独立前端模块（frontend-child），共享账户体系和家庭权限
mode: repo-grounded
---

# Ideation: Child Frontend Module Split

## Grounding Context

**Codebase context:**
- Numina: Vue 3 + TypeScript + Vite + Vant 4, self-hosted family asset management
- Frontend has adult routes (`/`) and child routes (`/child/*`) in ONE codebase, ONE build
- Child pages already isolated in `pages/child/` (ChildHomePage, ChildTasksPage, ChildTreasuresPage, ChildWishesPage, ChildLedgerPage)
- Child components in `components/child/` (ChildTabBar, MilestoneCelebration) + coin system
- Child auth: PIN-based via `useChildAuthStore`, separate from adult JWT auth
- Shared: `useFamilyStore`, `useAuthStore` (parent info), family API
- Route guard: single router with conditional logic checking `role === 'child'`
- No module boundary enforcement — child pages can import adult components
- Child and adult code bundled together; no tree-shaking isolation

**Past learnings:**
- Route classification system exists: PROTECTED_ROUTES / GUEST_ROUTES / PUBLIC_ROUTES
- Route sync test is mandatory (`tests/e2e/auth-guards.spec.ts`)
- ESLint v9 flat config pitfalls documented (explicit `ignores`, `globals.browser` required)
- No prior precedent for full Vue 3 sub-application splitting in this repo

**External context:**
- pnpm workspaces + Vite is the established pattern for Vue 3 multi-app monorepos
- Feature-Sliced Design (FSD) prevents shared folders from becoming dumping grounds
- Micro-frontends are a last resort for small teams; pnpm workspace monorepo is the right ceiling
- Family banking apps (Greenlight, Pockee) universally implement two distinct auth flows in one codebase
- Apple's Declared Age Range API: parent account grants child a scoped capability set

## Ranked Ideas

### 1. pnpm Workspace + Two Thin App Shells
**Description:** Restructure the repo as a pnpm workspace with `frontend/` (adult), `frontend-child/` (child), and shared packages (`packages/auth`, `packages/ui-shared`). Each app is a thin Vite shell consuming shared packages via `workspace:*` — no cross-app imports.
**Rationale:** This is the established pattern for Vue 3 multi-app monorepos. The child pages are already isolated in `pages/child/` and `components/child/` — the extraction is mostly mechanical. Micro-frontends are overkill; this is the right ceiling for a small team.
**Downsides:** One-time migration cost to restructure directories and set up workspace config. pnpm workspace adds a new mental model for contributors.
**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

### 2. Shared Auth Package (`packages/auth`)
**Description:** Extract `useChildAuthStore`, `useAuthStore`, and the PIN/JWT logic into a `packages/auth` workspace package consumed by both apps. Auth fixes propagate everywhere automatically; neither app can diverge on auth behavior.
**Rationale:** The natural seam already exists — `useChildAuthStore` and `useAuthStore` are logically separate today. This makes the boundary physical and versioned. Auth bugs fixed once are fixed everywhere.
**Downsides:** Requires deciding the exact public API surface of the package upfront. Changes to auth now require a package-level change, not just a file edit.
**Confidence:** 88%
**Complexity:** Low–Medium
**Status:** Unexplored

### 3. Typed API Contract Package (`packages/api-types`)
**Description:** Define all API response shapes, request payloads, and domain types (FamilyMember, Asset, Task, Coin) in a single `packages/api-types` package. Both apps import types from here — a backend schema change surfaces as a TypeScript error in both apps simultaneously.
**Rationale:** `useFamilyStore` is already shared between child and adult pages; the types it uses are the natural extraction target. This turns API drift from a runtime surprise into a compile-time signal.
**Downsides:** Requires discipline to keep types in the package rather than co-locating them with API call files. Initial extraction requires auditing all existing type definitions.
**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

### 4. ESLint Import Boundary Rules
**Description:** Add `eslint-plugin-boundaries` rules that forbid `frontend-child` from importing anything outside `packages/auth`, `packages/ui-shared`, and its own directory. CI fails if a child page imports an adult component.
**Rationale:** Without this, the split degrades over time as developers take shortcuts. The repo already has ESLint v9 flat config infrastructure — adding boundary rules is additive. The architecture becomes self-enforcing.
**Downsides:** Requires configuring the plugin correctly for the workspace structure. False positives possible during initial setup.
**Confidence:** 87%
**Complexity:** Low
**Status:** Unexplored

### 5. Nginx-Level App Routing (No Shared Router)
**Description:** Nginx serves `frontend-child/dist` for `/child/*` requests and `frontend/dist` for everything else. Each app has its own minimal router with no cross-app route awareness. The `role === 'child'` guard in `router/index.ts` is deleted — Nginx is the only guard.
**Rationale:** The project already uses Nginx + Docker Compose. Moving the guard to infrastructure means it can't drift, can't be bypassed by a bad import, and is auditable in one place. A `location /child/` block is a one-line nginx config change.
**Downsides:** Nginx config becomes load-bearing for security — a misconfiguration could expose adult routes to child sessions. Requires careful testing of the routing rules.
**Confidence:** 82%
**Complexity:** Low (config) + Medium (testing)
**Status:** Unexplored

### 6. Scoped Capability Token (Capability-Based Auth)
**Description:** Instead of `role === 'child'` checks, the backend issues a scoped capability token to the child PIN session: `{ canViewLedger: true, canRedeemWishes: true, canViewAdultAssets: false }`. The child app reads a capability set — it has no concept of "child mode" or role comparison.
**Rationale:** Reframes auth from role-based to data-driven, enabling per-child permission overrides. Apple's Declared Age Range API uses exactly this pattern. Extensible without code changes when new child features are added.
**Downsides:** Requires backend changes to issue capability tokens. More complex than a role check for the initial implementation. Capability set must be kept in sync with what the child app actually renders.
**Confidence:** 78%
**Complexity:** Medium
**Status:** Unexplored

### 7. Server-Side Child Session (Move PIN to Backend)
**Description:** Instead of `useChildAuthStore` holding PIN state in the browser, the backend issues a short-lived child session token when a parent unlocks child mode via the family API. The child app checks only for this token — no PIN logic in the frontend at all.
**Rationale:** PIN validation in the browser is a client-side auth bypass risk. Moving it to the server follows the same pattern as the existing JWT auth. Additive to the existing backend — a `POST /family/child-session` endpoint returning a scoped token.
**Downsides:** Requires the parent to be authenticated to unlock child mode (currently a child can PIN-login independently). May change the UX flow for child login.
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Turborepo task graph | Premature for small team; pnpm workspaces alone is sufficient |
| 2 | Child app as PWA | Orthogonal to the split question; can be done after split |
| 3 | Two Vite configs, one repo root | Weaker version of workspace idea; keeps shared node_modules coupling |
| 4 | Child app has no router | Breaks deep-linking; child pages already have distinct URLs |
| 5 | Data-driven child navigation | Over-engineered for a stable 5-page set |
| 6 | Auto-extract import graph script | Migration tool, not an architectural idea |
| 7 | Child-first build order | Complexity already solved by workspace separation |
| 8 | SSR/Jinja2 child shell | Introduces second rendering paradigm; maintenance burden |
| 9 | No child app (parent projection) | Contradicts the product goal of a child-facing experience |
| 10 | Child as primary, adult as admin | High disruption for a naming/mental-model benefit only |
| 11 | Capacitor native wrapper | Massive operational overhead for a self-hosted app |
| 12 | API-level split (two FastAPI routers) | Backend concern; separate improvement from frontend DX |
| 13 | Generated child auth adapter | Over-engineered; simple extraction to packages/auth suffices |
