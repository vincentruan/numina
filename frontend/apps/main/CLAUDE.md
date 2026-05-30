# frontend/CLAUDE.md

Module-specific guidance for the Vue 3 + TypeScript frontend.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `frontend/apps/main/`:

```bash
pnpm dev          # Vite dev server — http://localhost:5173, hot reload
pnpm lint          # ESLint — check for errors and warnings
pnpm lint:fix      # ESLint — auto-fix where possible
pnpm format        # Prettier — format all files in src/
pnpm typecheck     # vue-tsc --noEmit — type check without building
pnpm build         # vue-tsc -b && vite build — full production build
pnpm test:run      # vitest run — run tests once (no watch)
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **Prettier:** config at `.prettierrc`. Single quotes, no semicolons, trailing commas, 100-char width.
- **vue-tsc:** canonical type gate. Run `pnpm typecheck` before pushing. Strict mode is on (`tsconfig.app.json`).
- **vitest:** test runner. Tests live in `src/**/*.test.ts` or `src/**/*.spec.ts`.

## Directory Structure

```
src/
├── api/           # HTTP request modules
├── assets/        # Static assets bundled by Vite
├── components/    # Reusable Vue components (ai/, asset/, charts/, common/, etc.)
├── composables/   # Vue composition functions
├── constants/     # Static constants
├── i18n/          # Localization (zh-CN.ts, en-US.ts)
├── layouts/       # Layout wrappers
├── pages/         # Route-level views (DashboardPage, AssetListPage, etc.)
├── plugins/       # Vite/Vue plugin wiring (loading, etc.)
├── router/        # Vue Router config
├── stores/        # Pinia state stores
├── types/         # TypeScript type definitions
└── utils/         # Helper functions
```

## Workspace Dependencies

Imports come from two shared packages under `frontend/packages/`:

| Package | Purpose |
|---------|---------|
| `@numina/auth` | Auth store (`useAuthStore`), trusted-device card, login form, axios wiring (`configureAuthHttp`), loading overlay |
| `@numina/math` | Pure cross-wish reachability + opportunity-cost math. Same exports the child app uses — both apps must produce identical results |

Always import from the package root (`import { useAuthStore } from '@numina/auth'`). Do not reach into `@numina/auth/src/...`.

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

Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` + `en-US.ts`, use `t('key')` in Vue file, run `pnpm typecheck`.

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

## Display Configuration

Three user preferences. Language and theme mode are persisted server-side on `User` and applied via `App.vue` watchers; theme color is persisted in `localStorage`. Source UI: `SettingsPage.vue`. Read via `authStore.user` (language/theme) or `localStorage` (theme color) — never call the API directly.

### i18n (`App.vue` watches `authStore.user?.language`)

- Every string goes through `t('key')` — including template ternaries and `toLocaleDateString()` calls.
- Arrays of `t()` labels must be `computed()`; otherwise labels freeze at setup time.
- Date formatting uses `locale.value` from `useI18n()`, never literal `'zh-CN'`.
- Language option labels use self-identifying names identical in both locale files (`'🇨🇳 中文'`, `'🇺🇸 English'`).
- `zh-CN.ts` and `en-US.ts` must stay in lockstep.

### Dark/Light mode (`App.vue` resolves `User.theme` → `data-theme` attribute)

- Use CSS variables from `src/style.css`. Key tokens: `--bg-primary`, `--bg-secondary`, `--card-bg`, `--text-primary`, `--text-secondary`, `--separator`, `--color-canvas`.
- Dark mode overrides live in `style.css`'s `[data-theme='dark']` block — never `@media (prefers-color-scheme: dark)` in components.
- Vant adapts automatically via `<van-config-provider>` — do not override Vant colors manually.
- Test both modes before reporting done.

#### 🌙 暗黑模式视觉规范 (HIG-aligned, Together AI 系)

四条标准在 token 之外补足"该写成什么样"。WCAG AA (≥4.5:1) 是底线，不是目标。

1. **多色卡片** — 在 `var(--card-bg)` (`#12122a` 深午夜蓝) 之上叠日间语义色的低饱和 tint：
   `linear-gradient(135deg, rgba(<日间色>, 0.14), rgba(<辅色>, 0.08))`，alpha ≤ 0.18。
   `NetWorthCard` / FAB 菜单是参考实现；`AlertCards` / hero 卡的"纯换底"是历史路线，新代码统一走 tint 叠色。
2. **主文本** — 一律 `var(--text-primary)` (`#f5f5f5`)，对齐 DESIGN.md "Pure White on dark"。
   不允许局部硬编码 `#fff` / `#f0f0f0` 等等价值。
3. **次级标签** — `var(--text-secondary)` (`#c8c8d0`) 优先；卡片内 caption 在 tint 表面上的 alpha **floor 是 0.55**
   （在 `#12122a` + 14% tint 上 ≈ 5:1，AA 余量已经很薄）。`WishDetailPage`/`AssetDetailPage`/`AIHubPage` 的
   α=0.30/0.40/0.45 是已知技术债，新代码勿沿袭。
4. **语义高亮** — 红绿蓝琥珀保留色相家族；暗黑下用"提亮 + 降饱和"变体并校验对比度 ≥4.5:1。
   `var(--van-primary-color)` 在暗黑下被赋为字面量 `#bdbbff`（与日间 `--color-lavender` 同值），勿另立强调色。

**红线 1**：themable 元素禁止静态 `style="background:..."` / `style="color:..."`。inline 特异性 (1,0,0,0) 静默压过所有 `[data-theme='dark']` 规则。
参见 `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`。

**红线 2**：组件级 `[data-theme='dark']` 规则**不要硬编码颜色字面量**（如 `#6ee7a0`、`#fca5a5`）。消费 token；token 缺时按上文规则补到 `style.css`。

### Theme color (`localStorage('theme-primary')` → `--van-primary-color` + `--theme-primary`)

- Interactive elements use `var(--van-primary-color)` — never hardcode primary colors.
- Tinted backgrounds: `rgba(var(--theme-primary-rgb), 0.06)` or `var(--color-soft-stone)`.
- Dark mode overrides `--van-primary-color` to `#bdbbff` (lavender). Respect this — interactive elements adapt automatically.
- Predefined colors (any new addition needs WCAG AA contrast): Blue `#007aff`, Purple `#5856d6`, Indigo `#3634a3`, Orange `#ff9500`, Red `#ff3b30`, Pink `#ff2d55`, Green `#248a3d`, Teal `#0071a4`.

When you need a token that doesn't exist yet, add it to `style.css` in both `:root` and `[data-theme='dark']`.

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
