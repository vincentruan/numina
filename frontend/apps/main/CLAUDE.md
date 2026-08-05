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

## UI Design Patterns

按页面区域（总览/财务/AI/宝贝/设置）的 Vant 4 组件选择、卡片布局、表单模式、CRUD 交互、DeerFlow 复刻等实践详见 [`docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md`](../../../../docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md)。

**核心约束**: 除 AI 场景外，整体 UI 组件尽量复用 Vant 4。AI 场景使用自定义组件复刻 DeerFlow 交互。

## UI 问题排查指南

遇到以下问题时，参考对应的 solution 文档：

| 问题场景 | 参考文档 |
|---------|---------|
| 深色模式样式不生效 / `!important` 优先级问题 | [`dark-mode-inline-style-specificity`](../../../../docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md) |
| NProgress 进度条闪烁 / 卡住不消失 | [`nprogress-flicker`](../../../../docs/solutions/ui-bugs/nprogress-flicker-page-navigation.md) |
| Vant 4 `van-field` 绑定不生效 / picker 状态问题 | [`vant4-field-binding`](../../../../docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md) |
| Vue 3 Transition + KeepAlive 白屏 / 页面切换问题 | [`user-feedback-branch-fixes`](../../../../docs/solutions/ui-bugs/user-feedback-branch-multi-domain-fixes-2026-08-05.md) (Bug 1, 2, 6, 9) |
| onboarding overlay 阻挡导航 / action-sheet 被裁剪 | 同上 |
| UI 设计模式 / 组件选择 / 卡片布局 | [`main-app-ui-design-patterns`](../../../../docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md) |

## Links

Parent [`CLAUDE.md`](../../CLAUDE.md) — frontend workspace 约束
[`apps/child/CLAUDE.md`](../child/CLAUDE.md) — child app 配置