# frontend/packages/CLAUDE.md

Shared packages under `frontend/packages/`. All conventions from [`frontend/apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) apply here unless noted otherwise.

## Packages

| Package | Purpose |
|---------|---------|
| `auth` | Shared auth components, stores, and utilities used by both `main` and `child` apps |

Code changes here affect both `frontend/apps/main` and `frontend/apps/child`.

## auth Package Exports

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

## Key Invariants (inherited)

- **i18n required for all UI strings** — no hard-coded Chinese strings in `.vue` or `.ts` files. Define in the consuming app's `src/i18n/locales/*.ts` and pass via props or composable arguments.
- **Emoji convention** — user-facing messages must include emoji prefixes. See main app CLAUDE.md for the full table.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.
- **Vant components** — do not import Vant directly in packages; leave that to the consuming app's auto-import setup.

## Quality Commands

Run from `frontend/`:

```bash
npm run lint          # ESLint across all workspaces
npm run typecheck     # type-check all workspaces including packages
```

Or from the package directory directly:

```bash
cd packages/auth && npx tsc --noEmit
```

## Links

- [`frontend/apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) — full conventions, patterns, design system
- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
