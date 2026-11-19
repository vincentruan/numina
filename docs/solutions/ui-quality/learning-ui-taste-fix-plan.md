# 学习系统 UI 品味修复方案

## 问题清单与修复优先级

### P0 — 严重影响可用性（立即修复）

#### 1. Markdown 未渲染
**问题**: AI 消息中的 `**text**` 显示为原始星号
**影响**: LearningSessionPage, SmartTutorPanel, TeachBackPanel
**修复方案**:

> **⚠️ 安全要求**: `v-html` 渲染 AI 生成内容必须经过 XSS 清洗。主应用已有 `userMarkdownSanitizer.ts`（marked + DOMPurify），子应用应复用相同模式。

```vue
<!-- LearningSessionPage.vue -->
<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({ breaks: true })

// 渲染 Markdown 内容（含 XSS 防护，参照 main app 的 userMarkdownSanitizer.ts 模式）
const renderMarkdown = (content: string) => {
  const raw = md.render(content)
  return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
}
</script>

<template>
  <div class="chat-msg__text" v-html="renderMarkdown(msg.content)"></div>
</template>
```

**依赖安装**（与 main app 保持一致，使用 markdown-it + dompurify）:
```bash
cd frontend/apps/child
pnpm add markdown-it dompurify
pnpm add -D @types/markdown-it @types/dompurify
```

**CSS 样式**:
```css
.chat-msg__text :deep(strong) {
  font-weight: 600;
  color: var(--color-ink);
}

.chat-msg__text :deep(em) {
  font-style: italic;
}

.chat-msg__text :deep(ul),
.chat-msg__text :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.chat-msg__text :deep(li) {
  margin: 0.25em 0;
}
```

---

#### 2. MCP 工具调试信息泄漏
**问题**: 工具调用状态和 JSON 结果显示在聊天区
**影响**: SmartTutorPanel, LearningSessionPage
**修复方案**:

> **注意**: SmartTutorPanel.vue 和 TeachBackPanel.vue 已有角色过滤逻辑（分别按 assistant/user/tool 分组显示）。仅需修改 LearningSessionPage.vue，它目前展示所有角色的消息。

```typescript
// LearningSessionPage.vue — 过滤消息列表，排除 tool 角色
const filteredMessages = computed(() => {
  return messages.value.filter(msg => 
    msg.role === 'assistant' || msg.role === 'user'
  )
})

// 如果 assistant 消息中包含 tool_calls 字段，清理其内容
const cleanMessage = (msg: Message) => {
  if (msg.role === 'assistant' && msg.tool_calls) {
    return {
      ...msg,
      content: msg.content || '', // 移除工具调用信息
    }
  }
  return msg
}
```

**模板修改**:
```vue
<div v-for="msg in filteredMessages" :key="msg.id">
  <div class="chat-msg__text" v-html="renderMarkdown(cleanMessage(msg).content)"></div>
</div>
```

---

#### 3. 输入框 placeholder 对比度
**问题**: `#E5E5E5` 在 `#F5F0E0` 上对比度仅 1.1:1
**修复方案**:

```css
/* 全局输入框样式 */
.chat-input::placeholder {
  color: #888888; /* 对比度 4.6:1 ✅ */
  opacity: 1;
}

/* Vant 输入框覆盖 */
:deep(.van-field__control::placeholder) {
  color: #888888;
  opacity: 1;
}

/* 禁用状态 */
.chat-input:disabled::placeholder {
  color: #777777;
  opacity: 0.8;
}
```

---

### P1 — 影响体验（本周修复）

#### 4. 消息气泡样式
**问题**: AI 和用户消息无视觉区分
**修复方案**:

```css
/* AI 消息（左对齐，浅色气泡） */
.chat-msg--assistant {
  display: flex;
  justify-content: flex-start;
  margin: 12px 0;
}

.chat-msg--assistant .chat-msg__bubble {
  background: var(--color-surface-card);
  border-radius: 12px 12px 12px 4px;
  padding: 12px 16px;
  max-width: 85%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--color-border, #F0F0F0);
}

/* 用户消息（右对齐，深色气泡） */
.chat-msg--user {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0;
}

.chat-msg--user .chat-msg__bubble {
  background: var(--color-primary);
  color: var(--color-bg, #FFFFFF);
  border-radius: 12px 12px 4px 12px;
  padding: 12px 16px;
  max-width: 85%;
}

.chat-msg--user .chat-msg__text {
  color: var(--color-bg, #FFFFFF);
}

/* 头像区域 */
.chat-msg__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  margin: 0 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.chat-msg--assistant .chat-msg__avatar {
  background: var(--learning-bg-secondary, #F5F0E0);
}

.chat-msg--user .chat-msg__avatar {
  background: var(--color-primary);
  color: var(--color-bg, #FFFFFF);
}
```

**模板结构**:
```vue
<!-- 消息列表需添加 aria-live 以支持屏幕阅读器 -->
<div class="chat-msg-list" aria-live="polite" aria-relevant="additions">
  <div class="chat-msg" :class="`chat-msg--${msg.role}`">
    <div class="chat-msg__avatar">
      {{ msg.role === 'assistant' ? '🤖' : '👤' }}
    </div>
    <div class="chat-msg__bubble">
      <div class="chat-msg__text" v-html="renderMarkdown(msg.content)"></div>
    </div>
  </div>
</div>
```

**交互状态**（实现时需覆盖以下状态）:
| 状态 | 视觉表现 |
|------|---------|
| 加载中 | AI 气泡区域显示打字动画（三个跳动的点），头像旁显示"正在思考…" |
| 空消息 | 居中显示引导文案，如"问一个问题开始学习吧" |
| 发送失败 | 用户气泡旁显示红色 ⚠️ 图标 + "发送失败，点击重试" |
| 消息截断 | 长消息默认显示前 5 行，底部"展开"按钮 |

---

#### 5. 色彩系统统一
**问题**: 背景色不一致
**修复方案**: 复用 `clay.css` 已有的 token 系统，不创建并行的 `--learning-*` 命名空间。

```css
/* 学习页面统一使用 clay.css 已有 token */
.learning-session-page,
.smart-tutor-page,
.teach-back-page {
  background: var(--color-canvas);
  color: var(--color-ink);
}

/* 如需学习系统专用 token，在 clay.css 中新增（而非另建命名空间） */
/* clay.css :root 区域追加: */
--color-learning-warm:      #F5F0E0;   /* 米黄色卡片背景 */
--color-learning-warm-deep: #EBE5D5;   /* 深米色分隔 */
--color-learning-accent:    #E8B94A;   /* 品牌金色 */
--color-learning-accent-hover: #D4A843;

/* clay.css [data-theme="dark"] 区域追加: */
--color-learning-warm:      #152828;
--color-learning-warm-deep: #1F3535;
--color-learning-accent:    #E8B94A;
--color-learning-accent-hover: #F0C45A;
```

**应用样式**:
```css
.chat-msg__bubble {
  background: var(--color-surface-card);
}

.chat-msg__avatar--assistant {
  background: var(--color-learning-warm);
}
```

---

#### 6. 按钮样式升级
**问题**: 按钮缺乏现代感
**修复方案**:

```css
/* 主按钮（发送、提交） */
.chat-send-btn,
.btn-primary {
  background: var(--color-learning-accent, #E8B94A);
  color: var(--color-ink);
  border: none;
  border-radius: 20px;
  padding: 10px 24px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(232, 185, 74, 0.3);
  min-height: 44px; /* 触控目标 ≥ 44px */
}

.chat-send-btn:hover:not(:disabled) {
  background: var(--color-learning-accent-hover, #D4A843);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(232, 185, 74, 0.4);
}

.chat-send-btn:focus-visible {
  outline: 2px solid var(--color-learning-accent);
  outline-offset: 2px;
}

.chat-send-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(232, 185, 74, 0.3);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

/* 次要按钮（返回、取消） */
.back-btn,
.btn-secondary {
  background: transparent;
  color: var(--color-body);
  border: 1.5px solid var(--color-border);
  border-radius: 20px;
  padding: 8px 20px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 44px;
}

.back-btn:hover {
  background: var(--color-learning-warm);
  color: var(--color-ink);
  border-color: var(--color-body);
}

.back-btn:focus-visible {
  outline: 2px solid var(--color-ink);
  outline-offset: 2px;
}

/* 完成按钮 */
.btn-finish {
  background: var(--color-ink);
  color: var(--color-bg);
  border: none;
  border-radius: 20px;
  padding: 12px 32px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 44px;
}

.btn-finish:hover:not(:disabled) {
  background: var(--color-body);
  transform: translateY(-1px);
}

.btn-finish:focus-visible {
  outline: 2px solid var(--color-ink);
  outline-offset: 2px;
}

.btn-finish:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

---

### P2 — 优化项（下周修复）

#### 7. Typography 层次
```css
/* 标题层级 */
.session-header__title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-ink);
  line-height: 1.3;
  margin: 0 0 8px 0;
}

/* 正文 */
.chat-msg__text {
  font-size: 15px;
  font-weight: 400;
  color: var(--color-ink);
  line-height: 1.6;
}

/* 辅助文字（状态、时间戳） */
.status-indicator,
.chat-msg__time {
  font-size: 13px;
  font-weight: 400;
  color: var(--color-body);
}

/* 标签 */
.session-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 12px;
}

/* 标签语义映射 */
.badge--tutorial {
  background: #E8F5E9; color: #2E7D32;   /* 绿色 = 学习/进度 */
}
.badge--assessment {
  background: #FFF3E0; color: #E65100;   /* 橙色 = 评估/挑战 */
}
.badge--completed {
  background: #E3F2FD; color: #1565C0;   /* 蓝色 = 完成/掌握 */
}
.badge--locked {
  background: #F5F5F5; color: #9E9E9E;   /* 灰色 = 未解锁/禁用 */
}

/* 深色模式标签 */
[data-theme="dark"] .badge--tutorial {
  background: #1B3B1B; color: #66BB6A;
}
[data-theme="dark"] .badge--assessment {
  background: #3E2200; color: #FF9800;
}
[data-theme="dark"] .badge--completed {
  background: #0D2744; color: #42A5F5;
}
[data-theme="dark"] .badge--locked {
  background: #2A2A2A; color: #757575;
}
```

---

#### 8. 滚动条自定义
```css
/* Webkit 滚动条（Chrome, Safari, Edge） */
.chat-area::-webkit-scrollbar {
  width: 6px;
}

.chat-area::-webkit-scrollbar-track {
  background: transparent;
}

.chat-area::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}

.chat-area::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

/* Firefox 滚动条 */
.chat-area {
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.15) transparent;
}
```

---

#### 9. 图标统一
```typescript
// 替换 emoji 为 Iconify 图标
// components/learning/smart-tutor/TeacherAvatar.vue
<script setup lang="ts">
import { IIcon } from '@/components/IIcon.vue'
</script>

<template>
  <div class="teacher-avatar">
    <IIcon icon="mdi:robot-happy" :size="32" />
  </div>
</template>
```

**图标映射表**:
| 原 Emoji | Iconify 图标 | 用途 | aria-label |
|---------|-------------|------|-----------|
| 🎓 | `mdi:school` | 学习会话 | "学习会话" |
| 🧮 | `mdi:abacus` | 数学老师 | "数学老师" |
| 🤔 | `mdi:thought-bubble` | 思考中 | "正在思考" |
| 🔍 | `mdi:magnify` | 诊断阶段 | "诊断阶段" |
| 💡 | `mdi:lightbulb-on` | 引导阶段 | "引导阶段" |
| ✅ | `mdi:check-circle` | 验证阶段 | "验证阶段" |
| 🏆 | `mdi:trophy` | 巩固阶段 | "巩固阶段" |
| 🕵️ | `mdi:detective` | 侦探模式 | "侦探模式" |

> 所有图标组件需添加 `role="img"` 和对应的 `aria-label`。若图标加载失败，保留 emoji 作为 fallback。

---

## 实施步骤

### 第一阶段（P0 - 1 天）
1. 安装 `markdown-it` + `dompurify` 依赖并在 LearningSessionPage, SmartTutorPanel, TeachBackPanel 添加 Markdown 渲染（含 XSS 清洗）
2. 添加消息过滤逻辑，隐藏工具调用信息
3. 更新 placeholder 颜色

### 第二阶段（P1 - 2 天）
4. 实现消息气泡样式（AI 左/用户右）
5. 统一色彩变量（clay.css）
6. 升级按钮样式

### 第三阶段（P2 - 2 天）
7. Typography 层次优化
8. 自定义滚动条
9. 图标统一替换

---

## 验收标准

### 功能验收
- [ ] Markdown 正确渲染（粗体、列表、链接）
- [ ] 工具调用信息不可见
- [ ] placeholder 对比度 ≥ 4.5:1
- [ ] AI/用户消息视觉区分明显

### 视觉验收
- [ ] 色彩一致（所有学习页面使用 clay.css token，无硬编码颜色）
- [ ] 按钮有 hover/active/focus-visible 状态
- [ ] 滚动条不突兀
- [ ] 移动端（375px）无横向滚动
- [ ] 平板（768px）气泡 max-width 不超过 600px
- [ ] 桌面（1024px+）聊天气泡居中，最大宽度 720px

### 无障碍验收
- [ ] 消息列表使用 `aria-live="polite"` 通知屏幕阅读器新消息
- [ ] 所有图标有 `aria-label` 或 `role="img"` + 文字标签
- [ ] 按钮可键盘操作（Enter 发送，Escape 取消）
- [ ] 触控目标 ≥ 44px（按钮、图标按钮）
- [ ] 深色模式所有文字对比度 ≥ 4.5:1

### 性能验收
- [ ] Markdown 渲染延迟 < 50ms
- [ ] 无布局抖动（CLS < 0.1）
- [ ] 首屏加载时间无显著增加
- [ ] DOMPurify 清洗延迟 < 10ms

---

## 参考设计

### 配色方案灵感
- **Duolingo**: 明亮色彩 + 游戏化元素
- **Khan Academy Kids**: 温暖色调 + 大按钮
- **ClassDojo**: 可爱角色 + 清晰反馈

### 组件库参考
- **Vant 4**: 现有基础，保持一致性
- **Ant Design Mobile**: 按钮样式参考
- **Ionic**: 消息气泡布局参考

---

## Open Questions

> 以下问题需产品/设计方向确认后再实施。

### 响应式策略
- 除 375px 外还需支持哪些断点？平板（768px）和桌面端的聊天气泡 max-width、头像间距、字体缩放如何定义？

### 深色模式变体
- 各组件（气泡、按钮、徽章）在深色模式下的具体 token 值和对比度目标？当前仅定义了全局 `--color-learning-*` 的深色变体，组件级别的适配需确认。

### Markdown 共享工具
- 是否将 markdown 渲染 + 清洗逻辑抽取到 `@numina/shared` 包供 main/child 复用？还是仅在 child app 内共享？

### 徽章语义色彩
- 学习页面使用哪些徽章类型？各类型对应的语义色（成功/警告/错误/进度/中性）在 light/dark 模式下如何定义？

### 产品设计原则
- 定义 2-3 条产品专属设计原则（如"减少答题扫描成本"、"反馈状态一目了然"），替代通用"现代感"方向，指导后续视觉决策。

---

## Deferred / Open Questions

### From 2026-11-19 review
- **产品设计原则**: 参考设计引用了 Duolingo/Khan Academy Kids/ClassDojo，但未说明具体借鉴哪些方面。需要确定 2-3 条本产品专属的设计原则（例如"降低答题扫描成本"、"让反馈状态无可歧义"），以此指导视觉决策而非泛泛的"现代感"。
