# frontend/apps/child/CLAUDE.md

Module-specific guidance for the child-facing Vue 3 + TypeScript app.
See root [`CLAUDE.md`](../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `frontend/apps/child/`:

```bash
npm run dev          # Vite dev server — http://localhost:5174, hot reload
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run build         # full production build
npm run test:run      # vitest run — run tests once (no watch)
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **vue-tsc:** canonical type gate. Run `npm run typecheck` before pushing. Strict mode on.
- **Vant components** are auto-imported via `unplugin-vue-components`. Do not manually import them.

## Directory Structure

```
src/
├── api/           # HTTP request modules
├── components/    # Reusable Vue components
├── i18n/          # Localization (zh-CN.ts, en-US.ts)
│   └── locales/
│       ├── zh-CN.ts   # All user-facing strings — add here, never inline
│       └── en-US.ts   # English translations — keep in sync with zh-CN.ts
├── pages/         # Route-level views
├── router/        # Vue Router config
├── stores/        # Pinia state stores
├── types/         # TypeScript type definitions
└── utils/         # Helper functions
```

## Key Invariants

- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **Vant components are auto-imported** — do not manually import them.

## i18n Rules

**All user-facing strings must go through `t('key')`** — no exceptions.

```ts
// ✅ Correct
showToast(t('toast.drawFailed'))          // defined in zh-CN.ts
{{ t('chore.statusApproved') }}           // template label via i18n

// ❌ Wrong — hard-coded string
showToast('❌ 抽奖失败，请稍后再试')
{{ c.status === 'approved' ? '已完成' : '待审批' }}
```

This applies to:
- `showToast()` calls
- Template ternaries for status labels
- Milestone/achievement label maps
- Any string a child user will see

### Adding New Messages

1. Add the emoji-prefixed string to `src/i18n/locales/zh-CN.ts` under the appropriate section (`toast`, `errors`, `chore`, `blindBox`, etc.)
2. Use `t('section.key')` in the Vue file
3. Run `npm run typecheck` to verify

### Emoji Convention

| Type | Emoji | Examples |
|------|-------|---------|
| Success | ✅ | `✅ 登录成功`, `✅ 已赠出` |
| Failure/Error | ❌ | `❌ 抽奖失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 余额不足`, `⚠️ 暂无机会` |
| Lock | 🔒 | `🔒 账号已锁定` |

### i18n Key Sections in `zh-CN.ts`

| Section | Purpose |
|---------|---------|
| `common` | Shared labels (confirm, cancel, loading…) |
| `nav` | Bottom nav labels |
| `auth` | Login/PIN screen text |
| `errors` | Error code → message mapping |
| `toast` | All `showToast()` messages |
| `chore` | Chore status labels (`approved`, `pending_approval`…) |
| `blindBox` | Blind box draw messages |
| `milestone` | Achievement/milestone label map |

## Path Alias

`@/` maps to `src/` — configured in both `vite.config.ts` and `tsconfig.app.json`.

## Design System (DESIGN.md — mandatory)

This app uses the **Clay** design system defined in [`DESIGN.md`](./DESIGN.md). All UI work **must** follow it. Do not invent colors, spacing, typography, or component styles — reference DESIGN.md exclusively.

### Non-negotiable rules

- **Colors** — use only tokens from `DESIGN.md colors`. Never hardcode hex values. Map to CSS variables or Tailwind tokens derived from that palette.
- **Typography** — use only the type scale defined in `DESIGN.md typography` (display-xl → caption-uppercase). Match `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing` exactly.
- **Spacing** — use only the spacing scale (`xxs: 4px` → `section: 96px`). No arbitrary pixel values.
- **Border radius** — use only `rounded` tokens (`xs: 6px` → `pill: 9999px`).
- **Components** — buttons, cards, inputs, nav must match the component specs in `DESIGN.md components`. Use the correct variant (e.g. `button-primary` vs `button-secondary` vs `button-on-color`).
- **Feature cards** — use the named color variants (`feature-card-pink`, `feature-card-teal`, `feature-card-lavender`, `feature-card-peach`, `feature-card-ochre`, `feature-card-cream`). Do not create ad-hoc card colors.
- **Canvas background** — default page background is `canvas: #fffaf0`, not white (`#ffffff`).
- **Dark surfaces** — use `surface-dark` / `surface-dark-elevated` for dark-mode or inverted sections; never plain black.

### Before writing any UI component

1. Open `DESIGN.md` and locate the relevant component spec.
2. Apply the exact `backgroundColor`, `textColor`, `rounded`, `padding`, and `typography` values.
3. If a component variant doesn't exist in DESIGN.md, use the closest existing variant and note the gap — do not freestyle.

### Anti-patterns (never do these)

- Hardcoded hex colors not in the DESIGN.md palette
- Font sizes or weights outside the type scale
- Arbitrary border-radius values
- Inventing new component variants without a DESIGN.md entry
- Using `#ffffff` as canvas (correct value is `#fffaf0`)
- Using raw black (`#000000`) — use `ink: #0a0a0a` instead

## Display Configuration Requirements

The child app supports two user-configurable display preferences — language and theme mode. Both are persisted client-side via `localStorage` and applied reactively via module-level singleton composables. **Every UI component must respect these settings.**

### i18n (Language Switching)

User's language preference is managed by `src/utils/locale.ts` — a module-level singleton `ref` that syncs to `localStorage('child:locale')` via `watchEffect`. `App.vue` does not drive locale; the composable initializes itself on import (side-effect import in `main.ts`).

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
6. localStorage key is **namespaced** as `child:locale` to avoid collision with other apps on the same origin

### Dark/Light Mode (Theme Mode Switching)

User's theme preference is managed by `src/utils/darkMode.ts` — a module-level singleton `ref<'light' | 'dark' | 'system'>` that resolves to a boolean `isDark` and sets `document.documentElement.setAttribute('data-theme', 'dark'|'light')`. Persisted to `localStorage('theme-mode')`.

**Rules:**

1. **Use CSS variables, never hardcode colors** — all colors must reference the semantic tokens defined in `clay.css` (`:root` for light, `[data-theme="dark"]` for dark). Components must never use raw hex/rgb values for backgrounds, text, or borders
2. **Semantic tokens for layout colors:**
   | Purpose | Variable |
   |---------|----------|
   | Page background | `var(--color-canvas)` |
   | Soft surface | `var(--color-surface-soft)` |
   | Card background | `var(--color-surface-card)` |
   | Strong surface | `var(--color-surface-strong)` |
   | Primary text | `var(--color-ink)` |
   | Body text | `var(--color-body)` |
   | Secondary text | `var(--color-muted)` |
   | Borders/separators | `var(--color-hairline)` |
   | Primary CTA | `var(--color-primary)` |
   | On-primary text | `var(--color-on-primary)` |
3. **Dark mode overrides live in `clay.css`** under `[data-theme="dark"]` — do not scatter `@media (prefers-color-scheme: dark)` in component `<style>` blocks
4. **Vant components are themed via CSS variable overrides** in the second `[data-theme="dark"]` block in `clay.css` (tabbar, nav-bar, cell, field, popup, picker, dialog, button, toast, overlay). Do not manually override Vant colors in components unless there is no matching token
5. **Dark mode primary color switches to ochre** (`#e8b94a`) — not the same accent as light mode (`#0a0a0a`). Interactive elements using `var(--color-primary)` automatically adapt. Respect this — dark mode has its own accent palette for readability
6. **Test both modes** — after any visual change, verify the component in both light and dark mode before reporting done
7. **Feature card text tokens** — when rendering feature cards in dark mode, use the dedicated `--color-on-feature-*` tokens (e.g., `--color-on-feature-ochre`, `--color-on-feature-pink`) for text legibility on darkened brand surfaces

### Cross-Cutting Display Rules

- **Settings UI** (`ChildHomePage.vue`) is the single UI for both display preferences — a collapsible settings section with theme mode buttons and language buttons. Changes call `setMode()` and `setLocale()` from the respective composables
- **No component should read display preferences directly from localStorage** — always go through `useDarkMode()` (for theme) or `useLocale()` (for language). The composables are the single source of truth
- **Smooth transitions are global** — `clay.css` applies `transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease` to all elements. Do not add per-component transition rules for theme switching
- **When adding new visual components**, use the semantic CSS variable tokens above. If a needed token doesn't exist, add it to `clay.css` in both `:root` and `[data-theme="dark"]` blocks — don't inline colors in the component
- **Canvas background is `#fffaf0`** (warm cream), not `#ffffff` — this is set by `--color-canvas` and is a Clay design system invariant

## Documented Solutions

`docs/solutions/` contains documented fixes for past problems relevant to child frontend development:

| Category | Example |
|----------|---------|
| `developer-experience/` | Vue 3 i18n locale switching with localStorage persistence (canonical pattern for this app) |
| `ui-bugs/` | Vant 4 `:model-value` vs `:value` binding |

Search by `module`, `tags`, or `problem_type` in YAML frontmatter. Relevant when debugging recurring issues or implementing patterns that have been solved before.

## Links

- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Main app [`CLAUDE.md`](../main/CLAUDE.md) — same i18n rules, emoji convention reference
- [`DESIGN.md`](./DESIGN.md) — Clay design system (colors, typography, components, spacing)
