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

#### 🌙 暗黑模式视觉规范 (HIG → Clay warm-throughout)

Clay 暗黑沿用日间的 warm 基调 — **禁止纯白 `#FFFFFF` / 冷灰**，会破坏品牌声音。
HIG 标准映射到 Clay 现有暖调 token：

1. **多色卡片** — 不要平铺纯灰，也不要直接复用日间品牌色。底层 `var(--color-surface-card)`
   (`#152828` 暖深青)，叠 `rgba(var(--color-brand-X-rgb), 0.14)` 双层 linear-gradient
   (高光 0.16 + 阴影 0.08)。alpha 上限 0.18。`brand-X-rgb` 是与 `brand-X` 配对的 RGB 三元组 token，
   只在 `:root` 定义，dark 不需复盖。参考实现：`ChildHomePage` (.hero-card, ochre)、
   `ChildLedgerPage` (.balance-card, teal→mint 提亮)、`ChildTasksPage` (.balance-card, ochre+peach)、
   `ChildTreasuresPage` (.summary-card, lavender)。新卡片统一走此模式。
2. **主文本** — `var(--color-ink)` (`#f0ece0` 暖米白，对 `#0a1a1a` ≈ 14.6:1，AAA)。
   切勿替换为 `#FFFFFF`；DESIGN.md 的 warm-throughout 优先于 HIG 字面值。
3. **次级标签** — `var(--color-body)` (`#c0bcb0`) 即 Clay 的 secondary-label 等价物，
   不要硬编码 `rgba(255,255,255,0.55)`（冷调，破暖）。
4. **语义高亮 / feature card** — 卡内文字优先用 `--color-on-feature-{pink,teal,lavender,peach,ochre}`
   （已按底色调过、AA 达标）。`var(--color-primary)` 暗黑下 = ochre `#e8b94a`，自动适配，勿另立。
   注意：`--color-on-feature-pink` 在暗黑下取暖白 `#fff4ec`（与同色 brand-pink `#a82960` 配对，AAA 7.8:1）；
   日间维持 `var(--color-on-primary)` (`#ffffff`)。修改时务必同步校验对比度。

**Token 双向定义铁律**：新加 token 必须在 `:root` 与 `[data-theme="dark"]` 双向赋值，否则光照模式静默失效。
`--color-on-feature-*`、`--color-cost`、`--color-brand-X-rgb` 等都遵守此铁律。

**红线 1**：themable 元素禁止静态 `style="background:..."` / `style="color:..."`。inline 特异性 (1,0,0,0) 静默压过所有 `[data-theme="dark"]` 规则。

**红线 2**：组件级 `[data-theme="dark"]` 不要再写新的颜色字面量；消费 token，token 缺就先补到 `clay.css` 双向定义。

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
