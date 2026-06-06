# frontend/apps/child/CLAUDE.md

儿童端 H5 应用。继承 [`frontend/CLAUDE.md`](../../CLAUDE.md) 通用约束。

## Commands

`pnpm dev` — http://localhost:5174。其他命令见 parent [`CLAUDE.md`](../../CLAUDE.md)。

## Directory Structure

```
src/
├── api/           # HTTP 请求封装
├── components/    # 通用组件
├── i18n/          # 国际化 (zh-CN.ts, en-US.ts)
├── pages/         # 路由页面
├── router/        # Vue Router
├── stores/        # Pinia stores
├── types/         # TypeScript types
├── utils/         # Helper functions (locale.ts, darkMode.ts)
└── assets/        # clay.css — Clay visual tokens
```

## Vant 4 (Child-Specific)

- **No `<van-config-provider>`** — dark mode via CSS variable overrides in `clay.css`
- **Custom tabbar**: `ChildTabBar` component wraps `van-tabbar`
- **Custom empty**: `EmptyState` component with illustration + action
- Vant components auto-import via `unplugin-vue-components`

### Theme Token Mapping (Clay)

| Clay Token | Vant Variable |
|-----------|---------------|
| `--color-primary` | `--van-primary-color` |
| `--color-ink` | `--van-text-color` |
| `--color-canvas` | `--van-background` |
| `--radius-md` | `--van-radius-md` |

### Gotchas

- **van-list in pull-refresh**: `van-list` must be inside `van-pull-refresh`, not sibling
- **Route cache**: ChildHome, ChildTasks, ChildLedger, ChildWishes, ChildTreasures
- **Canvas warm cream**: `#fffaf0` (light), `#0a1a1a` (dark) — NOT pure white/black

## Dark Mode (Clay Warm-Throughout)

`useDarkMode()` composable + `[data-theme="dark"]` on `<html>` + `clay.css`。

| 规则 | 说明 |
|------|------|
| Warm 基调 | 禁止 `#FFFFFF` / 冷灰 |
| 多色卡片 | `var(--color-surface-card)` 上叠 brand rgba |
| 主文本 | `var(--color-ink)` |

**铁律**: 新 token 必须在 `:root` 和 `[data-theme="dark"]` 双向定义。

## Color Palette (Clay)

| Role | Light | Dark | Token |
|------|-------|------|-------|
| Canvas | `#fffaf0` | `#0a1a1a` | `--color-canvas` |
| Card surface | `#ffffff` | `#152828` | `--color-surface-card` |
| Primary text | `#0a0a0a` | `#f0ece0` | `--color-ink` |
| Secondary text | `#3d3d3d` | `#c0bcb0` | `--color-body` |
| CTA | `#0a0a0a` | `#e8b94a` | `--color-primary` |

## Links

Parent [`CLAUDE.md`](../../CLAUDE.md) — frontend workspace 约束
[`apps/main/CLAUDE.md`](../main/CLAUDE.md) — main app 配置