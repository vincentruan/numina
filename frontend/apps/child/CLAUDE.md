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

Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` + `en-US.ts`, use `t('key')` in Vue file, run `npm run typecheck`. See section keys in `zh-CN.ts` for organization.

### Emoji Convention

| Type | Emoji | Examples |
|------|-------|---------|
| Success | ✅ | `✅ 登录成功`, `✅ 已赠出` |
| Failure/Error | ❌ | `❌ 抽奖失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 余额不足`, `⚠️ 暂无机会` |
| Lock | 🔒 | `🔒 账号已锁定` |

## Path Alias

`@/` maps to `src/` — configured in both `vite.config.ts` and `tsconfig.app.json`.

## Design System (DESIGN.md — mandatory)

This app uses the **Clay** design system defined in [`DESIGN.md`](./DESIGN.md). All UI work **must** follow it — colors, typography, spacing, radius, components. Do not invent tokens; reference DESIGN.md exclusively.

**Key gotchas** (commonly violated):
- Canvas background is `#fffaf0`, not `#ffffff`
- Use `ink: #0a0a0a`, never raw `#000000`
- No hardcoded hex colors — use CSS variables from `clay.css`

## Display Configuration Requirements

Two user-configurable display preferences, both persisted client-side via `localStorage` and applied via module-level singleton composables.

### i18n (Language Switching)

**Source:** `src/utils/locale.ts` (composable), `src/i18n/locales/zh-CN.ts` + `en-US.ts` (strings), side-effect import in `main.ts`

**Rules:**
1. All strings via `t('key')` — no hardcoded text, including template ternaries and date formatting
2. `zh-CN.ts` and `en-US.ts` must stay in sync
3. Arrays with `t()` labels must be `computed()` — otherwise labels freeze at setup time
4. Date formatting must use `locale.value`, never hardcode `'zh-CN'`
5. Language option labels use self-identifying names identical in both locale files
6. localStorage key is `child:locale` (namespaced to avoid collision with main app)

### Dark/Light Mode (Theme Mode Switching)

**Source:** `src/utils/darkMode.ts` (composable), `src/assets/clay.css` (`:root` + `[data-theme="dark"]` tokens)

**Rules:**
1. Use CSS variables from `clay.css`, never hardcode colors
2. Key tokens: `--color-canvas`, `--color-surface-soft`, `--color-surface-card`, `--color-ink`, `--color-body`, `--color-muted`, `--color-hairline`, `--color-primary`, `--color-on-primary`
3. Dark mode overrides live in `clay.css` — no `@media (prefers-color-scheme: dark)` in components
4. Vant dark overrides are in `clay.css`'s second `[data-theme="dark"]` block — don't override Vant colors in components
5. Dark mode primary is ochre (`#e8b94a`), not ink — interactive elements using `var(--color-primary)` adapt automatically
6. Feature card text in dark mode uses `--color-on-feature-*` tokens
7. Test both modes before reporting done

### Cross-Cutting Display Rules

- `ChildHomePage.vue` settings section is the single UI for both preferences
- Read preferences via `useDarkMode()` / `useLocale()` composables — never read localStorage directly
- New visual components must use semantic CSS variables; add missing tokens to `clay.css` in both `:root` and `[data-theme="dark"]`
- Smooth transition is global in `clay.css` — don't add per-component theme transitions
- Canvas is `#fffaf0` (warm cream), not `#ffffff`

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
