# frontend/apps/main/CLAUDE.md

成人端 H5 应用。继承 [`frontend/CLAUDE.md`](../../CLAUDE.md) 通用约束。

## Commands

`pnpm dev` — http://localhost:5173。其他命令见 parent [`CLAUDE.md`](../../CLAUDE.md)。

## Directory Structure

```
src/
├── api/           # HTTP 请求封装
├── components/    # 通用组件 (ai/, asset/, charts/, common/)
├── composables/   # Vue composition functions
├── i18n/          # 国际化
├── layouts/       # MainLayout (KeepAlive + transitions)
├── pages/         # 路由页面
├── plugins/       # Vite/Vue plugins
├── router/        # Vue Router
├── stores/        # Pinia stores
├── types/         # TypeScript types
└── utils/         # Helper functions
```

## Vant 4 (Main-Specific)

- Uses `<van-config-provider :theme="resolvedTheme">` for dark mode auto-switch
- Vant components auto-import via `unplugin-vue-components`
- Theme tokens in `src/style.css`

### Theme Token Mapping

| Design Token | Vant Variable |
|-------------|---------------|
| `--van-primary-color` | Primary action color |
| `--van-tabs-bottom-bar-color` | `var(--van-primary-color)` |
| `--van-checkbox-checked-icon-color` | `var(--van-primary-color)` |

### Gotchas

- **No virtual scroll**: Vant `van-list` for infinite scroll; for 1000+ items use `vue-virtual-scroller`
- **Route cache**: Dashboard, FinanceHub, AIHub, Baby, Family, Settings (in `MainLayout.vue`)
- **Finance redirects**: `/assets`, `/liabilities`, `/wishes` routes redirect to `/finance?tab=...` (no standalone list pages)

## Dark Mode (WCAG AA)

`App.vue` 用 `<van-config-provider :theme="resolvedTheme">`。主题色 `localStorage('theme-primary')`。

| 规则 | 说明 |
|------|------|
| 多色卡片 | `var(--card-bg)` 上叠 `rgba(<日间色>, 0.14)` |
| 主文本 | `var(--text-primary)`，禁止 `#fff` |
| 次级标签 | `var(--text-secondary)`，alpha ≥ 0.55 |

**红线**: 禁止 inline `style="color:..."` → 见 `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`

## Color Palette

| Role | Light | Dark | Token |
|------|-------|------|-------|
| Canvas | `#ffffff` | `#010120` | `--bg-primary` |
| Surface | `#f5f5ff` | `#12122a` | `--card-bg` |
| Primary text | `#0a0a0a` | `#f5f5f5` | `--text-primary` |
| Secondary text | `#616161` | `#c8c8d0` | `--text-secondary` |
| CTA | `var(--van-primary-color)` | `#bdbbff` | `--van-primary-color` |

## Links

Parent [`CLAUDE.md`](../../CLAUDE.md) — frontend workspace 约束
[`apps/child/CLAUDE.md`](../child/CLAUDE.md) — child app 配置