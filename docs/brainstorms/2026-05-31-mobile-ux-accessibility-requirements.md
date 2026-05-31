---
date: 2026-05-31
topic: mobile-ux-accessibility
source: 2026-04-03-mobile-h5-ui-ux-optimization-ideation.md (Ideas #4, #5)
---

# 移动端 UX 与无障碍优化

## Problem Frame

Numina 移动端存在两个用户体验缺口：

1. **触摸目标过小** — StatusSummaryGrid tabs (`padding: 8px 14px`, `min-height: 36px`)、CategoryGrid items (`padding: 8px 4px`)、UsageFreqSelector items (`padding: 8px 4px`) 均未达 WCAG 2.1 SC 2.5.5 (AAA) 44×44px 标准（注：AA 级 SC 2.5.8 要求 24×24px，本项目以 44px AAA 为目标），手指较大或运动障碍用户难以准确点击
2. **新用户无引导** — 注册后直接跳转空白 Dashboard，无上下文说明如何开始使用，新用户流失风险高

这两个问题一个是无障碍合规底线，一个是新用户留存关键路径。

## Requirements

### Part A: Touch Target 修复

- R1. StatusSummaryGrid `.status-tab`：当前 `padding: 8px 14px` + `min-height: 36px`，通过增加垂直 padding 或 `min-height: 44px` 扩展点击区域至 44×44px，视觉尺寸保持紧凑
- R2. CategoryGrid `.grid-item`：当前 `padding: 8px 4px`，4 列网格布局（`grid-template-columns: repeat(4, 1fr)`），通过增加 padding 使每项实际触摸区域 ≥ 44×44px。注意：在 375px 屏幕宽度下，4 列布局每列约 80px，水平方向天然满足，主要需增加垂直 padding
- R3. UsageFreqSelector `.freq-item`：当前 `padding: 8px 4px`，5 列 flex 布局，同 R2 处理。注意：5 列在 375px 下每列约 63px，水平方向满足 44px，需增加垂直 padding
- R4. FAB 按钮验证：当前 52×52px（已满足 44px），仅验证不改动
- R5. 底部 Tab Bar（`AppTabBar.vue`）验证：使用 Vant `van-tabbar-item`，默认高度 50px，需验证每个 item 的实际可点击宽度（当前 `flex: 1` + `padding: 0 2px`）。注意：Tab 数量因角色而异（owner 显示 6 个 tab，非 owner 显示 5 个），需分别验证两种情况下是否满足 44px 宽度
- R6. FAB 展开菜单项（`.fab-menu-item`）：验证其触摸区域是否满足 44×44px
- R7. 使用 Chrome DevTools "Show tap highlight" 或 Layout > Rendering > "Highlight ad frames" 验证所有交互元素的实际点击区域
- R8. 所有修复需同时在 light mode 和 dark mode 下验证视觉效果
- R9. 确保 `:focus-visible` 样式在所有修改的组件上正常工作（键盘/辅助开关用户）

### Part B: 新用户引导流程

#### 触发条件

- R10. 以下场景首次进入 Dashboard 时触发引导（仅触发一次）：
  - 新注册用户
  - 通过邀请码加入家庭的新成员（同样面对空白 Dashboard）
- R11. 触发判断逻辑：`localStorage.getItem('onboarding_completed') !== 'true'` AND 当前路由为 Dashboard AND Dashboard 资产数为 0（防止老用户清除 localStorage 后误触发）

#### 引导步骤

- R12. 引导分 3 步：
  - Step 1: 高亮 NetWorthCard 区域，说明"这里展示家庭资产全貌"
  - Step 2: 高亮 FAB 按钮（52×52px 圆形，`position: fixed; right: 16px; bottom: 72px`），引导"点击这里添加第一笔资产"
  - Step 3: 高亮底部 Tab Bar 的"设置"项（`van-tabbar-item name="settings"`），说明"在设置中邀请家人一起管理"
- R13. 使用 `van-overlay` + CSS clip-path/box-shadow spotlight 遮罩实现，不引入新依赖
- R14. Spotlight 定位需基于目标元素的 `getBoundingClientRect()` 动态计算，适配不同屏幕尺寸

#### 交互与状态

- R15. 每步有"跳过"和"下一步"按钮，最后一步显示"完成"
- R16. 跳过或完成后均设置 `localStorage.setItem('onboarding_completed', 'true')`，不再显示
- R17. 引导过程中点击遮罩区域（非高亮区域）不关闭引导，防止误触
- R18. 引导过程中禁止页面滚动（`overflow: hidden` on body）

#### 无障碍

- R19. 引导弹层需实现焦点陷阱（focus trap）：Tab 键只在"跳过"/"下一步"按钮间循环
- R20. 每步切换时通过 `aria-live="polite"` 区域播报当前步骤文案
- R21. 支持 Escape 键跳过引导（等同点击"跳过"）

#### 国际化与主题

- R22. 引导文案使用 i18n key，定义在 `zh-CN.ts` 和 `en-US.ts` 中（保持 lockstep）
- R23. 引导 overlay 和按钮样式需适配 dark mode（使用 CSS 变量，遵循 `[data-theme='dark']` 模式）

#### 边界情况

- R24. 如果用户清除 localStorage 但已是老用户（有资产数据），不应重新触发引导（已在 R11 中通过"资产数为 0"条件覆盖）
- R25. 如果引导过程中用户通过浏览器后退/前进离开 Dashboard，引导状态保持（下次回来继续从 Step 1 开始，除非已完成）

## Acceptance Criteria

- [ ] StatusSummaryGrid、CategoryGrid、UsageFreqSelector 所有交互元素点击区域 ≥ 44×44px（DevTools 验证）
- [ ] FAB、Tab Bar、FAB menu items 确认满足 44×44px（验证记录）
- [ ] 新注册用户首次进入 Dashboard 看到引导
- [ ] 通过邀请码加入的新成员首次进入 Dashboard 看到引导
- [ ] 引导完成/跳过后不再出现
- [ ] 老用户清除 localStorage 后不会误触发引导（有资产数据时跳过）
- [ ] 引导文案通过 i18n 引用，无硬编码中文，zh-CN 和 en-US 同步
- [ ] 引导在 dark mode 下视觉正常
- [ ] 引导支持键盘导航（Tab 循环、Escape 跳过）
- [ ] 引导 spotlight 在 375px 和 414px 屏幕宽度下定位正确
- [ ] 所有 touch target 修复在 light/dark mode 下视觉无异常

## Technical Notes

以下为实现参考，不作为硬性约束：

- StatusSummaryGrid 位于 `frontend/apps/main/src/components/dashboard/StatusSummaryGrid.vue`
- CategoryGrid 位于 `frontend/apps/main/src/components/asset/CategoryGrid.vue`
- UsageFreqSelector 位于 `frontend/apps/main/src/components/asset/UsageFreqSelector.vue`
- DashboardPage 位于 `frontend/apps/main/src/pages/DashboardPage.vue`
- AppTabBar 位于 `frontend/apps/main/src/components/common/AppTabBar.vue`
- localStorage 使用模式参考 `frontend/apps/main/src/utils/storage.ts`
- 引导组件建议放在 `frontend/apps/main/src/components/common/` 下

## Out of Scope

- Accessibility labels 全面补充（中等工作量，单独迭代）
- 8dp Spacing Grid System（全局样式重构，单独迭代）
- Skeleton Loading（已在 quick-wins-ux-performance 中覆盖）
- 引导动画/过渡效果优化（基础功能优先，动效后续迭代）
- 多语言引导内容的 A/B 测试
- 引导完成率的埋点统计（可后续添加）
