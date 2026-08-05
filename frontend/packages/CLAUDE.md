# frontend/packages/CLAUDE.md

Shared packages. Inherits [`frontend/CLAUDE.md`](../CLAUDE.md) for common constraints.

Code changes here affect both `apps/main` and `apps/child`.

## Packages

| Package | Purpose | Has Vue/Pinia? |
|---------|---------|----------------|
| `@numina/auth` | Auth components, stores, axios wiring | Yes |
| `@numina/math` | Pure math/business-logic functions | No — framework-free |

## `@numina/auth` Exports

Import from `@numina/auth`:

| Export | Type | Purpose |
|--------|------|---------|
| `useAuthStore` | Pinia store | Main app auth (login, logout, token refresh) |
| `useChildAuthStore` | Pinia store | Child app auth (PIN login, step-1/step-2) |
| `configureAuthHttp` | Function | Wire axios instance — call in `main.ts` first |
| `AuthStep1Form` | Component | Step-1 login form |
| `TrustedDeviceCard` | Component | Trusted device management |
| `LoadingOverlay` | Component | Full-screen loading |
| `useLoadingOverlay` | Composable | Show/hide overlay |
| `getUser`/`setUser`/`removeUser`/`clearAuth` | Utils | LocalStorage helpers |
| `getDeviceFingerprint` | Util | Browser fingerprint |

### Auth Key Invariants

- **Don't import Vant directly** — leave to consuming app's auto-import

## `@numina/math` Exports

Import from `@numina/math`:

| Export | Kind | Purpose |
|--------|------|---------|
| `daysEstimate` | Function | Days-to-target reachability |
| `previewSpend` | Function | Opportunity-cost preview |
| `reachabilityTint` | Function | Map result to UI tint (`green`/`yellow`/`red`) |
| `YELLOW_BOUNDARY_DAYS` | Constant | Green→yellow threshold |
| `PrioritySimulationEntry`, `LedgerEntry`, `ReachabilityTint`, `SpendDelta`, `SpendPreview` | Types | Trust-contract types |

### Math Key Invariants

- **Pure functions only** — no Vue/Pinia/axios/localStorage/Date.now()
- **Trust-contract math** — identical results in both apps; changing semantics is breaking
- **Test-first** — colocated `*.test.ts`, failing test before impl
- **No framework imports** — `package.json` has no `peerDependencies`

## Links

Parent [`CLAUDE.md`](../CLAUDE.md) — frontend workspace 约束