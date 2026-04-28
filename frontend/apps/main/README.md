# Numina Frontend

Vue 3 + TypeScript + Vite + Vant 4 + ECharts mobile-first UI.
See the root [README.md](../README.md) for project overview and Docker deployment.

## Quick Start

```bash
cd frontend

npm ci                # Install dependencies
npm run dev           # Dev server (proxies /api to localhost:8000)
npm run build         # Production build (runs vue-tsc + vite build)
npm run preview       # Preview production build locally
```

## Quality Commands

```bash
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run format        # Prettier — format files in src/
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run test:run      # vitest run — run tests once (no watch mode)
```

## Architecture

```
frontend/src/
├── api/            # Axios HTTP client with JWT auto-refresh interceptor (21 modules — auth, assets, liabilities, dashboard, family, AI, children, chores, coins, wishes, and more)
├── assets/         # Static assets (images, icons, fonts)
├── components/     # Reusable components (charts/, common/, asset/, liability/, family/)
├── composables/    # Vue composables (one per domain)
├── constants/      # Shared constants and enums
├── i18n/           # Internationalization (zh-CN, en-US locale files)
├── layouts/        # MainLayout (bottom tab bar)
├── pages/          # Route-level page components (*Page.vue)
├── router/         # Vue Router with auth guards (requireAuth, requireGuest)
├── stores/         # Pinia state management (one store per domain)
├── types/          # TypeScript interfaces matching backend schemas
└── utils/          # storage (tokens + user), format (currency, date)
```

## Key Conventions

- **Vant components are auto-imported** via `unplugin-vue-components` — do not manually import them
- **Path alias `@/`** maps to `src/` (configured in `vite.config.ts` and `tsconfig.app.json`)
- **`<script setup lang="ts">`** only — no Options API, no `defineComponent`
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly
- **Incremental formatting** — format only files you touch, not the entire `src/`
- **Emoji convention** — all user-facing toast/dialog messages must use emoji-prefixed i18n keys (see `frontend/CLAUDE.md`)

## Detailed Conventions

See [`CLAUDE.md`](./CLAUDE.md) for:
- Full ESLint + Prettier + vue-tsc tooling config
- Emoji convention for user-facing messages with implementation examples
- i18n workflow for adding new messages
