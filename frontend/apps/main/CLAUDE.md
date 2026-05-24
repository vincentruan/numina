# frontend/CLAUDE.md

Module-specific guidance for the Vue 3 + TypeScript frontend.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `frontend/apps/main/`:

```bash
npm run dev          # Vite dev server — http://localhost:5173, hot reload
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run format        # Prettier — format all files in src/
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run build         # vue-tsc -b && vite build — full production build
npm run test:run      # vitest run — run tests once (no watch)
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **Prettier:** config at `.prettierrc`. Single quotes, no semicolons, trailing commas, 100-char width.
- **vue-tsc:** canonical type gate. Run `npm run typecheck` before pushing. Strict mode is on (`tsconfig.app.json`).
- **vitest:** test runner. Tests live in `src/**/*.test.ts` or `src/**/*.spec.ts`.

## Directory Structure

```
src/
├── api/           # HTTP request modules
├── components/    # Reusable Vue components (ai/, asset/, charts/, common/, etc.)
├── composables/   # Vue composition functions
├── constants/     # Static constants
├── i18n/          # Localization (zh-CN.ts, en-US.ts)
├── layouts/       # Layout wrappers
├── pages/         # Route-level views (DashboardPage, AssetListPage, etc.)
├── router/        # Vue Router config
├── stores/        # Pinia state stores
├── types/         # TypeScript type definitions
└── utils/         # Helper functions
```

## Architecture Flow

```
pages/ → stores/ → api/ → backend HTTP
   ↓
components/ (reusable UI)
```

- Pages use stores for state
- Stores call api modules for HTTP
- Components are pure UI (no direct api calls)

## Key Invariants

- **i18n** — see root `CLAUDE.md` cross-cutting conventions. Emoji convention and patterns below.
- **Vant components are auto-imported** via `unplugin-vue-components`. Do not manually import them.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.

## AI Frontend Interaction Constraints

Frontend AI UI must stay at the **presentation/adaptation layer only**.

| Layer | Frontend CAN | Frontend CANNOT |
|-------|--------------|-----------------|
| Runtime | Render events from backend | Implement agent runtime, tool registry, skill loader, memory manager, orchestration/workflow engine, MCP runtime |
| Process viz | Display `reasoning_content`, `thinking` blocks, `tool_calls`, tool results, task/subtask status, artifacts, progress events, final content | Fabricate hidden reasoning, request model to reveal private chain-of-thought, invent process steps not explicitly returned |

**Rule:** Only display what DeerFlow/backend explicitly returns for UI use. No speculative visualization.

## Patterns

### Emoji Convention for User-Facing Messages

| Type | Emoji | Examples |
|------|-------|---------|
| Success | ✅ | `✅ 添加成功`, `✅ 已保存` |
| Failure/Error | ❌ | `❌ 操作失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 请先选择资产`, `⚠️ 邀请码无效` |
| Delete | 🗑️ | `🗑️ 已删除` |
| Info/Status | 📡, 🤖, 🔑 | `📡 网络错误`, `🤖 AI 功能未启用` |
| Special | 💰, 🎨, 🔥, 🎉 | `💰 还款成功`, `🎉 注册成功` |

**Implementation rules:**
1. Define emoji-prefixed strings in `src/i18n/locales/*.ts` under `toast` or `errors`
2. Use `t('toast.xxx')` or `t('errors.xxx')` in Vue files — never hard-coded strings
3. Confirmation dialogs use emoji too: `t('toast.confirmDelete', { name })` → `⚠️ 确定要删除「{name}」吗？`
4. Dynamic messages use interpolation: `t('toast.assetDeletedCount', { count: 3 })` → `🗑️ 已删除 3 项资产`

```ts
// ✅ Correct
showToast(t('toast.addSuccess'))        // Shows: ✅ 添加成功

// ❌ Wrong — hard-coded string without emoji
showToast('添加成功')
```

### Adding New Messages

Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` + `en-US.ts`, use `t('key')` in Vue file, run `npm run typecheck`.

### Path Alias

`@/` maps to `src/` — configured in both `vite.config.ts` and `tsconfig.app.json`.

## Design System

**All visual changes MUST follow the design system defined in [`DESIGN.md`](./DESIGN.md).**

Before writing any CSS, colors, typography, spacing, or component styles:
1. Read `DESIGN.md` to understand the Together AI-inspired visual language
2. Use only the color tokens, type scale, radius values, and spacing defined there
3. Override Vant component styles to match — do not introduce new design decisions

Key constraints from `DESIGN.md`:
- **Dark surface**: `#010120` midnight blue for dark sections — never generic gray-black
- **Brand accents**: magenta `#ef2cc1` and orange `#fc4c02` are illustration-only, never UI chrome
- **Soft accent**: lavender `#bdbbff` for subtle secondary highlights
- **Surface**: white canvas (`#ffffff`) as default; `#010120` for dark/research sections
- **Border radius**: `4px` sharp for buttons/badges, `8px` for larger cards — no pills, no generous rounding
- **No blue gradients**: pastel gradients (pink/lavender/blue) are decorative hero backgrounds only
- **Typography**: system sans-serif fallback ("The Future" not available); tight negative letter-spacing on all headings
- **Shadows**: always dark-blue-tinted `rgba(1, 1, 32, 0.1)` — never generic black shadows
- **Dual atmosphere**: light sections (business, white canvas) vs dark sections (research, `#010120`)

### Mobile-First Priority

This app is **mobile-first**. All design decisions must prioritize the phone viewport (≤425px) before considering larger screens.

- Touch targets minimum 44×44px; pill CTAs and action buttons must be comfortably tappable
- Single-column layout is the default; multi-column only when screen width ≥768px
- Avoid hover-only interactions — all affordances must work on touch
- Sticky elements (nav, category tabs, action bars) must not consume more than 15% of viewport height
- Font sizes: body minimum `14px`, primary labels `16px` — never smaller on mobile
- Spacing scale from `DESIGN.md` applies; prefer `8px`/`12px`/`16px` gutters on mobile over `24px`+
- Test every component at 375px width before considering it done

## Display Configuration Requirements

Three user-configurable display preferences, all persisted server-side on `User` model and applied via `App.vue` watchers.

### i18n (Language Switching)

**Source:** `App.vue` (watches `authStore.user?.language` → sets `locale.value`), `src/i18n/locales/zh-CN.ts` + `en-US.ts`

**Rules:**
1. All strings via `t('key')` — no hardcoded text, including template ternaries and `toLocaleDateString()` calls
2. `zh-CN.ts` and `en-US.ts` must stay in sync
3. Arrays with `t()` labels must be `computed()` — otherwise labels freeze at setup time
4. Date formatting must use `locale.value` from `useI18n()`, never hardcode `'zh-CN'`
5. Language option labels use self-identifying names identical in both locale files (e.g., `'🇨🇳 中文'`, `'🇺🇸 English'`)

### Dark/Light Mode (Theme Mode Switching)

**Source:** `App.vue` (resolves `User.theme` → sets `data-theme` attribute), `src/style.css` (`:root` + `[data-theme='dark']` tokens)

**Rules:**
1. Use CSS variables from `style.css`, never hardcode colors
2. Key tokens: `--bg-primary`, `--bg-secondary`, `--card-bg`, `--text-primary`, `--text-secondary`, `--separator`, `--color-canvas`
3. Dark mode overrides live in `style.css` — no `@media (prefers-color-scheme: dark)` in components
4. Vant theming is automatic via `<van-config-provider>` — don't manually override Vant colors
5. Test both modes before reporting done

### Theme Color (Custom Primary Color)

**Source:** `localStorage('theme-primary')` → sets `--van-primary-color` + `--theme-primary` on `documentElement`

**Rules:**
1. Interactive elements must use `var(--van-primary-color)` — never hardcode primary colors
2. Themed backgrounds use light tint: `rgba(var(--theme-primary-rgb), 0.06)` or `var(--color-soft-stone)`
3. In dark mode, `--van-primary-color` is overridden to `#bdbbff` (lavender) — respect this
4. Predefined colors: Blue `#007aff`, Purple `#5856d6`, Indigo `#3634a3`, Orange `#ff9500`, Red `#ff3b30`, Pink `#ff2d55`, Green `#248a3d`, Teal `#0071a4` — new colors need WCAG AA contrast

### Cross-Cutting Display Rules

- `SettingsPage.vue` is the single UI for all display preferences
- Read preferences via `authStore.user` (language/theme) or `localStorage` (theme color) — never from API directly
- New visual components must use semantic CSS variables; add missing tokens to `style.css` in both `:root` and `[data-theme='dark']`

## Documented Solutions

`docs/solutions/` contains documented fixes for past problems relevant to frontend development:

| Category | Example |
|----------|---------|
| `ui-bugs/` | Vant 4 `:model-value` vs `:value` binding |
| `developer-experience/` | Vue 3 i18n locale switching with localStorage persistence |

Search by `module`, `tags`, or `problem_type` in YAML frontmatter. Relevant when debugging recurring issues or implementing patterns that have been solved before.

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, component structure
