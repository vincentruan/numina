---
date: 2026-05-31
topic: child-experience-enhancement
source: 2026-04-17-family-asset-enhancement-ideation.md (#1), child-ui-interaction-ideas.md (#10)
---

# 儿童体验增强：任务优先首页 + 温暖空状态

## Summary

将儿童首页英雄区从余额展示改为任务进度环（行动优先于结果），并为 5 个空状态场景添加 SVG 插画 + 鼓励文案，提升 4-12 岁儿童的情感连接和使用动力。

---

## Problem Frame

儿童端存在两个体验问题：

1. **首页信息层级倒置** — ChildHomePage 英雄区展示余额数字（CoinDisplay 组件），但孩子打开 app 的核心动机是"完成任务赚币"而非"查余额"。行动（任务）应比结果（余额）更突出。
2. **空状态冷漠** — 当没有任务/心愿时，页面仅显示纯文字提示（如 `home.noTasks: "今天没有任务，好好休息吧！"`），对 4-12 岁儿童缺乏情感连接和鼓励。现有 ChildWishesPage 的空状态仅用 emoji + 文字，无插画。

---

## Requirements

**任务优先首页（Part A）**

- R1. ChildHomePage 英雄区改为"今日任务完成环"：圆形进度条显示 `completed / total`
- R2. 进度环中心显示今日可获得的总星星币数（所有任务的 `coin_reward + streak_bonus` 之和）
- R3. 余额降级为进度环下方副标题：`⭐ 当前余额: {balance}`
- R4. 所有任务完成（status 为 `approved`）后，英雄区切换为庆祝状态（复用现有 CelebrationAnimation 组件的视觉效果）
- R5. 数据来源：复用现有 `todayChores` 数据（已在 `onMounted` 中加载），无需新 API
- R6. 进度环组件使用 CSS conic-gradient 或 SVG arc，不引入新图表库
- R7. 进度环加载态：在 `loadingChores` 为 true 时显示骨架环（灰色静态环），避免布局跳动
- R8. 进度环需提供 ARIA 属性（`role="progressbar"`, `aria-valuenow`, `aria-valuemax`）以支持无障碍访问
- R9. 进度环动画需尊重 `useReducedMotion` 偏好：reduced-motion 时跳过过渡动画，直接显示最终状态
- R10. "已完成"的定义：status 为 `approved` 的任务计为已完成；`pending_approval` 在进度环中显示为"待确认"状态（视觉上区分于未完成和已完成）
- R10a. 进度环三色弧段方案：`--color-brand-ochre`（金色）= 已完成，`--color-brand-teal`（青色）= 待确认，`--color-neutral-200`（浅灰）= 未完成
- R11. 深色模式下进度环颜色使用 Clay CSS 变量，确保对比度达标

**温暖空状态（Part B）**

- R12. 定义 5 个空状态场景，区分"无任务分配"和"全部完成"两种不同语义：
  - 无今日任务（未分配）
  - 全部完成（庆祝后回落态）
  - 无心愿
  - 无宝贝
  - 无账本记录
- R13. 每个空状态包含：
  - 一个 SVG 插画（简笔画风格，与 Clay 设计系统色调一致：cream/pink/ochre/teal）
  - 一句鼓励文案（i18n key）
  - 一个行动按钮（按钮文案也通过 i18n），按钮导航目标：
    - 无任务 → 无按钮（孩子无法自行创建任务）
    - 全部完成 → 无按钮或"查看心愿"导航到心愿页
    - 无心愿 → 导航到创建心愿页
    - 无宝贝 → 导航到心愿页（引导完成心愿）
    - 无记录 → 导航到任务页
- R14. 空状态文案需区分语义：
  - 无任务（未分配）："今天没有任务，好好休息吧 🌟"（保持现有语义）
  - 全部完成（R4 庆祝后回落）："今天的任务都完成啦！太棒了 🎉"
  - 无心愿："许个心愿吧，努力就能实现！✨"
  - 无宝贝："完成心愿后，宝贝会出现在这里 🎁"
  - 无记录："开始做任务，星星币就会到账 💫"
- R15. 插画尺寸：120x120px，居中显示，下方文案 + 按钮
- R16. 所有文案通过 i18n 引用（zh-CN.ts + en-US.ts 同步更新）
- R17. SVG 插画需支持深色模式（通过 `currentColor` 或 CSS 变量适配）
- R18. 空状态组件可复用：抽取为通用 `EmptyState` 组件，接受 illustration/text/action props

---

## Acceptance Examples

- AE1. **Covers R1, R2, R10.** 今日有 3 个任务，1 个 approved、1 个 pending_approval、1 个 available → 进度环显示 1/3 完成，pending 部分用不同颜色标识，中心显示总可得星星币数。
- AE2. **Covers R4, R14.** 今日 3 个任务全部 approved → 英雄区播放庆祝动画，动画结束后显示"全部完成"空状态（插画 + "今天的任务都完成啦！太棒了 🎉"）。
- AE3. **Covers R7, R9.** 页面加载中 → 显示灰色骨架环；用户开启 reduced-motion → 进度环无过渡动画，庆祝状态降级为静态展示。
- AE4. **Covers R12, R14.** 今日无任务分配（todayChores 为空数组）→ 显示"无任务"空状态插画 + "今天没有任务，好好休息吧 🌟"，而非进度环。

---

## Success Criteria

- 儿童首页英雄区显示任务进度环而非余额
- 全部任务完成后显示庆祝状态 + 温暖回落
- 5 个空状态场景有 SVG 插画 + 鼓励文案 + 行动按钮
- 无硬编码中文字符串（所有文案通过 i18n）
- 深色模式下所有新增 UI 元素正常显示
- 进度环通过基本无障碍检查（ARIA progressbar）
- reduced-motion 用户不会看到突兀动画

---

## Scope Boundaries

- Swipe-to-Complete 手势（已在 completion-experience bundle 中规划）
- Sound & Haptic 反馈层（同上）
- "My Room" 空间隐喻首页（大改版方向，后续迭代）
- 进度环的微交互动画（如弹性效果、粒子）— 保持简洁，后续可增强
- 替换 ChildWishesPage 现有空状态 — 本次仅新增 EmptyState 组件，现有页面迁移为后续任务

---

## Key Decisions

- **进度环"完成"定义为 `approved` 而非 `pending_approval`**：因为 pending 状态的任务尚未被家长确认，从孩子视角"做完了但还没拿到奖励"，应视觉区分而非计为完成。
- **复用 CelebrationAnimation 而非 MilestoneCelebration**：ChildHomePage 已引入 CelebrationAnimation 组件，MilestoneCelebration 仅在 ChildTasksPage 使用，保持组件职责一致。
- **空状态抽取为通用组件**：避免 4 个页面各自实现，统一视觉规范和维护成本。
- **"无任务"与"全部完成"区分为两种不同状态**：语义不同（未分配 vs 已完成），文案和情感基调不同（休息 vs 庆祝）。

---

## Dependencies / Assumptions

- 现有 `todayChores` API 返回的 `status` 字段包含 `approved` / `pending_approval` / `available` 状态（已验证）
- CelebrationAnimation 组件可通过 props 控制触发（已验证：接受 `visible`, `taskCount`, `starsEarned` props）
- SVG 插画需要设计产出（5 张简笔画），可先用 placeholder 开发
- Clay 设计系统 CSS 变量已覆盖深色模式（已验证：`clay.css` 有 `[data-theme="dark"]` 块）

---

## Outstanding Questions

### Deferred to Planning

- [Affects R10][Technical] `pending_approval` 状态在进度环中的视觉表现具体用什么颜色/样式？需要与 Clay 设计系统协调
- [Affects R15][Needs research] SVG 插画是否需要动画（如轻微浮动），还是纯静态？需权衡性能和体验
- [Affects R18][Technical] EmptyState 通用组件的 API 设计（props 结构）在实现时确定
