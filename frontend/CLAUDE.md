# frontend/CLAUDE.md

Frontend pnpm workspace. Inherits root [`CLAUDE.md`](../CLAUDE.md) project-level constraints.

## Workspace Structure

```
frontend/
├── apps/
│   ├── main/      # Adult H5 app (localhost:5173)
│   └── child/     # Child H5 app (localhost:5174)
├── packages/
│   ├── auth/      # @numina/auth — auth stores, components, axios wiring
│   └── math/      # @numina/math — pure business-logic functions
└── pnpm-workspace.yaml
```

## Commands

Dev commands — see root [`CLAUDE.md`](../CLAUDE.md) §Development Commands. Workspace-wide:

```bash
pnpm -r lint && pnpm -r typecheck && pnpm -r test:run
```

## Technology Stack

(See root for full stack: Vue 3 + TS + Vite + Vant 4 + ECharts)

| Technology | Constraint |
|------------|-----------|
| Vue | `<script setup lang="ts">` only — Options API forbidden |
| Types | `any` / `@ts-ignore` / `@ts-expect-error` forbidden |
| UI | Vant 4 auto-imported — no additional UI libraries |
| Icons | Iconify first, local SVG as fallback — no additional icon libraries; shared bitmaps/illustrations go in `@numina/assets` |
| HTTP | Axios unified wrapper (`src/api/index.ts`) — bare `fetch`/`axios` forbidden |
| State | Pinia — no global variables / localStorage as state management |
| Style | CSS variables + scoped — no fixed-width overflow |

## Architecture Flow

```
pages/ → stores/ → api/ → backend HTTP
   ↓
components/ (reusable UI, no direct api calls)
```

## Key Invariants

- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`
- **Vant auto-import** — don't manually import Vant components; only import functional API (`showToast`, `showDialog`)
- **i18n required** — every user-facing string must be defined in `src/i18n/locales/zh-CN.ts` and referenced via `t('key')`. Never hard-code Chinese strings in `.vue` or `.ts` — not even in template ternaries.
- **Date formatting must follow i18n locale** — `Date.toLocaleDateString()` / `toLocaleString()` first argument must use `locale.value` (from `useI18n()`). Hard-coding `'zh-CN'` / `'en-US'` or using `undefined` is forbidden. Manual Chinese date formatting (e.g. `${month}月${day}日`) is forbidden. Formatting should follow the app language setting, letting `Intl` API auto-select the format per locale.
- **Snowflake ID fields must be `string`** — the backend `SnowflakeBase` serializes `id` / `*_id` fields as strings at the JSON layer. Frontend TypeScript types must align: any field named `id` or ending in `*_id` must be typed as `string`, never `number`. Check new API types against this rule.
- **Toast uses Vant built-in icons** — select the correct toast function for the scenario:
  - ✅ Success → `showSuccessToast(message)` (built-in success icon)
  - ❌ Failure → `showFailToast(message)` (built-in failure icon)
  - ⏳ Loading → `showLoadingToast(message)` (built-in loading icon)
  - ℹ️ Info → `showToast({ message })` (plain text, no icon)
  - ⚠️ Warning → `showToast({ message, icon: 'warning-o' })`
- **Path alias** — `@/` maps to `src/`

## Vant 4 Patterns

| Need | Use | Not |
|------|-----|-----|
| Card/section | `van-cell-group` | Raw `<div class="card">` |
| List + scroll | `van-list` inside `van-pull-refresh` | Manual scroll listeners |
| Empty state | `EmptyState` component | Bare `van-empty` |
| Loading | `van-skeleton` / `van-loading` | Text "Loading..." |
| Confirm | `showConfirmDialog()` | `van-dialog` component |
| Toast | `showToast()` with i18n key | `van-notify` |
| Picker | `van-field` (readonly, `is-link`) + `van-popup` + `van-picker` | Custom dropdown |

**Gotchas:**
- `van-field`: use `:model-value` (not `:value`) in Vant 4
- `van-popup` + picker: use `destroy-on-close` to reset state
- `van-list` in pull-refresh: `van-list` must be inside, not a sibling

## Mobile H5 Patterns

- **KeepAlive**: Tab pages cached via `<KeepAlive :include="cachedTabs">` — `defineOptions({ name: 'Xxx' })` required
- **Refresh**: Use `onActivated` on cached pages; `onMounted` only fires once
- **Safe area**: Bottom handled globally in layout; pages don't add own padding
- **Pull-to-refresh**: All list pages wrap in `van-pull-refresh`
- **Touch targets**: Min 44×44px for all interactive elements

## Template Reference Baseline

**Base template**: [yulimchen/vue3-h5-template](https://github.com/yulimchen/vue3-h5-template) (reference, not a dependency)

| Principle | Description |
|-----------|------------|
| Existing first | Reuse current project implementations directly |
| Vant first | Official practices > personal wrappers |

## ECharts Guidelines

`vue-echarts` wrapper already exists — don't import useECharts. Consider mobile sizing / orientation / dark mode for containers. Separate data transformation from rendering.

## Dark Mode Guidelines

CSS variable implementation. Main app: `van-config-provider`; Child app: `[data-theme="dark"]` + clay.css. No designSetting store.

## ESLint

ESLint flat config + Prettier. Migration not recommended; if improvements are needed, consider lint-staged separately.

## Development Rules

| Rule | Description |
|------|------------|
| Research before writing | Check Vant/components/Iconify/request/structure before writing |
| Generalize first | Derive conventions from existing code; don't invent |
| Consistent style | Confirm CSS variable choices; don't introduce Tailwind without planning |
| Change documentation | Explain reuse/reference/new additions/impact |

**Forbidden:** Duplicate implementations, tech stack forking, unplanned UI/icon library additions

### Conflict Resolution

Priority: Project existing > Base template > Supplementary templates > Vant official > Simple unified

## Links

- [`packages/CLAUDE.md`](packages/CLAUDE.md) — @numina/auth + @numina/math exports
- [`apps/main/CLAUDE.md`](apps/main/CLAUDE.md) — main app specific config
- [`apps/child/CLAUDE.md`](apps/child/CLAUDE.md) — child app specific config
- Root [`CLAUDE.md`](../CLAUDE.md) — project-level constraints
