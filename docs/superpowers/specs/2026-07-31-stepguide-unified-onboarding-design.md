---
date: 2026-07-31
module: frontend (main + child)
problem_type: feature-design
applies_when: 实现新用户引导和各模块可发现性引导时参考
tags: [onboarding, step-guide, feature-hint, gesture-hint, a11y, i18n]
sources:
  - docs/brainstorms/2026-05-31-mobile-ux-accessibility-requirements.md (Part B)
  - docs/plans/2026-07-24-002-feat-finance-page-ux-optimization-plan.md (R7 deferred)
  - docs/design/family-manifesto-deferred-items.md
---

# StepGuide 统一引导系统 — 设计规格

> **状态**：待实现
> **日期**：2026-07-31
> **来源文档**：531 移动端 UX 需求（Part B）、724 财务页 UX 优化（R7 deferred swipe 提示）、730 manifesto deferred items 分析

---

## 1. 背景与目标

### 问题

Numina 经过多次改版（财务 hub 合并、导航 6→5 tabs、Dashboard 重构），现有引导系统已失效：

1. **OnboardingOverlay 选择器失效** — 现有组件 (`OnboardingOverlay.vue`) 的 Step 2 指向 `.fab`（Dashboard 已无 FAB），Step 3 指向 `[data-tabbar-settings]`（TabBar 无此属性）
2. **各模块无可发现性引导** — FinanceHub 的 long-press/swipe 操作、AI 教练入口、设置页邀请家人等功能，新用户无法自行发现
3. **Child app 无引导** — 儿童端从未有过 onboarding

### 目标

构建统一的 **StepGuide 引导系统**，覆盖三个引导模式：

| 模式 | 用途 | 视觉 |
|------|------|------|
| `spotlight` | 首次 onboarding | 全屏遮罩 + 高亮目标元素 + tooltip card |
| `tooltip` | 模块首次进入提示 | 目标元素旁浮层气泡，无遮罩，3s 自动消失 |
| `gesture-hint` | 可发现性动画引导 | 目标元素自动微滑回弹/pulse，无遮罩，一次性 |

---

## 2. 架构设计

### 2.1 核心 composable：`useStepGuide`

```ts
// frontend/apps/main/src/composables/useStepGuide.ts
// frontend/apps/child/src/composables/useStepGuide.ts (child 版本，使用 child 设计变量)

interface StepGuideStep {
  selector: string          // CSS 选择器，定位目标元素
  mode: 'spotlight' | 'tooltip' | 'gesture-hint'
  title?: string            // i18n key，spotlight/tooltip 模式必填
  desc?: string             // i18n key，spotlight/tooltip 模式必填
  gestureType?: 'swipe-left' | 'long-press-pulse'  // gesture-hint 模式必填
  duration?: number         // tooltip/gesture-hint 自动消失时间(ms)，默认 3000
}

interface UseStepGuideOptions {
  key: string               // localStorage 唯一标识，命名: guide_<context>
  steps: StepGuideStep[]
  onComplete?: () => void
  onSkip?: () => void
}

interface UseStepGuideReturn {
  isActive: Ref<boolean>    // 当前是否有引导在进行
  currentStep: Ref<number>  // 当前步骤索引
  start: () => void         // 手动启动引导
  skip: () => void          // 跳过引导
  complete: () => void      // 完成引导
  next: () => void          // 下一步
}
```

**持久化**：
- localStorage key 统一前缀 `guide_`（如 `guide_main-onboarding-v2`）
- 值为 `'done'` 表示已完成
- `start()` 前检查 key，已 done 则不启动

**手势引导独立调用**（不走 step 流程）：

```ts
// frontend/apps/main/src/composables/useGestureHint.ts
interface UseGestureHintOptions {
  target: string            // CSS 选择器
  type: 'swipe-left' | 'long-press-pulse'
  autoPlay?: number         // 自动播放延迟(ms)，默认 800
}

const { played } = useGestureHint('asset-longpress', {
  target: '.asset-list-item:first-child',
  type: 'long-press-pulse',
})
// 内部: 检查 localStorage('gesture_asset-longpress') !== 'done'
// 首次进入 → 播放动画 → 标记 done
```

### 2.2 组件：`StepGuideOverlay`

替换现有 `OnboardingOverlay.vue`，支持 spotlight/tooltip 两种模式的渲染：

```
StepGuideOverlay.vue
├── SVG spotlight mask (spotlight 模式)
│   ├── 全屏半透明遮罩
│   └── 目标元素区域挖空
├── Tooltip card (spotlight/tooltip 模式)
│   ├── 步骤指示点 (dots)
│   ├── 标题 + 描述 (i18n)
│   └── 操作按钮 (跳过/下一步/完成)
└── 动画层 (gesture-hint 模式)
    ├── swipe-left: translateX 微滑 20px + 回弹
    └── long-press-pulse: border 闪烁 2 次
```

**关键约束**：
- 使用 Teleport 到 body，避免 z-index 层叠问题
- spotlight 定位基于 `getBoundingClientRect()` 动态计算
- tooltip 位置自动避让视口边界（优先下方，空间不足则上方）
- 动画过渡 `transition: top 0.25s ease, left 0.25s ease`

### 2.3 文件结构

```
frontend/apps/main/src/
├── composables/
│   ├── useStepGuide.ts         # 核心 composable
│   └── useGestureHint.ts       # 手势引导 composable
├── components/common/
│   └── StepGuideOverlay.vue    # 统一引导组件 (替换 OnboardingOverlay.vue)
└── utils/
    └── storage.ts              # 新增 guide storage helpers

frontend/apps/child/src/
├── composables/
│   └── useStepGuide.ts         # child 版本 (复用逻辑，使用 child CSS 变量)
└── components/common/
    └── StepGuideOverlay.vue    # child 版本 (clay.css 风格)
```

---

## 3. Main App 引导定义

### 3.1 Dashboard 首次引导 (spotlight)

**Key**: `guide_main-onboarding-v2`
**触发条件**:
- `localStorage.getItem('guide_main-onboarding-v2') !== 'done'`
- 当前路由为 Dashboard (`/`)
- 旧 key 兼容：若 `localStorage.getItem('onboarding_completed') === 'true'`，直接标记 `guide_main-onboarding-v2 = 'done'` 并跳过（老用户不再重新引导）

**自适应选择器**（根据 Dashboard 状态匹配不同 DOM）：

| Step | Selector | Mode | i18n Key | 文案 (zh-CN) |
|------|----------|------|----------|-------------|
| 1 | `.empty-dashboard, .hero-section` | spotlight | `onboarding.step1.*` | 空状态时："欢迎来到 Numina — 这里是你的家庭资产全貌"；有数据时："家庭资产全貌 — 这里展示您家庭的净资产、总资产和总负债" |
| 2 | `[data-tab="finance"]` | spotlight | `onboarding.step2.*` | 管理资产与负债 — 点击这里管理您的资产、负债和心愿 |
| 3 | `[data-tab="settings"]` | spotlight | `onboarding.step3.*` | 邀请家人一起 — 在设置中创建或加入家庭，邀请家人共同管理 |

> **注意**：Step 1 使用逗号选择器，StepGuideOverlay 按顺序尝试，匹配第一个存在的元素。空数据时高亮 `.empty-dashboard`（含"添加第一笔资产"按钮），有数据时高亮 `.hero-section`（OverviewStatCard）。tooltip 文案通过 JS 检测 `overview.asset_count === 0` 动态切换 i18n key。

**交互**：
- 跳过/完成 → `localStorage.setItem('guide_main-onboarding-v2', 'done')`
- Escape 键跳过
- 焦点陷阱：Tab 在"跳过"/"下一步"按钮间循环
- 遮罩点击不关闭引导（防误触）
- 引导期间禁止页面滚动

### 3.2 FinanceHub 手势引导 (gesture-hint)

**资产 long-press 提示**：
- **Key**: `gesture_asset-longpress`
- **目标**: `.asset-list-item:first-child`
- **动画**: `long-press-pulse` — 边框闪烁 2 次（模拟长按效果）
- **触发条件**: 首次进入 assets tab，资产数 > 0
- **文案 tooltip**: "长按资产可快捷操作（编辑/出售/标记闲置）"
- **`prefers-reduced-motion`**: 若用户开启减少动画，跳过动画播放，仅显示 tooltip 文案 3s

**负债 swipe 提示**：
- **Key**: `gesture_liability-swipe`
- **目标**: `.liability-card:first-child`
- **动画**: `swipe-left` — 卡片左滑 20px 后回弹
- **触发条件**: 首次进入 liabilities tab，负债数 > 0
- **文案 tooltip**: "左滑负债卡片可删除"
- **`prefers-reduced-motion`**: 同上，跳过动画仅显示 tooltip

### 3.3 模块首次提示 (tooltip)

**AI Hub 首次进入**：
- **Key**: `tip_ai-first`
- **位置**: AI Hub 页顶
- **文案**: "AI 教练随时为您解答财务问题"
- **触发条件**: 首次进入 `/ai`
- **交互**: 3s 自动消失；点击 tooltip 外部区域立即关闭；tooltip 不阻挡目标元素交互（`pointer-events: none`）

**Settings 邀请提示**：
- **Key**: `tip_settings-invite`
- **位置**: Settings 页顶
- **文案**: "邀请家人加入，一起管理家庭资产"
- **触发条件**: 首次进入 `/settings`，用户为 owner 且家庭无其他成员
- **交互**: 同上，3s 自动消失 + 点击外部关闭 + 不阻挡交互

---

## 4. Child App 引导定义

### 4.1 Child 首次引导 (spotlight)

**Key**: `guide_child-onboarding-v1`
**触发条件**:
- `localStorage.getItem('guide_child-onboarding-v1') !== 'done'`
- 当前路由为 child 任务列表页（ChildTasksPage）
- 无条件判断（所有孩子用户都需要引导，不论任务数）

**约束**：child 引导限制在单页内（ChildTasksPage），不跨路由到 ChildWishesPage。

| Step | Selector | Mode | i18n Key | 文案 (zh-CN) |
|------|----------|------|----------|-------------|
| 1 | `.chore-list, .empty-state` | spotlight | `childOnboarding.step1.*` | 有任务时："这是你的任务列表 — 完成家务就能获得奖励"；无任务时："这里会显示你的家务任务 — 完成后就能获得奖励" |
| 2 | `[data-child-tab="wishes"], .empty-state:last-of-type` | spotlight | `childOnboarding.step2.*` | 引导查看底部的心愿入口区域（若 ChildTasksPage 有心愿导航 tab）；否则改为引导滚动到底部"我的奖励"区域 |

> **注意**：Step 2 不使用 `.wish-card`（该元素在 ChildWishesPage，spotlight 无法跨页定位）。改为定位 ChildTasksPage 内的导航入口或奖励展示区域。实现时需确认 ChildTasksPage 当前是否有心愿/奖励入口元素，若无需新增一个。

**视觉风格**：
- 使用 child app 的 CSS 变量（clay.css 风格）
- 遮罩色: `rgba(0, 0, 0, 0.6)`
- Tooltip 圆角更大（16px），按钮用 child 主色调
- 字体略大（面向儿童可读性）

---

## 5. AppTabBar 改造

为 AppTabBar 各项新增 `data-tab` 属性，供引导选择器定位：

```html
<van-tabbar-item name="dashboard" data-tab="dashboard" icon="chart-trending-o">
<van-tabbar-item name="finance" data-tab="finance" icon="balance-o">
<van-tabbar-item name="ai" data-tab="ai" :aria-label="t('settings.aiAssistant')">
<van-tabbar-item v-if="isOwner" name="baby" data-tab="baby" icon="friends-o">
<van-tabbar-item name="settings" data-tab="settings" icon="setting-o">
```

完整映射表：

| Tab name | data-tab 值 | 引导选择器 | 备注 |
|----------|------------|-----------|------|
| dashboard | `data-tab="dashboard"` | — | 当前页，不作为引导目标 |
| finance | `data-tab="finance"` | `[data-tab="finance"]` | Step 2 目标 |
| ai | `data-tab="ai"` | — | 暂无引导目标 |
| baby | `data-tab="baby"` | — | 仅 owner 可见 |
| settings | `data-tab="settings"` | `[data-tab="settings"]` | Step 3 目标 |

---

## 6. 设置页"重置引导"入口

**位置**: Settings 页底部，"关于"分组上方

**UI**:
```html
<van-cell
  :title="t('settings.replayOnboarding')"
  is-link
  @click="onReplayOnboarding"
/>
```

**行为**:
1. 清除所有 `guide_*` 和 `gesture_*` 和 `tip_*` localStorage keys
2. 跳转 Dashboard（`router.push('/')`）
3. Dashboard 的 `maybeShowOnboarding()` 检测到 key 已清除 → 触发 onboarding

**i18n keys**:
- zh-CN: `settings.replayOnboarding: '重新播放新手引导'`
- en-US: `settings.replayOnboarding: 'Replay onboarding'`

---

## 7. 持久化命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `guide_` | spotlight 引导完成标记 | `guide_main-onboarding-v2` |
| `gesture_` | gesture-hint 已播放标记 | `gesture_asset-longpress` |
| `tip_` | tooltip 提示已显示标记 | `tip_ai-first` |

**清理辅助函数** (`utils/storage.ts`):
```ts
export function clearAllGuideKeys(): void {
  const keysToRemove = Object.keys(localStorage).filter(
    k => k.startsWith('guide_') || k.startsWith('gesture_') || k.startsWith('tip_')
  )
  keysToRemove.forEach(k => localStorage.removeItem(k))
  // 兼容旧版: 清除 531 文档遗留的 key
  localStorage.removeItem('onboarding_completed')
}
```

**旧 key 迁移**（在 `maybeShowOnboarding()` 中）：
```ts
// 若用户已有旧版引导完成标记，直接标记新版完成
if (localStorage.getItem('onboarding_completed') === 'true') {
  localStorage.setItem('guide_main-onboarding-v2', 'done')
}
```

---

## 8. 无障碍要求

所有引导模式必须满足：

- **焦点陷阱** (spotlight 模式): Tab 键只在"跳过"/"下一步"按钮间循环
- **Escape 跳过**: 按 Escape 等同点击"跳过"
- **aria-live**: 步骤切换时通过 `aria-live="polite"` 播报当前步骤文案
- **键盘可达**: 所有按钮 `min-height: 44px`，`:focus-visible` 样式正常
- **屏幕阅读器**: overlay `role="dialog"` + `aria-modal="true"` + `aria-label` 指向当前步骤标题

---

## 9. 国际化要求

所有文案使用 i18n key，zh-CN 和 en-US lockstep：

```ts
// zh-CN.ts
onboarding: {
  step1: {
    empty: { title: '欢迎来到 Numina', desc: '这里是你的家庭资产全貌' },
    data: { title: '家庭资产全貌', desc: '这里展示您家庭的净资产、总资产和总负债' },
  },
  step2: { title: '管理资产与负债', desc: '点击这里管理您的资产、负债和心愿' },
  step3: { title: '邀请家人一起', desc: '在设置中创建或加入家庭，邀请家人共同管理' },
  skip: '跳过',
  next: '下一步',
  done: '完成',
},
childOnboarding: {
  step1: {
    empty: { title: '你的家务任务', desc: '这里会显示你的家务任务，完成后就能获得奖励' },
    data: { title: '你的任务列表', desc: '完成家务就能获得奖励' },
  },
  step2: { title: '我的奖励', desc: '积攒奖励，兑换心愿' },
},
featureHints: {
  assetLongPress: '长按资产可快捷操作（编辑/出售/标记闲置）',
  liabilitySwipe: '左滑负债卡片可删除',
  aiFirst: 'AI 教练随时为您解答财务问题',
  settingsInvite: '邀请家人加入，一起管理家庭资产',
},
settings: {
  replayOnboarding: '重新播放新手引导',
},
```

> **注意**：使用新的 `step1.empty` / `step1.data` 结构支持自适应文案（P0 修复）。旧 `onboarding.step1.title` / `onboarding.step1.desc` 键被替换，实现时需同步清理旧 key。`featureHints.assetSwipe` 重命名为 `assetLongPress` 以匹配实际动画类型 `long-press-pulse`。

---

## 10. 暗色模式适配

- spotlight 遮罩: `rgba(1, 1, 32, 0.72)` (沿用现有)
- tooltip card: `background: var(--card-bg)` + `border: var(--color-card-border)`
- 按钮: primary 用 `var(--van-primary-color)`，ghost 用 `var(--text-secondary)`
- dark override: `[data-theme='dark']` 选择器下调整对比度

---

## 11. 边界情况

| 场景 | 行为 |
|------|------|
| 老用户清除 localStorage | 旧 `onboarding_completed` 迁移逻辑阻止重新引导（标记 `guide_* = done`）|
| 引导中途导航离开 | overlay 随组件销毁；下次回来若 key 未标记 done 则重新从 Step 1 开始 |
| 目标元素不存在（DOM 未渲染） | spotlight 降级为居中 tooltip（沿用现有 `positionTooltipCenter()` 逻辑） |
| 窗口 resize | spotlight 位置实时更新（`resize` listener + `getBoundingClientRect`） |
| 家庭邀请提示条件不满足 | 非 owner 或已有家庭成员时不触发 `tip_settings-invite` |
| 手势引导目标为空列表 | 列表为空时不触发 gesture-hint（仅在有数据时引导） |
| `prefers-reduced-motion` 开启 | gesture-hint 跳过动画，仅显示 tooltip 文案 3s |
| tooltip 自动消失中用户点击 | 点击 tooltip 外部区域立即关闭（`pointer-events: none` 不阻挡目标交互） |
| 新旧 i18n key 共存 | 实现时清理旧 `onboarding.step1.title`/`desc` 平铺 key，替换为 `step1.empty.*`/`step1.data.*` 结构 |

---

## 12. 不做的事

- **引导完成率埋点** — 后续迭代
- **引导 A/B 测试** — 不需要
- **多语言引导语音播报** — 超出范围
- **Child 手势引导** — child 交互模式不同，暂不需要

---

## 13. 实现依赖

- **无新依赖**：复用 Vue 3 内置（Teleport, computed, watch）+ 现有 CSS 变量
- **删除旧组件**：实现完成后删除 `OnboardingOverlay.vue`，替换为 `StepGuideOverlay.vue`
- **旧 key 兼容**：`clearAllGuideKeys()` 同时清除旧的 `onboarding_completed` key

---

## 14. 验收标准

- [ ] 新注册用户首次进入空 Dashboard 看到 3 步 spotlight 引导，Step 1 高亮 `.empty-dashboard`
- [ ] 老用户（已有资产）首次触发引导时，Step 1 高亮 `.hero-section`（两种状态均正确）
- [ ] 引导选择器正确高亮 `[data-tab="finance"]` / `[data-tab="settings"]`
- [ ] 通过邀请码加入的新成员首次进入 Dashboard 看到引导
- [ ] 引导完成/跳过后不再出现（刷新页面验证）
- [ ] 老用户（有旧 `onboarding_completed` key）不会重新触发引导（迁移逻辑验证）
- [ ] FinanceHub assets tab 首次进入：第一项资产出现 long-press pulse 动画 + tooltip（`prefers-reduced-motion` 开启时仅 tooltip）
- [ ] FinanceHub liabilities tab 首次进入：第一项负债出现 swipe-left 回弹 + tooltip（`prefers-reduced-motion` 开启时仅 tooltip）
- [ ] AI Hub 首次进入：顶部 tooltip 提示，3s 自动消失或点击外部关闭
- [ ] Settings 首次进入（owner + 无家庭成员）：顶部 tooltip 提示，3s 自动消失或点击外部关闭
- [ ] Child app 首次进入：2 步 spotlight 引导在 ChildTasksPage 内完成，不跨页
- [ ] Settings "重新播放引导"：清除所有 key → 跳转 Dashboard → 重新触发引导
- [ ] 引导文案通过 i18n 引用，无硬编码中文，zh-CN 和 en-US 同步
- [ ] 引导在 dark mode 下视觉正常
- [ ] 引导支持键盘导航（Tab 循环、Escape 跳过）
- [ ] 所有引导在 375px 和 414px 屏幕宽度下定位正确
- [ ] typecheck 0 errors, vitest 通过
