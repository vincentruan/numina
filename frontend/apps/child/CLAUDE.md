# frontend/apps/child/CLAUDE.md

Child H5 application. Inherits [`frontend/CLAUDE.md`](../../CLAUDE.md) common constraints.

## Commands

`pnpm dev` — http://localhost:5174. Other commands — see parent [`CLAUDE.md`](../../CLAUDE.md).

## Directory Structure

```
src/
├── api/           # HTTP request wrappers
├── components/    # Shared components
├── i18n/          # Internationalization (zh-CN.ts, en-US.ts)
├── pages/         # Route pages
├── router/        # Vue Router
├── stores/        # Pinia stores
├── types/         # TypeScript types
├── utils/         # Helper functions (locale.ts, darkMode.ts)
└── assets/        # clay.css — Clay visual tokens
```

## Vant 4 (Child-Specific)

- **No `<van-config-provider>`** — dark mode via CSS variable overrides in `clay.css`
- **Custom tabbar**: `ChildTabBar` component wraps `van-tabbar`
- **Custom empty**: `EmptyState` component with illustration + action
- Vant components auto-imported via `unplugin-vue-components`

### Theme Token Mapping (Clay)

| Clay Token | Vant Variable |
|-----------|---------------|
| `--color-primary` | `--van-primary-color` |
| `--color-ink` | `--van-text-color` |
| `--color-canvas` | `--van-background` |
| `--radius-md` | `--van-radius-md` |

### Gotchas

- **Route cache**: ChildHome, ChildTasks, ChildLedger, ChildWishes, ChildTreasures
- **Canvas warm cream**: `#fffaf0` (light), `#0a1a1a` (dark) — NOT pure white/black

## Dark Mode (Clay Warm-Throughout)

`useDarkMode()` composable + `[data-theme="dark"]` on `<html>` + `clay.css`.

| Rule | Description |
|------|------------|
| Warm base | `#FFFFFF` / cold gray forbidden |
| Multi-color cards | Stack brand rgba over `var(--color-surface-card)` |
| Primary text | `var(--color-ink)` |

**Iron rule**: New tokens must be defined in both `:root` and `[data-theme="dark"]`.

## Color Palette (Clay)

| Role | Light | Dark | Token |
|------|-------|------|-------|
| Canvas | `#fffaf0` | `#0a1a1a` | `--color-canvas` |
| Card surface | `#ffffff` | `#152828` | `--color-surface-card` |
| Primary text | `#0a0a0a` | `#f0ece0` | `--color-ink` |
| Secondary text | `#3d3d3d` | `#c0bcb0` | `--color-body` |
| CTA | `#0a0a0a` | `#e8b94a` | `--color-primary` |

## Shared Assets (`@numina/assets`)

Shared image/icon package — `@numina/assets` — tree-shaken at the module boundary. Only `import`-referenced assets enter the build.

| Category | Subpath | Import kind | Notes |
|----------|---------|-------------|-------|
| Shared icons (SVG/PNG) | `@numina/assets/icons` | `?url` → string URL | Cross-app icons only |
| Shared images | `@numina/assets/images` | `?url` → string URL | PNG, JPG, WebP |
| Empty-state illustrations | `@numina/assets/empty-states` | `?raw` → string | For `v-html` rendering ✅ already migrated |

### Child-app-local icons

- **`@iconify/vue`** — via `IIcon.vue` wrapper (`@/components/IIcon.vue`)
- **Empty-states** → migrated to `@numina/assets/empty-states`; import from shared package, not `@/assets/`

### Rules

- New cross-app images → add to `@numina/assets/images/` + named export in `index.ts`
- Child-only illustrations → prefer `@numina/assets/empty-states` (shared), unless truly child-specific
- `src/assets/` → avoid new files here; prefer shared package or `public/`

## Child App Troubleshooting Guide

For the following issues, refer to the corresponding solution document:

| Problem | Reference |
|---------|-----------|
| NProgress bar stuck spinning / bypassed guard flag | [`nprogress-stuck-child`](../../../docs/solutions/ui-bugs/nprogress-stuck-spinning-bypassed-guard.md) |
| Device fingerprint stability / authentication | [`device-fingerprint-stability`](../../../docs/solutions/integration-issues/device-fingerprint-stability.md) |
| Child gamification system architecture | [`gamified-child-system`](../../../docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md) |

## Links

- Parent [`CLAUDE.md`](../../CLAUDE.md) — frontend workspace constraints
- [`apps/main/CLAUDE.md`](../main/CLAUDE.md) — main app config
