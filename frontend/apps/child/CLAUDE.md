# frontend/apps/child/CLAUDE.md

Module-specific guidance for the child-facing Vue 3 + TypeScript app.
See root [`CLAUDE.md`](../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Workspace Dependencies

This app consumes two shared packages from `frontend/packages/` (pnpm workspace):

| Package | What it provides |
|---------|------------------|
| `@numina/auth` | Child auth store (`useChildAuthStore`), step-1/step-2 PIN login form, trusted-device card, axios wiring (`configureAuthHttp`), loading overlay |
| `@numina/math` | Cross-wish reachability + opportunity-cost math (`daysEstimate`, `previewSpend`, `reachabilityTint`, `YELLOW_BOUNDARY_DAYS`). Pure functions, no Vue/Pinia — both child and parent apps must compute identical results |

When importing, prefer the named exports from the package root (`import { daysEstimate } from '@numina/math'`). Do not reach into `@numina/math/src/...` paths.

## Quality Commands

Run all commands from `frontend/apps/child/`:

```bash
pnpm dev          # Vite dev server — http://localhost:5174, hot reload
pnpm lint          # ESLint — check for errors and warnings
pnpm lint:fix      # ESLint — auto-fix where possible
pnpm typecheck     # vue-tsc --noEmit — type check without building
pnpm build         # full production build
pnpm test:run      # vitest run — run tests once (no watch)
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **vue-tsc:** canonical type gate. Run `pnpm typecheck` before pushing. Strict mode on.
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

Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` + `en-US.ts`, use `t('key')` in Vue file, run `pnpm typecheck`. See section keys in `zh-CN.ts` for organization.

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

## Display Configuration

Two user-configurable preferences, both persisted to `localStorage` and applied via singleton composables. Source UI: `ChildHomePage.vue` settings section. Read preferences via `useLocale()` / `useDarkMode()` — never `localStorage.getItem` directly.

### i18n (`src/utils/locale.ts` + `src/i18n/locales/{zh-CN,en-US}.ts`)

- Every string goes through `t('key')` — including template ternaries and date formatters.
- Arrays of `t()` labels must be `computed()`; otherwise labels freeze at setup time.
- Date formatting uses `locale.value`, never literal `'zh-CN'`.
- localStorage key is `child:locale` (namespaced — do not collide with main app).
- `zh-CN.ts` and `en-US.ts` must stay in lockstep.

### Dark/Light mode (`src/utils/darkMode.ts` + `src/assets/clay.css`)

- Use CSS variables from `clay.css` — never hardcode colors. Key tokens: `--color-canvas`, `--color-surface-soft`, `--color-surface-card`, `--color-ink`, `--color-body`, `--color-muted`, `--color-hairline`, `--color-primary`, `--color-on-primary`.
- Dark mode primary is ochre (`#e8b94a`); elements using `var(--color-primary)` adapt automatically.
- Feature-card dark text uses `--color-on-feature-*` tokens.
- Dark mode overrides live in `clay.css`'s `[data-theme="dark"]` blocks (one for tokens, one for Vant). Do not introduce `@media (prefers-color-scheme: dark)` in components.
- Smooth theme transition is global in `clay.css` — don't add per-component overrides.
- Canvas is `#fffaf0` (warm cream), not `#ffffff`.
- Test both light and dark before reporting done.

When you need a token that doesn't exist yet, add it to `clay.css` under both `:root` and `[data-theme="dark"]`.

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
