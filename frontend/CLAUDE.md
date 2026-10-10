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
│   ├── math/      # @numina/math — pure business-logic functions
│   └── shared/    # @numina/shared — SSE parsing and shared utilities
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

## Solutions (Frontend Lessons Learned)

Check these docs before working in `frontend/` — they document verified fixes and patterns for known pitfalls.

### Architecture Patterns

| Doc | Topic |
|-----|-------|
| [`gamified-child-system`](../docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md) | 儿童积分游戏化系统架构 |
| [`ai-task-page-leave-continuity`](../docs/solutions/architecture-patterns/ai-task-page-leave-continuity-2026-08-21.md) | AI 任务页面离开连续性 |

### UI Bugs

| Doc | Topic |
|-----|-------|
| [`nprogress-lifecycle`](../docs/solutions/ui-bugs/nprogress-lifecycle-three-failure-modes.md) | NProgress 生命周期三种故障 (闪烁/不可见/卡住) |
| [`dark-mode-specificity`](../docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md) | Dark mode CSS 优先级被 inline style 覆盖 |
| [`action-sheet-clipped`](../docs/solutions/ui-bugs/action-sheet-clipped-in-transformed-container.md) | Action-sheet 在 transform 容器中被裁剪 |
| [`button-margin-overflow`](../docs/solutions/ui-bugs/full-width-button-margin-overflow.md) | 全宽按钮 margin 溢出 |
| [`itinerary-picker-icon`](../docs/solutions/ui-bugs/itinerary-type-picker-icon-display-2026-10-07.md) | Vant picker #option slot 图标不显示 |
| [`onboarding-overlay`](../docs/solutions/ui-bugs/onboarding-overlay-blocks-navigation.md) | Onboarding 遮罩阻挡导航 |
| [`silent-error-codes`](../docs/solutions/ui-bugs/silent-error-codes-for-expected-404.md) | 预期 404 触发错误 toast |
| [`vant4-field-binding`](../docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md) | Vant 4 van-field 需要 :model-value |
| [`vue3-keepalive-blank`](../docs/solutions/ui-bugs/vue3-transition-keepalive-blank-screen.md) | Vue3 Transition+KeepAlive 白屏 |

### Best Practices

| Doc | Topic |
|-----|-------|
| [`main-app-ui-design-patterns`](../docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md) | Main App UI 设计模式 |
| [`ai-chat-checkpoint-retry`](../docs/solutions/architecture-patterns/ai-chat-checkpoint-retry-architecture.md) | AI Chat checkpoint 重试架构 |

### Developer Experience

| Doc | Topic |
|-----|-------|
| [`monorepo-lint-format`](../docs/solutions/developer-experience/monorepo-module-level-lint-format-typecheck-2026-04-12.md) | Monorepo 模块级 lint/format/typecheck |
| [`pr-merge-verification`](../docs/solutions/developer-experience/pr-merge-verification-squash.md) | PR 合并状态验证 (squash merge 陷阱) |
| [`pnpm-duplicate-vant`](../docs/solutions/tooling-decisions/pnpm-workspace-duplicate-vant-provide-inject-broken.md) | pnpm 重复 Vant 版本破坏 provide/inject |
| [`vite-cache-stale-vue`](../docs/solutions/developer-experience/vite-cache-stale-vue-version.md) | Vite 缓存旧 Vue 版本 |
| [`vue-tsc-noop-typecheck`](../docs/solutions/developer-experience/vue-tsc-references-only-root-tsconfig-noop-typecheck-gate-2026-07-23.md) | vue-tsc references-only 导致 typecheck 空转 |
| [`vue3-i18n-locale-switching`](../docs/solutions/developer-experience/vue3-i18n-locale-switching-persistence-2026-05-15.md) | Vue3 i18n 语言切换 + localStorage 持久化 |
| [`device-fingerprint-stability`](../docs/solutions/integration-issues/device-fingerprint-stability.md) | 设备指纹稳定性问题 |

## Links

- [`packages/CLAUDE.md`](packages/CLAUDE.md) — @numina/auth + @numina/math exports
- [`apps/main/CLAUDE.md`](apps/main/CLAUDE.md) — main app specific config
- [`apps/child/CLAUDE.md`](apps/child/CLAUDE.md) — child app specific config
- Root [`CLAUDE.md`](../CLAUDE.md) — project-level constraints
