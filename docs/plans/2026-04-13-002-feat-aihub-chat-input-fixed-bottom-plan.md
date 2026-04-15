---
title: "feat: AIHubPage 问答框固定底部 + 换行输入 + 高度调整 + 问题透传修复"
type: feat
status: active
date: 2026-04-13
---

# feat: AIHubPage 问答框固定底部 + 换行输入 + 高度调整 + 问题透传修复

## Problem Frame

AIHubPage 当前的问答框（`.chat-entry`）是页面流中的普通块元素，随页面滚动消失。用户需要滚动到底部才能提问，体验割裂。同时输入框是单行 `<input type="text">`，不支持换行，限制了多行问题的输入。

另一个独立 bug：`startChat()` 已经通过 `router.push({ path: '/ai/chat', query: { q } })` 传递了问题，但 `AIChatPage` 的 `onMounted` 只加载历史记录，从不读取 `route.query.q`，导致跳转后问题丢失、不自动发送。

## Requirements

- R1. 问答框固定在页面最底部，不随页面内容滚动
- R2. 输入框支持换行（多行文本）
- R3. 输入框右上角有放大/缩小按钮，点击可在"默认高度"和"展开高度"之间切换
- R4. 宽度保持自适应页面宽度（现状不变）
- R5. 固定底部时不遮挡底部导航栏（需叠加在导航栏之上，或与导航栏高度协调）
- R6. 页面内容底部需有足够 padding，避免被固定问答框遮挡
- R7. 保持无障碍合规（aria-label、键盘可访问性）
- R8. 从 AIHubPage 输入问题跳转到 AIChatPage 后，问题自动填入并发送

## Scope Boundaries

- Unit 2 仅修改 `AIChatPage` 的 `onMounted`，不改动其他逻辑
- 不修改底部导航栏组件
- 不做动画过渡（resize 切换直接跳变即可）
- 不持久化用户选择的高度（页面刷新后恢复默认）

## Key Technical Decisions

- **`<textarea>` 替换 `<input type="text">`**：原生支持换行，`resize: none` 禁用浏览器默认拖拽 resize（用自定义按钮控制）。`@keydown.enter` 改为 `@keydown.enter.exact`（不带 Shift）触发发送，`Shift+Enter` 自然换行。
- **固定定位**：`.chat-entry` 改为 `position: fixed; bottom: 0; left: 0; right: 0`，`z-index` 高于页面内容但需考虑与 Vant tabbar 的层级（Vant tabbar 默认 `z-index: 1`，问答框设为 `z-index: 10` 即可叠加在导航栏上方）。
- **高度切换**：`expanded` ref（boolean），默认 `false`。默认高度约 `72px`（单行视觉），展开高度约 `160px`。`textarea` 的 `rows` 或 `height` 由 computed style 控制。
- **放大/缩小图标**：右上角绝对定位的 `<button>`，使用现有 SVG inline 模式（`viewBox="0 0 24 24"`，`stroke="currentColor"`）。放大图标用 expand arrows，缩小图标用 compress arrows。
- **页面底部 padding**：`.ai-hub-page` 需增加 `padding-bottom`，值 = 固定问答框高度 + 导航栏高度（约 `50px + 72px = 122px`，展开时更大）。用 CSS 变量或固定值均可，实现时取固定值即可。
- **问题透传**：`AIChatPage.onMounted` 在加载历史后检查 `route.query.q`，若存在则填入 `inputText` 并调用 `onSend()`。需在历史加载完成后执行，避免消息顺序错乱。

## Implementation Units

### Unit 1: AIHubPage 问答框固定底部 + 换行 + 高度切换

**Goal:** 将 AIHubPage 的问答框改为固定底部、多行输入、支持高度切换

**Files:**
- Modify: `frontend/src/pages/AIHubPage.vue`

**Approach:**

Template 层：
- `.chat-entry` 保持结构，内部调整：
  - 右上角新增 expand/collapse `<button>`，绝对定位
  - `<input>` 替换为 `<textarea>`，绑定 `v-model="chatInput"`，`:style` 绑定高度，`@keydown.enter.exact.prevent="startChat"`

Script 层：
- 新增 `expanded` ref（`boolean`，默认 `false`）
- `toggleExpand()` 函数切换 `expanded`

Style 层：
- `.chat-entry`：`position: fixed; bottom: 0; left: 0; right: 0; z-index: 10; padding: 8px 16px 12px; background: var(--bg-primary); border-top: 1px solid var(--border-color)`
- `.chat-input-wrap`：`position: relative`（为 expand 按钮提供定位上下文）
- `.chat-input`（textarea）：`width: 100%; resize: none`；默认高度约 `52px`，展开约 `140px`
- `.chat-expand-btn`：右上角浮出，`position: absolute; top: -28px; right: 0`
- `.ai-hub-page`：`padding-bottom: 120px`（默认）；展开时动态增加

**Patterns to follow:**
- 现有 `.chat-send` 按钮的 SVG inline 模式（`width="16" height="16" viewBox="0 0 24 24"`）

**Test scenarios:**
- Happy path: 问答框固定在视口底部，滚动页面时不移动
- Happy path: 输入框内按 Enter 触发发送，按 Shift+Enter 换行
- Happy path: 点击放大按钮后输入框高度增加，图标变为缩小图标
- Happy path: 点击缩小按钮后输入框恢复默认高度，图标变为放大图标
- Happy path: 页面内容最底部不被固定问答框遮挡（有足够 padding）
- Happy path: 输入框宽度随页面宽度自适应
- Edge case: 展开状态下发送消息后，输入框清空但保持展开高度

**Verification:**
- `npm run typecheck` 通过
- 视觉检查：固定底部、换行、高度切换均正常

---

### Unit 2: AIChatPage 读取 query.q 并自动发送

**Goal:** 修复从 AIHubPage 跳转时问题丢失的 bug — `AIChatPage` 在 `onMounted` 中读取 `route.query.q` 并自动触发发送

**Files:**
- Modify: `frontend/src/pages/AIChatPage.vue`

**Root cause:** `startChat()` 已正确传递 `query: { q }`（`AIHubPage.vue` line 266），但 `AIChatPage.onMounted`（line 157）只调用 `getChatHistory()` 和 `markChatRead()`，从不读取路由参数。

**Approach:**
- 在 `onMounted` 中，历史加载完成后：
  - 读取 `const q = route.query.q`
  - 若 `q` 为非空字符串，则 `inputText.value = q`，然后调用 `onSend()`
- 需要 `import { useRoute } from 'vue-router'` 并在 setup 中初始化 `route`

**Patterns to follow:**
- 现有 `onChipClick(text)` 的模式：填入 `inputText.value` 后直接调用 `onSend()`

**Test scenarios:**
- Happy path: 从 AIHubPage 输入"我家净资产是多少"后点击发送，跳转到 AIChatPage 后问题自动出现在对话中并触发 AI 回复
- Happy path: 直接访问 `/ai/chat`（无 query 参数）时，行为与现在完全一致（加载历史，不自动发送）
- Edge case: `route.query.q` 为空字符串时不触发发送
- Edge case: 历史记录加载失败时，query.q 仍然正常触发发送（在 catch 块之后处理）

**Verification:**
- `npm run typecheck` 通过
- 手动测试：AIHubPage 输入问题 → 点击发送 → AIChatPage 自动发送该问题并显示 AI 回复
