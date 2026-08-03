---
date: 2026-08-03
module: frontend/apps/main
problem_type: best-practice
tags: [ui, vant4, dashboard, finance, ai-chat, baby, settings, design-patterns]
applies_when: "开发 main app 的 Dashboard/Finance/AI/Baby/Settings 页面时"
---

# Main App UI Design Patterns

从现有代码提炼的 UI 实践指南。除 AI 场景外，整体 UI 组件尽量复用 Vant 4。

## 1. 总览页 (Dashboard)

**页面结构**: `van-pull-refresh` 包裹垂直卡片栈。三态渲染：Skeleton 加载中 → `van-empty` 空态 → 卡片内容。

**卡片容器两种模式**:
- **可折叠卡片**: `van-cell-group inset` + `van-collapse`，自定义 `#title` slot（icon + 标题 + 摘要计数）。用于 SmartRemindersCard、FinanceCoachCard、LiteracyStatusCard、ManifestoDashboardCard、DashboardNarrativeCard。
- **固定卡片**: `div` + `background: var(--card-bg)` + `border-radius: 12px` + `margin: 12px` + `box-shadow: 0 1px 4px rgba(0,0,0,0.06)`。用于 FocusTop3Card、PendingApprovalsSection。

**Hero 卡片 (OverviewStatCard)**: 全宽无边距，`padding: 20px 16px 16px`，大数字 `clamp(28px, 8vw, 36px)`，下方 2×2 grid 子统计（`grid-template-columns: 1fr 1fr`，hairline 分隔，每项 `min-height: 64px`，每个子统计是 `router-link`）。

**卡片自门控**: 卡片内部判断是否可见（如 `v-if="visible"`），页面不做条件渲染。

**卡片间距**: 可折叠卡片 `margin: 8px 0`，固定卡片 `margin: 12px`。

**懒加载**: 折叠卡片数据在首次展开时加载（`onToggle`）。

**交互反馈**: 可点击元素 `:active { transform: scale(0.97) }` + `transition: transform 0.15s ease`。

**图表**: ECharts via `vue-echarts`，高度 200-240px，`autoresize`，暗色模式通过 `MutationObserver` 监听 `data-theme` 切换配色。

## 2. 财务页 (Finance)

**入口**: FinanceHubPage 使用 `van-tabs`（assets/liabilities/wishes），`van-pull-refresh` 在 tab 层级统一包裹。`/assets`、`/liabilities`、`/wishes` 路由重定向到 `/finance?tab=...`。

### 列表模式

**资产列表 (AssetListPanel)**: 多层筛选——StatusSummaryGrid 状态过滤 → `van-tabs` 资产类型 → 可滚动分类 tab → `van-search` + 排序按钮。`van-list` 无限滚动，按分类分组（AssetGroupHeader 可折叠）。双视图模式：卡片 (AssetCard) / 列表 (AssetListItem)，通过 `view-mode-toggle` 切换，用户偏好持久化。

**负债列表 (LiabilityListPanel)**: Active/Inactive tabs → pill 形分类筛选按钮 → 排序按钮（三态循环：默认→desc→asc）。LiabilityCard 使用 `van-swipe-cell`（Pay/Edit/Delete 滑出操作）。长按进入多选模式。

**心愿列表 (WishListPanel)**: Pending/Realized/Cancelled tabs → pill 排序按钮（Priority/Price/Name）。自定义卡片（非 van-cell），左侧优先级色条 4px。每个 tab 有独立 SVG 插画 + `ShimmerText` 空态。

**FAB**: 固定右下角 `+` 按钮，展开菜单（资产有"导入账单"+"添加资产"），有 backdrop overlay。

**跨模块提示**: `useDebtWarning` 检测高息负债影响心愿时，在 tabs 上方显示警告条。

### 表单模式

**页面结构**: `PageHeader`（动态标题）→ 表单组件（接收 `initialData`/`isEdit`/`loading`，emit `@submit`）。页面负责 toast + `router.back()`。

**组件选择**:
| 需求 | 组件 |
|------|------|
| 文本/数字输入 | `van-field` + `rules` 验证 |
| 图片上传 | `van-uploader`（max 1, 5MB） |
| 分类选择 | `van-popup` + 4-column CSS grid（icon + name，选中态 primary border + tinted bg） |
| 日期选择 | `van-popup` + `van-date-picker` |
| 简单选择器 | `van-popup` + `van-picker` |
| 币种选择 | `CurrencyButton` 在 `van-field` 的 `#left-icon` slot |
| 标签选择 | `TagSelector`（支持内联创建） |
| 优先级 | `van-radio-group` horizontal |
| 开关 | `van-switch` |
| 折叠分区 | `van-collapse`（AssetForm 的 Physical/Financial/Warranty/Tags 分区） |

**验证**: `van-form` + `rules` prop，`@failed` 自动展开错误所在折叠区并 focus。

**提交按钮**: 全宽 `van-button round block type="primary" native-type="submit"`，在 `.form-actions { padding: 16px }` 内。

### 详情页模式

**Hero 卡片**: 渐变背景 + 状态 badge + 图标/图片 + 数据行（使用 `MoneyDisplay`）。

**信息分区**: `van-cell-group inset :title="..."` 分组展示基本信息、物理信息、财务信息、标签、备注等。

**操作按钮**: 底部 `.actions` 容器，按钮按状态变化（如 `in_use` → Edit/Sell/Retire/Delete，`retired` → Reactivate/Edit/Delete）。Delete 使用 `showConfirmDialog`。

### CRUD 交互

| 场景 | 模式 |
|------|------|
| 创建/更新成功 | `showSuccessToast(t('toast.addSuccess'))` |
| 操作失败 | `showFailToast(t('toast.operationFailed'))` |
| 删除确认 | `showConfirmDialog({ title, message })` |
| 批量操作/出售 | `BottomSheetConfirm`（底部弹出 + 影响预览） |
| 页面加载 | `usePageLoading` 驱动 NProgress 顶部进度条 |

### 金额显示

- **MoneyDisplay 组件**: 统一金额显示，`size` (small/normal/large)，`showSign`，`colorful`。CNY 用万/亿单位。
- **useCurrency composable**: `format(amount)` 用户默认币种，`formatIn(amount, code)` 指定币种。
- **大数字字体**: 负债使用 `'Crimson Pro', Georgia, serif`。

## 3. AI 页面

> AI 场景是 Vant 4 约束的例外——大量自定义组件复刻 DeerFlow 交互。

**AI Hub**: 问候 + 健康评分 SVG 环 + 统计行 → 报告摘要卡 → Featured Agent (NuminaAgentCard) → My Agents (2-column grid, 可折叠) → Analysis Apps (垂直列表, 可折叠) → InputBox (welcome mode)。

**AI Chat**: AIChatBox 固定全屏（`position: fixed; inset: 0`），三态：Skeleton → WelcomePage → 聊天模式。

### DeerFlow 交互复刻

**消息分组** (6 种类型): `human` → UserBubble | `assistant` → AssistantMessage | `assistant:processing` → ChainOfThought | `assistant:clarification` → HumanInputCard | `assistant:present-files` → ArtifactFileList | `assistant:subagent` → SubtaskCard。

**思维链 (ChainOfThought)**: 步骤类型 `reasoning`/`toolCall`/`leadingContent`。工具调用 icon 通过 `getToolIcon` 映射，垂直连接线（gradient），最后一个工具调用无连接线。可折叠历史步骤（"X more steps"）。工具结果特定渲染：搜索结果 (ChainOfThoughtSearchResults)、代码 (CodeBlock with Shiki)、文件 (artifact link)。

**推理展示**: 可折叠，灯泡 icon + "Thinking..." + `LiveTimer`，自动展开/折叠逻辑。内容降调（`text-secondary`）。

**4 模式选择器 (ModeSelector)**: Flash (indigo) / Thinking (violet) / Pro (teal) / Ultra (gold + pulse ripple)。通过 `visualViewport` 定位弹窗兼容 Safari。

**Markdown 渲染 (MarkdownContent)**: markdown-it + Shiki 双主题代码高亮 + DOMPurify 消毒。表格注入操作栏（复制 markdown、下载 CSV）。引用转 badge 样式 + CitationHoverCard。流式 60ms debounce。

**流式状态**:
- `StreamingDots`：三点弹跳（1s ease-in-out, 0.2s 错开）
- `AiThinkingLabel`：shimmer 扫描动画
- `AiProcessBlock`：phase 状态 `connecting` → `thinking` → `answering` → `done`/`error`，自动展开/折叠

**自动滚动 (MessageList)**: `MutationObserver` + `requestAnimationFrame` + 50ms debounce 捕获异步 DOM 变化。用户上滚暂停 + "回到底部"浮按钮。新消息发送重置滚动。

**SSE 重试**: `SSE_RETRY_DELAYS = [1000, 2000, 4000]` ms + jitter，最多 3 次。

**Token Usage**: 两种模式——Popover (header 汇总) + Inline (per_turn/step_debug)。实时从 SSE 累积，K 后缀，`font-variant-numeric: tabular-nums`。

**澄清交互 (HumanInputCard)**: 支持 `free_text`/`single_choice`/`choice_with_other`。回答作为新 HumanMessage 发送（带 `human_input_response`）。

**报告页**: 三步时间线 (ReportStepTimeline) → SVG 评分环 (120px, animated) → markdown 总结 → 指标卡片（1-5 评分 + 色彩等级）→ 导出 PNG/PDF。

## 4. 宝贝页 (Baby)

**主页结构**: PageHeader → Skeleton → EmptyState → 子选择 tabs（scrollable，每个 tab 显示 22px 彩色圆形头像 + 名字）→ PendingApprovalsSection (owner-only) → 摘要卡 (`van-cell-group inset`) → 内容 tabs (Diary/Wishes/Chores) → 底部弹出层群。

**子选择 tabs**: 首 tab "全部"，后续 per-child，头像用 `avatar_color` 或默认 `#FF6B6B`，显示名字首字。

**摘要卡**: `van-cell-group inset` 多行——余额 (含打赏按钮)、本周家务比、活跃心愿数、盲盒礼物 (link)、盲盒抽取 (link + `van-badge` 待抽数)、家务模板 (link)、识字报告 (link 或 AiGatedInline)。

### 审批模式

**PendingApprovalsSection**: 折叠卡，header 显示 label + 红色 badge 计数 + chevron。每张审批卡：头像 (40px) + 家务信息 + **钢琴键操作按钮**（三等宽，竖线分隔）——Approve (success) / Redo (warning) / Reject (danger)。`actioningId` 期间禁用所有按钮。

**ChoreApprovalsPage**: 独立列表，更大卡片，三个 `van-button`（type="success"/"warning"/"danger"）。

**心愿审批**: pending_review 状态 → Approve + Reject 按钮；redemption_requested → Realize + Defer。Approve 弹出底部表单（金额 + StarCoinSuggestion AI 建议）。Reject 弹出原因输入。

### 卡片设计

**WishCard / ChoreCard**: `background: var(--card-bg)`, `border-radius: 12px`, `padding: 12px`, `box-shadow: var(--shadow-elevated)`。顶部：emoji + name (15px/600) + `van-tag` 状态。Meta 行：金额 (金色 `--color-cost`)、名字、优先级 badge (color-coded pill)。操作按钮：渐变 pill (`linear-gradient(135deg, ...)`)，success/danger/primary/muted 四色。已完成/拒绝：`opacity: 0.75`。

**ChoreTemplate Card**: `var(--van-background-2)` bg, `border-radius: 10px`, `padding: 12px 16px`。状态 tag 绝对定位右上角（可点击切换 active/inactive）。底部钢琴键操作（Edit indigo / Delete red）。

### 表单模式

- **家务创建**: `van-form` + `van-cell-group inset`。字段：名称 (required) + emoji + 奖励 (`type="digit"`) + 频率 (`van-radio-group` horizontal) + 分配类型 + 指派人 (`van-checkbox-group` horizontal) + 真实奖励 (`van-switch`)。
- **盲盒配置**: 自动保存模式——debounce 600ms，`van-slider` + 百分比标签 + 刻度标记。
- **宣言编辑**: `BlockEditor` 组件，每段一个卡片（编号 + trackable toggle + 删除），底部 "添加段落"。

### 特殊交互

**盲盒**: 礼物池管理 (GiftListPage) → 配置页 (概率 slider 自动保存) → 抽取历史 (GiftCard + DrawAnimation)。BabyPage 摘要卡 `van-badge` 显示待抽数。

**宣言签署**: 多步向导 (useManifestoWizard)——模板选择 (2-column grid, 语言渐变) → 编辑 → 预览 → 签署。**双门控**: IntersectionObserver 滚到底部 + 3 秒等待 → SignaturePad (canvas, 速度敏感笔触 1.5-3px)。

**奖励显示**: 统一 `N ⭐` 格式，金色 `var(--color-cost, #f5a623)` + `font-weight: 600`。

## 5. 设置页 (Settings)

**主页结构**: 7 个 `van-cell-group inset :title="..."` 分组——账户信息 / 外观与偏好 / 家庭管理 / 账户安全 / 通知设置 / AI 助手设置 / 数据管理。间距 `.section { margin-top: 12px }`。

**Cell 项模式**:
- 导航项: `van-cell` + `icon` + `is-link` + `to="/path"` + `:value` 当前值
- 开关项: `van-cell center` + `#value` slot 放 `van-switch size="22px"`
- 角色门控: owner-only 项 `v-if="authStore.user?.role === 'owner'"`
- 内联 picker: `van-popup position="bottom"` + `van-picker`

**退出按钮**: 底部全宽 `van-button block type="danger" plain`。

### 列表管理模式（5 种）

| 模式 | 使用场景 | 关键组件 |
|------|----------|----------|
| **滑动操作** | 分类、标签、通知渠道 | `van-swipe-cell` + `#right` (Edit/Delete 按钮) |
| **卡片 + 操作栏** | 家庭成员、AI Provider | 自定义 card + 色文本按钮 (edit #4F46E5 / danger #ee0a24 / warn #ff976a) |
| **Cell + 内联操作** | Agents、Skills、MCPs | `van-cell` + `#value` (switch + delete icon) |
| **拖拽排序** | AI Provider、Web Search | `vuedraggable` + `handle=".drag-handle"` + `@end` 持久化 |
| **分组列表** | Agents (系统/自定义)、Web Search (启用/禁用/未配置) | 多个 `van-cell-group :title` |

**添加按钮 4 种位置**: PageHeader `#right` +plus icon | 页面底部 `van-button block plain icon="plus"` | 固定底栏 | 空态内按钮。

### 表单模式

**验证方式**:
- 常用: `computed canSubmit` + `:disabled="!canSubmit"` 按钮
- 复杂: 手动 check + `showToast`
- 内联: `van-field :error` + error-message
- 对话框: `before-close` hook 阻止关闭

**Picker 三步**: readonly `van-field is-link` → `van-popup position="bottom"` → `van-picker`。

**Slider 自动保存**: debounce 600ms + 刻度标签（0%/50%/100% 或 min/mid/max）。

**底部表单弹窗**: `van-popup position="bottom" round :style="{ height: '75%' }"` + `van-nav-bar` 标题栏 + `van-cell-group inset` 表单区。

**对话框表单**: `van-dialog` + `van-form` + `van-field`，`show-cancel-button` + `@confirm`。

**固定底栏**: `position: fixed; bottom: calc(50px + env(safe-area-inset-bottom))` + `van-button type="primary" block round :loading`。用于独立表单页（AIProvider、Agent、Skill、MCP Form）。

### 破坏性操作确认

统一使用 `showConfirmDialog` + try/catch 处理取消：
```ts
try {
  await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name }) })
} catch { return }  // 用户取消
await api.delete(id)
showSuccessToast(t('toast.deleteSuccess'))
```

### AI 管理 UI

- **Circuit breaker 可视化**: 彩色健康点 (green/yellow/red) + 文本 badge + 原因
- **API Key 安全**: 遮蔽显示 + 异步 reveal + 复制到剪贴板
- **Capability chips**: 色标 mini icon (blue=text, purple=thinking, teal=vision)
- **Provider 排序**: vuedraggable 拖拽 + drag handle

## Key Component Reference

| 组件 | 路径 | 用途 |
|------|------|------|
| MoneyDisplay | `components/common/MoneyDisplay.vue` | 统一金额显示 |
| EmptyState | `components/common/EmptyState.vue` | 空态（van-empty 封装） |
| CurrencyButton | `components/common/CurrencyButton.vue` | 币种选择器 |
| PageHeader | `components/common/PageHeader.vue` | 页面标题栏 |
| BottomSheetConfirm | `components/BottomSheetConfirm.vue` | 底部确认弹窗 |
| TagSelector | `components/asset/TagSelector.vue` | 标签多选+创建 |
| ChainOfThought | `components/ai-chat/ChainOfThought.vue` | DeerFlow 思维链 |
| MarkdownContent | `components/ai-chat/MarkdownContent.vue` | Markdown 渲染 |
| ModeSelector | `components/ai-chat/ModeSelector.vue` | 4 模式选择器 |
| InputBox | `components/ai-chat/InputBox.vue` | AI 输入框 |
| BlockEditor | `components/manifesto/BlockEditor.vue` | 宣言段落编辑器 |
| SignaturePad | `components/manifesto/SignaturePad.vue` | 手写签名画布 |
