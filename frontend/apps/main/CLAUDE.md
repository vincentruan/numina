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

- **i18n required for all UI strings** — every user-facing string (toasts, dialogs, labels, status text) must be defined in `src/i18n/locales/zh-CN.ts` and referenced via `t('key')`. Never hard-code Chinese strings in `.vue` templates or `.ts` logic — not even in ternary expressions like `condition ? '已完成' : '待审批'`. Move all status labels to i18n keys.
- **Emoji convention** — All user-facing toast messages, confirmation dialogs, and error messages MUST include an emoji prefix via i18n keys. Never hard-code strings directly in Vue files. See Patterns section.
- **Vant components are auto-imported** via `unplugin-vue-components`. Do not manually import them.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.

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

1. Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` and `en-US.ts` under `toast` or `errors`
2. Use `t('key')` or `t('key', { param })` in the Vue file
3. Run `npm run typecheck` to verify

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

The main app supports three user-configurable display preferences — language, theme mode, and theme color. All three are persisted server-side on the `User` model and applied reactively via `App.vue` watchers. **Every UI component must respect these settings.**

### i18n (Language Switching)

User's language preference (`User.language`) drives `vue-i18n` locale. `App.vue` watches `authStore.user?.language` and sets `locale.value` reactively.

**Rules:**

1. All user-facing strings must use `t('key')` — never hardcode Chinese or English text in `.vue` or `.ts` files, including template ternaries and `toLocaleDateString()` calls
2. Both `zh-CN.ts` and `en-US.ts` must stay in sync — every key added to one must exist in the other
3. Arrays with `t()` labels must be `computed()`, not static — otherwise labels freeze at setup time and won't update on locale switch:
   ```ts
   // Wrong — labels frozen at component setup
   const options = [{ label: t('foo'), value: 'a' }]

   // Correct — labels re-evaluate reactively
   const options = computed(() => [{ label: t('foo'), value: 'a' }])
   ```
4. Date/time formatting must use `locale.value` from `useI18n()`, never hardcode `'zh-CN'`:
   ```ts
   const { t, locale } = useI18n()
   const label = computed(() =>
     date.toLocaleDateString(locale.value, { month: 'long', day: 'numeric' })
   )
   ```
5. Language option labels use self-identifying names identical in both locale files (e.g., `'🇨🇳 中文'`, `'🇺🇸 English'`) to solve the bootstrap problem

### Dark/Light Mode (Theme Mode Switching)

User's theme preference (`User.theme`) supports three values: `'light'`, `'dark'`, `'system'`. `App.vue` resolves `system` via `window.matchMedia('(prefers-color-scheme: dark)')` and sets `document.documentElement.setAttribute('data-theme', resolvedTheme)`.

**Rules:**

1. **Use CSS variables, never hardcode colors** — all colors must reference the semantic tokens defined in `style.css` (`:root` for light, `[data-theme='dark']` for dark). Components must never use raw hex/rgb values for backgrounds, text, or borders
2. **Semantic tokens for layout colors:**
   | Purpose | Variable |
   |---------|----------|
   | Page background | `var(--bg-primary)` or `var(--bg-secondary)` |
   | Card background | `var(--card-bg)` |
   | Primary text | `var(--text-primary)` |
   | Secondary text | `var(--text-secondary)` |
   | Borders/separators | `var(--separator)` or `var(--color-hairline)` |
   | Surface canvas | `var(--color-canvas)` |
3. **Dark mode overrides live in `style.css`** under `[data-theme='dark']` — do not scatter `@media (prefers-color-scheme: dark)` in component `<style>` blocks
4. **Vant components are themed automatically** via `<van-config-provider :theme="resolvedTheme">` in `App.vue` plus CSS variable overrides in `style.css`. Do not manually override Vant colors in components unless there is no matching token
5. **Test both modes** — after any visual change, verify the component in both light and dark mode before reporting done

### Theme Color (Custom Primary Color)

User selects a primary color from 8 predefined options. Currently stored in `localStorage('theme-primary')` and applied by setting `--van-primary-color` and `--theme-primary` CSS variables on `document.documentElement`.

**Rules:**

1. **Buttons and interactive elements must use `var(--van-primary-color)`** — never hardcode a specific color like `#010120` or `#bdbbff` for primary button backgrounds, active tabs, or checked states
2. **Background colors derived from theme color must use a light tint** — when a component needs a themed background (e.g., a selected card, active section), derive a light-opacity version: `rgba(var(--theme-primary-rgb, 1, 1, 32), 0.06)` or use `var(--color-soft-stone)` as a safe neutral. Never use the full-intensity theme color as a background on content areas
3. **Button style tokens in `style.css`** — primary buttons inherit from `--van-button-primary-background` and `--van-button-primary-border-color`. Both are set from `--color-primary` in light mode and `#bdbbff` in dark mode. If you add new button variants, follow this pattern
4. **Dark mode interaction** — in dark mode, `style.css` overrides `--van-primary-color` to `#bdbbff` (lavender). Custom theme color is currently overridden by this CSS rule. Respect this behavior — dark mode has its own accent palette for readability against dark backgrounds
5. The 8 predefined colors are: Blue `#007aff`, Purple `#5856d6`, Indigo `#3634a3`, Orange `#ff9500`, Red `#ff3b30`, Pink `#ff2d55`, Green `#248a3d`, Teal `#0071a4`. When adding new selectable colors, ensure they have sufficient contrast (WCAG AA) against both white text (for buttons) and dark backgrounds

### Cross-Cutting Display Rules

- **Settings page** (`SettingsPage.vue`) is the single UI for all display preferences — language, theme mode, and theme color. Changes call `PUT /auth/me/settings` for server-persisted settings (language, theme) and `localStorage` for theme color
- **No component should read display preferences directly from the API** — always go through `authStore.user` (for language/theme) or `localStorage` (for theme color). `App.vue` is the single point that applies these settings to the DOM
- **When adding new visual components**, use the semantic CSS variable tokens above. If a needed token doesn't exist, add it to `style.css` in both `:root` and `[data-theme='dark']` blocks — don't inline colors in the component

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
