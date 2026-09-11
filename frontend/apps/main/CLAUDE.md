# frontend/apps/main/CLAUDE.md

Adult H5 application. Inherits [`frontend/CLAUDE.md`](../../CLAUDE.md) common constraints.

## Commands

`pnpm dev` — http://localhost:5173. Other commands — see parent [`CLAUDE.md`](../../CLAUDE.md).

## Directory Structure

```
src/
├── api/           # HTTP request wrappers
├── components/    # Shared components (ai/, asset/, charts/, common/)
├── composables/   # Vue composition functions
├── i18n/          # Internationalization
├── layouts/       # MainLayout (KeepAlive + transitions)
├── pages/         # Route pages
├── plugins/       # Vite/Vue plugins
├── router/        # Vue Router
├── stores/        # Pinia stores
├── types/         # TypeScript types
└── utils/         # Helper functions
```

## Vant 4 (Main-Specific)

- Uses `<van-config-provider :theme="resolvedTheme">` for dark mode auto-switch
- Vant components auto-imported via `unplugin-vue-components`
- Theme tokens in `src/style.css`

### Theme Token Mapping

| Design Token | Vant Variable |
|-------------|---------------|
| `--van-primary-color` | Primary action color |
| `--van-tabs-bottom-bar-color` | `var(--van-primary-color)` |
| `--van-checkbox-checked-icon-color` | `var(--van-primary-color)` |

### Gotchas

- **Route cache**: Dashboard, FinanceHub, AIHub, Baby, Family, Settings (in `MainLayout.vue`)
- **Finance redirects**: `/assets`, `/liabilities`, `/wishes` routes redirect to `/finance?tab=...` (no standalone list pages)

## Dark Mode (WCAG AA)

`App.vue` uses `<van-config-provider :theme="resolvedTheme">`. Theme color from `localStorage('theme-primary')`.

| Rule | Description |
|------|------------|
| Multi-color cards | Stack `rgba(<daytime-color>, 0.14)` over `var(--card-bg)` |
| Primary text | `var(--text-primary)` — `#fff` forbidden |
| Secondary labels | `var(--text-secondary)`, alpha ≥ 0.55 |

**Red line**: No inline `style="color:..."` — see `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`

## Color Palette

| Role | Light | Dark | Token |
|------|-------|------|-------|
| Canvas | `#ffffff` | `#010120` | `--bg-primary` |
| Surface | `#f5f5ff` | `#12122a` | `--card-bg` |
| Primary text | `#0a0a0a` | `#f5f5f5` | `--text-primary` |
| Secondary text | `#616161` | `#c8c8d0` | `--text-secondary` |
| CTA | `var(--van-primary-color)` | `#bdbbff` | `--van-primary-color` |

## UI Design Patterns

Per-page-area (Overview/Finance/AI/Baby/Settings) Vant 4 component selection, card layouts, form patterns, CRUD interactions, and DeerFlow replication practices — see [`docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md`](../../../docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md).

**Core constraint**: Outside AI scenarios, reuse Vant 4 components as much as possible. AI scenarios use custom components replicating DeerFlow interactions.

## Shared Assets (`@numina/assets`)

Shared image/icon package — `@numina/assets` — tree-shaken at the module boundary. Only `import`-referenced assets enter the build.

| Category | Subpath | Import kind | Notes |
|----------|---------|-------------|-------|
| Shared icons (SVG/PNG) | `@numina/assets/icons` | `?url` → string URL | Cross-app icons only |
| Shared images | `@numina/assets/images` | `?url` → string URL | PNG, JPG, WebP |
| Empty-state illustrations | `@numina/assets/empty-states` | `?raw` → string | For `v-html` rendering |

### Main-app-local icons

- **SVG sprites** (47 category icons in `src/icons/svg/`) — remain app-local; used via `SvgIcon` component + `vite-plugin-svg-icons-ng`
- **IIcon** (`@/components/IIcon.vue`) — wraps `@iconify/vue` for Iconify icons
- **Game characters** (`public/images/*.svg`) — loaded via `fetch()` URL in `useDeerField.ts`, not importable

### Rules

- New cross-app images → add to `@numina/assets/images/` + named export in `index.ts`
- Main-only SVG category icons → stay in `src/icons/svg/`
- `src/assets/` → avoid new files here; prefer shared package or `public/`

## UI Troubleshooting Guide

For the following issues, refer to the corresponding solution document:

| Problem | Reference |
|---------|-----------|
| Dark mode styles not applying / `!important` specificity issues | [`dark-mode-inline-style-specificity`](../../../docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md) |
| NProgress bar flickering / stuck and not disappearing | [`nprogress-flicker`](../../../docs/solutions/ui-bugs/nprogress-flicker-page-navigation.md) |
| Vant 4 `van-field` binding not working / picker state issues | [`vant4-field-binding`](../../../docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md) |
| Vue 3 Transition + KeepAlive blank screen / page switch issues | [`vue3-transition-keepalive-blank-screen`](../../../docs/solutions/ui-bugs/vue3-transition-keepalive-blank-screen.md) |
| Onboarding overlay blocking navigation / scroll leak | [`onboarding-overlay-blocks-navigation`](../../../docs/solutions/ui-bugs/onboarding-overlay-blocks-navigation.md) |
| Action-sheet / popup clipped inside swipeable tabs | [`action-sheet-clipped-in-transformed-container`](../../../docs/solutions/ui-bugs/action-sheet-clipped-in-transformed-container.md) |
| Expected 404 response triggering error toast | [`silent-error-codes-for-expected-404`](../../../docs/solutions/ui-bugs/silent-error-codes-for-expected-404.md) |
| Full-width button + margin causing viewport overflow | [`full-width-button-margin-overflow`](../../../docs/solutions/ui-bugs/full-width-button-margin-overflow.md) |
| UI design patterns / component selection / card layouts | [`main-app-ui-design-patterns`](../../../docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md) |

## Links

- Parent [`CLAUDE.md`](../../CLAUDE.md) — frontend workspace constraints
- [`apps/child/CLAUDE.md`](../child/CLAUDE.md) — child app config
