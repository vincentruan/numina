# frontend/CLAUDE.md

前端 pnpm workspace。继承 root [`CLAUDE.md`](../CLAUDE.md) 项目级约束。

## Workspace Structure

```
frontend/
├── apps/
│   ├── main/      # 成人端 H5 (localhost:5173)
│   └── child/     # 儿童端 H5 (localhost:5174)
├── packages/
│   ├── auth/      # @numina/auth — auth stores, components, axios wiring
│   └── math/      # @numina/math — pure business-logic functions
└── pnpm-workspace.yaml
```

## Commands

Dev commands 见 root [`CLAUDE.md`](../CLAUDE.md) §Development Commands。Workspace-wide:

```bash
pnpm -r lint && pnpm -r typecheck && pnpm -r test:run
```

## Technology Stack

(root 已述: Vue 3 + TS + Vite + Vant 4 + ECharts)

| 技术 | 约束 |
|------|------|
| Vue | `<script setup lang="ts">` only，禁止 Options API |
| Type | 禁止 `any`/`@ts-ignore`/`@ts-expect-error` |
| UI | Vant 4 自动导入，禁止新 UI 库 |
| Icon | Iconify 优先，本地 SVG 补充，禁止新图标库 |
| HTTP | Axios 统一封装 (`src/api/index.ts`)，禁止裸 `fetch`/`axios` |
| State | Pinia，禁止全局变量/localStorage 代替状态管理 |
| Style | CSS 变量 + scoped，禁止固定宽度溢出 |

## Architecture Flow

```
pages/ → stores/ → api/ → backend HTTP
   ↓
components/ (reusable UI, no direct api calls)
```

## Key Invariants

- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`
- **Vant auto-import** — 不手动 import Vant 组件，仅 import functional API (`showToast`, `showDialog`)
- **i18n** — 见 root [`CLAUDE.md`](../CLAUDE.md) §Cross-Cutting Conventions
- **Emoji prefix** — toast/dialog 必须有 emoji (✅❌⚠️🔒🗑️📡🤖🔑💰🎨🔥🎉)
- **Type safety** — 禁止 `any`，接口类型必须显式声明
- **Path alias** — `@/` maps to `src/`

## Vant 4 Patterns

| Need | Use | Not |
|------|-----|-----|
| Card/section | `van-cell-group` | Raw `<div class="card">` |
| List + scroll | `van-list` inside `van-pull-refresh` | Manual scroll listeners |
| Empty state | `EmptyState` component | Bare `van-empty` |
| Loading | `van-skeleton` / `van-loading` | Text "Loading..." |
| Confirm | `showConfirmDialog()` | `van-dialog` component |
| Toast | `showToast()` with i18n key | `van-notify` |
| Picker | `van-field` (readonly, `is-link`) + `van-popup` + `van-picker` | Custom dropdown |

**Gotchas:**
- `van-field`: 用 `:model-value` (not `:value`) in Vant 4
- `van-popup` + picker: 用 `destroy-on-close` reset state
- `van-list` in pull-refresh: `van-list` must be inside, not sibling

## Mobile H5 Patterns

- **KeepAlive**: Tab pages cached via `<KeepAlive :include="cachedTabs">` — `defineOptions({ name: 'Xxx' })` required
- **Refresh**: Use `onActivated` on cached pages, `onMounted` only fires once
- **Safe area**: Bottom handled globally in layout, pages don't add own padding
- **Pull-to-refresh**: All list pages wrap in `van-pull-refresh`
- **Touch targets**: Min 44×44px for all interactive elements

## 模板参考基线

**主模板**: [yulimchen/vue3-h5-template](https://github.com/yulimchen/vue3-h5-template)
**补充模板**: [xiangshu233/vue3-vant4-mobile](https://github.com/xiangshu233/vue3-vant4-mobile)

> **注意**: 模板是"参考"，不是"依赖"。本文件已吸收模板实践，开发时无需读取模板文件。

| 原则 | 说明 |
|------|------|
| 已有优先 | 当前项目已有实现直接复用 |
| 主模板优先 | 补充模板仅用于增强 |
| Vant 优先 | 官方实践 > 个人封装 |
| 简单优先 | 统一/可维护 > 复杂迁移 |

**禁止:** 第二套工程体系、不一致规范混用、不需要的能力强行引入

## ECharts 规范

已有 `vue-echarts` 封装，不引入 useECharts。容器考虑移动尺寸/横竖屏/暗黑；数据转换与渲染分离。

## Dark Mode 规范

CSS 变量实现。main: `van-config-provider`；child: `[data-theme="dark"]` + clay.css。不引入 designSetting store。

## ESLint

ESLint flat config + Prettier。不建议迁移；如需改进可单独引入 lint-staged。

## Development Rules

| 规则 | 说明 |
|------|------|
| 先查后写 | 查 Vant/组件/Iconify/request/结构后再写 |
| 归纳优先 | 从现有代码归纳约定，不臆造 |
| 样式一致 | 确认 CSS 变量选型，无规划不引入 Tailwind |
| 变更说明 | 说明复用/参考/新增/影响 |

**禁止:** 重复实现、技术栈分叉、无规划引入 UI/图标库

### 冲突处理

优先级: 项目已有 > 主模板 > 补充模板 > Vant 官方 > 简单统一

## Links

- [`packages/CLAUDE.md`](packages/CLAUDE.md) — @numina/auth + @numina/math exports
- [`apps/main/CLAUDE.md`](apps/main/CLAUDE.md) — main app 特有配置
- [`apps/child/CLAUDE.md`](apps/child/CLAUDE.md) — child app 特有配置
- Root [`CLAUDE.md`](../CLAUDE.md) — 项目级约束