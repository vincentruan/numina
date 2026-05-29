# frontend/packages/CLAUDE.md

Shared packages under `frontend/packages/`. Conventions from [`frontend/apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) apply unless noted.

Code changes in this directory affect both `frontend/apps/main` and `frontend/apps/child`.

## Packages

| Package | Purpose | Has Vue/Pinia? |
|---------|---------|----------------|
| `@numina/auth` | Auth components, stores, axios wiring, trusted-device flow | Yes |
| `@numina/math` | Pure math/business-logic functions for cross-wish reachability and opportunity-cost peek | No — framework-free |

## `@numina/auth` Exports

Import from `@numina/auth`:

| Export | Type | Purpose |
|--------|------|---------|
| `useAuthStore` | Pinia store | Main app auth state (login, logout, token refresh) |
| `useChildAuthStore` | Pinia store | Child app auth state (PIN login, step-1/step-2 flow) |
| `configureAuthHttp` | Function | Wire the shared axios instance — call in `main.ts` before using stores |
| `AuthStep1Form` | Component | Step-1 login form (shared UI) |
| `TrustedDeviceCard` | Component | Trusted device management card |
| `LoadingOverlay` | Component | Full-screen loading overlay |
| `useLoadingOverlay` | Composable | Show/hide the loading overlay |
| `getUser` / `setUser` / `removeUser` / `clearAuth` | Utils | LocalStorage token/user helpers |
| `getDeviceFingerprint` | Util | Stable browser fingerprint for trusted-device flow |

### Auth Key Invariants

- **i18n required** — no hard-coded Chinese strings. Define in the consuming app's `src/i18n/locales/*.ts`; pass via props or composable arguments.
- **Emoji convention** — see [`apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) for the table.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API.
- **Don't import Vant directly** — leave Vant imports to the consuming app's auto-import setup.

## `@numina/math` Exports

Import from `@numina/math`:

| Export | Kind | Purpose |
|--------|------|---------|
| `daysEstimate` | Function | Days-to-target reachability projection |
| `previewSpend` | Function | Opportunity-cost preview (delta on remaining wishes if you spend now) |
| `reachabilityTint` | Function | Map a `daysEstimate` result to UI tint (`green`/`yellow`/`red`) |
| `YELLOW_BOUNDARY_DAYS` | Constant | Threshold between green and yellow tint |
| `PrioritySimulationEntry`, `LedgerEntry`, `ReachabilityTint`, `SpendDelta`, `SpendPreview` | Types | Trust-contract type surface shared with backend simulation |

### Math Key Invariants

- **Pure functions only** — no Vue, no Pinia, no axios, no `localStorage`, no `Date.now()` reads outside arguments. Inputs in → outputs out.
- **Trust-contract math** — both `apps/child` and `apps/main` rely on identical results. Changing arithmetic semantics is a breaking change; bump tests in lockstep.
- **Test-first** — every function has a colocated `*.test.ts`. New behavior needs a failing test before implementation.
- **No framework imports** — `package.json` has no `peerDependencies`. Don't add any.

Reference: `docs/plans/2026-05-24-002-feat-child-cross-wish-bundle-plan.md` U1 and `docs/brainstorms/2026-05-24-child-cross-wish-bundle-requirements.md`.

## Quality Commands

Run from `frontend/`:

```bash
pnpm -r lint            # ESLint across all workspaces
pnpm -r typecheck       # type-check all workspaces including packages
pnpm -r test:run        # run vitest in every package that defines it
```

Or per-package:

```bash
cd packages/auth && pnpm typecheck && pnpm test:run
cd packages/math && pnpm typecheck && pnpm test:run
```

## Links

- [`frontend/apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) — full conventions, design system
- [`frontend/apps/child/CLAUDE.md`](../apps/child/CLAUDE.md) — child app conventions
- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
