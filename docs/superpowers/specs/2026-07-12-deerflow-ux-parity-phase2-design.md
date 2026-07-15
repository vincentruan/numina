---
title: DeerFlow UX Parity Phase 2 — AI Agent 交互增强
created: 2026-07-12
status: draft
scope: frontend-main, server-agent
priority_tiers: P0 (核心交互) → P1 (体验增强) → P2 (细节打磨)
revised: 2026-07-13 — feasibility + scope-guardian 审查合并：修正文件路径、拆分 P0 子任务、补充遗漏项
review_status: reviewed — feasibility ✅ scope-guardian ✅
---

# DeerFlow UX Parity Phase 2 — AI Agent 交互增强

## 背景

基于 2026-06-18 AI Chat Redesign 完成的基础架构（LangGraph SDK streaming + 组件化），对 DeerFlow 参考代码进行系统性对比后，识别出尚未对齐的交互设计方向。核心目标是**复刻 DeerFlow PC 端交互模式，融入 Numina 的 deerflow-harness 框架**。

### 用户画像

Numina AI Agent 服务两类用户：

1. **轻度分析用户** — 查询资产余额、简单分析家庭资产负债表、月度支出概览。交互模式：一问一答，快速获得答案。
2. **深度研究用户** — 基于资产/负债/基金理财现状，深度研究优化方向，挖掘投资机会，对比不同理财策略。交互模式：多轮对话，agent 主动搜索、分析、澄清需求，输出结构化研究报告。

深度研究场景与 DeerFlow 的定位高度一致——DeerFlow 本身就是面向知识工作者的深度研究 agent。**先复刻 DeerFlow 的成熟交互模式，后续在此基础上针对家庭资产场景打磨超越。**

### 前置依赖

- [2026-06-18 AI Chat Redesign](./2026-06-18-ai-chat-redesign-design.md) — 基础架构已就位
- [2026-06-09 AI Chat 处理过程展示优化](./2026-06-09-ai-chat-process-display-optimization-design.md) — 事件命名已统一
- 现有组件体系：`components/ai-chat/` 下 26 个组件 + `composables/ai-chat/` 下 7 个 composable

### 设计原则

1. **复刻优先** — DeerFlow 已有成熟实现的，直接对齐其交互模式，不自创方案
2. **增量集成** — 在现有组件体系上扩展，不重写已稳定的模块
3. **后端最小改动** — 优先前端实现，只在必要时扩展 SSE 协议或 API

---

## 已实现功能（不在本期范围）

经代码库审查，以下 DeerFlow 交互模式已在 Numina 中实现，**不纳入本期需求**：

| 功能 | 实现位置 | 状态 |
|------|---------|------|
| Regenerate（重新生成） | `components/chat/AssistantMessage.vue` footer retry 按钮 (line 299) + error-state retry (line 268-273) + `useThreadChat.ts` retry() (line 773-781) | ✅ 已实现 |
| Follow-up 建议 | 后端 SSE `suggestions` 事件 + `components/ai/SuggestionChips.vue` 容器 + `components/ai-chat/SuggestionChip.vue` 单 chip + `AssistantMessage.vue` 内联 chip（三套实现） | ✅ 已实现 |
| 消息列表骨架屏 | `components/ai/AIChatSkeleton.vue` 全页骨架屏（注意：在 `ai/` 目录，非 `ai-chat/`） | ✅ 已实现 |
| 滚动到底部按钮 | `components/ai/MessageList.vue` sticky 浮动按钮 + scroll 事件监听 + isNearBottom() 阈值检测（非 IntersectionObserver） | ✅ 已实现 |

---

## 分期总览

| 期次 | 方向 | 增益 | 预估工作量 |
|------|------|------|-----------|
| **P0** | LangGraph interrupt/resume spike | 🔴 验证 deerflow-harness rev 4538c322 是否支持 interrupt()，阻断 Human Input Card | 0.5 天 |
| **P0** | Human Input Card — 后端 interrupt/resume | 🔴 功能性缺失，阻断 agent 澄清能力 | 3 天 |
| **P0** | Human Input Card — 前端交互卡片 | 🔴 依赖后端 interrupt pipeline | 2 天 |
| **P0** | Reasoning 计时器 + 自动收起 | 🔴 核心 AI 交互体验，低成本高收益 | 1-2 天 |
| **P1** | Markdown 错误边界 | 🟡 崩溃恢复，当前无保护 | 0.5-1 天 |
| **P1** | 语音输入 | 🟡 移动端体验提升，深度研究场景辅助 | 2-3 天 |
| **P1** | Branch（分支对话） | 🟡 深度研究用户探索多假设路径 | 2-3 天 |
| **P1** | 选中文本引用 | 🟡 深度研究场景引用上下文 | 1 天 |
| **P2** | Citation HoverCard 预览 | 🟢 引用来源快速预览 | 1 天 |
| **P2** | 工具调用富结果可视化 | 🟢 信息密度提升 | 2-3 天 |

---

## P0 — 核心交互（优先实现）

### 0. LangGraph interrupt/resume 可行性验证（Spike）

**目标：** 在投入 Human Input Card 开发前，验证 deerflow-harness rev 4538c322 是否支持 LangGraph interrupt() 机制。

**验证项：**
1. `DeerFlowClient.stream()` 使用 `run_in_executor` 做同步迭代 — interrupt() 是否能在同步 stream 路径中正确暂停图执行？
2. `typed_stream_dispatch`（adapter.py:270-320）是否有事件类型可以承载 interrupt 数据？
3. `worker.py` 的 `run_family_agent()` 流式循环（lines 214-249）目前只检测 `record.abort_event`（用户取消），需要能检测 LangGraph interrupt 事件并暂停 run
4. `schedule_run_cleanup(run_manager, run_id, delay=300)` 会在 5 分钟后 GC 已中断的 run — 需要跳过 `interrupted` 状态的 run

**验收标准：**
- 产出 spike 报告：可行 / 需要 harness 修改 / 不可行需替代方案
- 如果不可行，Human Input Card 降级为 P1 并重新评估技术方案

---

### 1. Human Input Card（澄清交互卡片）

**DeerFlow 参考：** `human-input-card.tsx`

**当前状态：** 前端 `MessageGroup.vue`（lines 204-217）已有 `assistant:clarification` 分组渲染（info 图标 + "Need clarification?" 标题 + markdown 内容），但**后端完全缺少 interrupt/resume 流程**：
- `ask_clarification` 工具在后端零注册（仅前端 `messageGroups.ts` 有检测逻辑）
- `runs_stream.py` 的 `command` 字段是死代码（`sse_gateway.py` 不转发给 `run_family_agent()`）
- 无 `/resume` endpoint
- `worker.py` 的 "interrupted" 状态是 run 级取消，非 LangGraph 图级 human-in-the-loop

**需求拆分为两个独立子任务：**

#### 1a. 后端：LangGraph interrupt/resume 流程（3 天）

**需要实现：**

1. **`ask_clarification` 工具注册** — 在 DeerFlow adapter（`sync_tool_patch.py` 或新建 `interrupt_tools.py`）中注册工具，调用 LangGraph `interrupt()` 暂停图执行
2. **Worker interrupt 检测** — `worker.py` 流式循环需检测 interrupt 事件，将 run 状态设为 `interrupted`（区别于用户取消的 `cancelled`），**并跳过 cleanup**（当前 300s delay 会 GC interrupted run）
3. **Interrupt SSE 事件** — 在 `typed_stream_dispatch` 中新增 interrupt 事件类型映射，通过 SSE `custom` 事件传递 `{type: 'interrupt', question, options, context, interrupt_id}`
4. **Resume endpoint** — `POST /api/threads/{thread_id}/runs/resume`
   - Request body: `{answer: string, interrupt_id: string}`
   - 需验证 `family_id` 归属（参照 `cancel_run` 的 runs_stream.py:164-170 模式）
   - 通过 LangGraph `Command(resume=answer)` 恢复图执行

**并发 interrupt 处理：**
- 同一 thread 同时只允许一个 active interrupt
- 如果 agent 在用户回答前发起第二个 interrupt，取消第一个（前端卡片标记为 superseded）

**验收标准：**
- 后端可以发起 interrupt，SSE 输出 interrupt 事件
- Resume endpoint 接收回答后 agent 继续执行
- 多租户隔离：family_id 校验通过
- interrupted run 不被 cleanup GC

#### 1b. 前端：交互卡片组件 `HumanInputCard.vue`（2 天）

新建组件，替代当前 `assistant:clarification` 分组的纯文本渲染。

**卡片结构：**
```
┌─────────────────────────────────┐
│ 💬 Agent 需要确认              │  ← 标题 + 图标
│                                 │
│ [context markdown]              │  ← 背景说明（可选）
│                                 │
│ ❓ 问题内容（markdown）         │  ← 问题正文
│                                 │
│ ┌─────────────────────────┐    │
│ │ 选项 A                   │    │  ← choice 模式：按钮列表
│ └─────────────────────────┘    │
│ ┌─────────────────────────┐    │
│ │ 选项 B                   │    │
│ └─────────────────────────┘    │
│                                 │
│ ┌─────────────────────────┐    │
│ │ 或输入自定义回答...      │    │  ← 自由文本输入
│ └─────────────────────────┘    │
│                    [提交]       │
│                                 │
│ ✅ 已回答                       │  ← 状态标记
└─────────────────────────────────┘
```

**Props 接口：**
- `question: string` — 问题内容（markdown）
- `context?: string` — 背景说明（markdown）
- `options?: Array<{ label: string; value: string }>` — 可选选项
- `choiceWithOther?: boolean` — 是否允许选项 + 自定义输入
- `status: 'pending' | 'submitting' | 'answered' | 'error' | 'superseded'` — 当前状态
- `answer?: string` — 已回答的内容
- `errorMessage?: string` — 提交失败时的错误信息
- `threadId: string` — 用于 resume API 调用
- `interruptId: string` — 标识要 resume 的 interrupt

**交互逻辑：**
- 选项模式：点击按钮直接提交
- 自由文本模式：textarea + 提交按钮，IME-aware Enter 提交
- `choice_with_other`：同时显示选项按钮和文本输入
- 提交中显示 loading 状态（spinner + "提交中..."）
- 提交成功后卡片变为只读状态，显示 ✅ 已回答
- 提交失败显示 ❌ + 错误信息 + 重试按钮
- 历史会话中已回答的卡片显示为只读

**无障碍：**
- 选项按钮支持 Tab 键导航 + Enter/Space 激活
- 卡片获得焦点时屏幕阅读器朗读问题内容
- `role="group"` + `aria-label="Agent 澄清请求"`

**前端验收标准：**
- 卡片正确渲染问题和选项
- 提交后显示 loading → 成功/失败状态
- 历史会话中已回答的卡片显示为只读
- 键盘可完成所有操作（Tab + Enter）
- `superseded` 状态的卡片显示为灰色 + "已被新问题替代"

---

### 2. Reasoning 计时器 + 自动收起

**DeerFlow 参考：** `reasoning.tsx` 中的 `LiveTimer` + 自动收起逻辑

**当前状态：** `ChainOfThought.vue` 展示推理内容，但没有前端侧计时器，也不会自动收起。`showThinking` ref 默认 `false`（折叠），但无自动折叠逻辑。

**需求：**

#### 2.1 LiveTimer 组件

在 `ChainOfThought.vue` 的标题区域增加实时计时显示。

**行为：**
- 推理内容开始流式输出时，启动计时器
- 显示格式：`思考中... (12s)` — 使用 `ShimmerText` 效果
- 推理结束后，停止计时，记录总时长
- 收起后显示：`已思考 N 秒`（静态文本）
- 超过 60 秒时格式化为 `1m 23s`，超过 5 分钟格式化为 `5m+`

**实现要点：**
- 使用 `setInterval(1000ms)` 更新秒数
- 推理结束事件（`reasoning_content` 流结束或 `content` 开始）触发停止
- 计时器组件在推理结束后销毁（`clearInterval`），避免内存泄漏

#### 2.2 自动收起逻辑

**行为：**
- 推理内容流式输出时，默认展开
- 推理结束后 **1 秒** 自动收起（CSS transition 300ms）
- 用户手动展开/收起后，不再自动触发（尊重用户意图）
- 收起状态下显示摘要行：`已思考 N 秒 ▼`

**实现要点：**
- 在 `ChainOfThought.vue` 中维护 `autoCollapsed` flag
- 用户点击 toggle 时设置 `manualControl = true`，禁用自动收起
- 每次新的推理开始时重置 `manualControl = false`

**验收标准：**
- 推理流式输出时显示实时秒数
- 推理结束后 1 秒自动收起，显示"已思考 N 秒"
- 用户手动展开后不再自动收起
- 历史会话：如果 checkpoint 中有 reasoning 时间戳元数据，显示"已思考 N 秒"；**如果无元数据，不显示时长摘要**（避免猜测错误数据）

**⚠️ 审查发现 — 历史模式依赖：** checkpoint 中 `additional_kwargs.reasoning_content` 不包含时长元数据。实现时需先验证 checkpoint metadata 是否有 reasoning start/end timestamp。如果没有，需在后端新增持久化（在 SSE reasoning 事件流中记录首尾时间戳到 message metadata），否则历史会话的"已思考 N 秒"功能不可用，应降级为仅实时会话显示。

---

## P1 — 体验增强

### 3. Markdown 错误边界

**DeerFlow 参考：** `streamdown.tsx` + `StreamdownFallbackBoundary`

**当前状态：** `MarkdownContent.vue` 使用 60ms debounce 全量重新渲染 markdown-it 输出。Shiki 代码高亮已有 try-catch 降级，但**主渲染路径 `renderMarkdown()` 无错误保护**。畸形 markdown（深层嵌套引用导致栈溢出）可能导致白屏。

**需求：**

#### 3.1 错误边界

**方案：**
- 在 `MarkdownContent.vue` 的 `renderMarkdown()` 中 try-catch
- 捕获异常时降级为纯文本渲染（`<pre>` + 基础 HTML 转义）
- 控制台输出警告日志（`console.warn`），不影响其他消息
- 添加 Vue `onErrorCaptured` 作为二级保护

**不做增量渲染优化** — 当前 60ms debounce 已提供可接受的流式体验，增量渲染（按 `\n\n` 分段）引入的复杂度（代码块跨块、表格续行、列表续行）不值得在家庭资产场景下投入。如果后续监控发现长回复性能问题，再单独优化。

**验收标准：**
- 畸形 markdown（深层嵌套引用 `> > > > > > ...` 50 层）不导致白屏，降级为纯文本
- 代码高亮仍然正常工作
- 控制台有警告日志便于排查

---

### 4. 语音输入

**DeerFlow 参考：** `input-box.tsx` 中的 Web Speech API 集成

**需求：**

- InputBox 增加麦克风按钮
- 使用 Web Speech API (`SpeechRecognition`) 进行语音识别
- 支持连续识别 + 中间结果实时显示
- 自动重连（短暂静音后自动继续监听，silenceTimeout=1500ms）
- 最大录制时长 60s，超时自动停止
- 语言检测：从 `navigator.language` 获取
- 识别结果填充到输入框（不自动发送，显式写入验收标准）
- 浏览器不支持时隐藏按钮
- 识别中途失败（网络错误等）：toast 提示 + 重置按钮状态

**隐私与权限：**
- 首次点击麦克风时，如果浏览器未授权，显示 tooltip 说明"语音输入需要麦克风权限，音频不会上传到服务器"
- 权限拒绝后，麦克风按钮变为禁用状态 + tooltip "麦克风权限被拒绝"
- 录音中麦克风按钮显示红色脉冲动画

**浏览器兼容性：**
- 特征检测：`'SpeechRecognition' in window || 'webkitSpeechRecognition' in window`
- 不支持时（Firefox）隐藏按钮，不显示任何提示
- Safari 使用 `webkitSpeechRecognition` 前缀
- **⚠️ iOS WebView (WKWebView) 不支持 SpeechRecognition** — iOS 上所有浏览器（包括 Chrome/Safari）都使用 WKWebView，均无法使用语音输入。麦克风按钮在这些环境下隐藏。这是已知限制，不在本期解决。

**验收标准：**
- 点击麦克风按钮开始语音识别
- 识别结果实时显示在输入框
- 不支持的浏览器不显示按钮
- 权限拒绝后有明确提示

---

### 5. Branch（分支对话）

**DeerFlow 参考：** `message-list.tsx` 中的 `GitBranchPlusIcon` + `onBranchTurn`

**当前状态：** 无 Branch 功能。

**⚠️ 审查发现 — 前置依赖：** `threads.py` 的 `POST /{thread_id}/state` 支持 `checkpoint_id` 但只修改同一 thread，不提供 fork 到新 thread 的能力。需要新增 `POST /api/threads/{thread_id}/fork` endpoint。LangGraph checkpointer fork 语义（新 thread_id + 复制 checkpoint state）需要集成测试验证。

**需求：**

- **P1 前置 spike（0.5 天）：** 验证 LangGraph SDK 是否支持 checkpoint-level fork 到新 thread_id。如果不可行，需实现后端 workaround（复制 checkpoint messages 到新 thread）或降级到后续阶段。
- 在 AI 回复的悬浮工具栏增加 Branch 按钮（🔀 图标）
- 点击后：基于当前消息轮次创建新的 thread 分支
- 新 thread 在当前窗口打开，URL 更新
- 保留原 thread 不变

**后端：** 新增 `POST /api/threads/{thread_id}/fork` endpoint，创建新 thread_id，复制 checkpoint state，验证 family_id 归属传播到新 thread。

**错误处理：**
- checkpoint 不可用时显示 toast "无法创建分支"
- 网络失败时显示 ErrorMessage + 重试
- 并发操作（快速连续点击）时禁用按钮

**验收标准：**
- Branch 按钮可从指定轮次创建新 thread
- 新 thread 打开后 URL 更新
- 原 thread 数据不受影响

---

### 6. 选中文本引用

**DeerFlow 参考：** `message-list.tsx` 中的 selection toolbar

**需求：**

- 用户在 AI 回复中选中文本后，弹出浮动工具条
- 工具条包含："引用到对话" 按钮
- 点击后将选中文本作为引用块填充到输入框：
  ```
  > 选中的文本内容

  ```
- 输入框自动获得焦点
- 工具条在鼠标移出选区 500ms 后淡出

**验收标准：**
- 选中文本后出现引用按钮
- 点击后引用内容出现在输入框
- 输入框获得焦点

---

## P2 — 细节打磨

### 7. Citation HoverCard 预览

**DeerFlow 参考：** `citation-link.tsx`

**当前状态：** `CitationLink.vue` 已存在，但只是简单的链接样式（`<a>` + badge）。`CitationSourcesPanel.vue` 已完整实现（可折叠面板 + 复制引用），由 `AssistantMessage.vue` 在 `phase === 'done'` 时渲染。

**⚠️ 审查发现 — 双形态引用：** 引用标记在页面中以两种形式存在：(1) `CitationLink.vue` 组件实例，(2) `MarkdownContent.vue` 的 `transformCitations()` 生成的内联 `<span class="citation-badge">` HTML。HoverCard 必须同时覆盖两种形态，需通过 `MarkdownContent` 根元素的事件委托实现，而非组件级 hover。

**需求：**

- 鼠标 hover 引用链接时弹出预览卡片
- 卡片内容：标题 + URL + "访问来源" 链接
- 使用 Vant Popover 或自定义 floating panel
- 移动端改为点击触发：
  - 使用 Vant Popover `trigger="click"`
  - 点击外部区域关闭
  - Popover 位置自动计算避免溢出

**验收标准：**
- Hover 引用编号显示来源预览卡片
- 包含标题和 URL
- 移动端点击触发，点击外部关闭

---

### 8. 工具调用富结果可视化

**DeerFlow 参考：** `message-group.tsx` 中的工具特定渲染

**当前状态：** ⚠️ **审查修正** — `ChainOfThought.vue`（lines 243-328）**已实现**工具特定结果可视化：`getSearchResults()` 处理 web_search/image_search/web_fetch，`getBashCommand()` 处理 bash/python CodeBlock，`getArtifactPath()` 处理 read_file/write_file artifact links。原 spec 描述"结果展示统一为文本"不准确。

**本期增量需求：**

- `web_search`：增强现有 `ChainOfThoughtSearchResults.vue` 样式（当前已可点击）
- `image_search`：缩略图网格 + tooltip（**仍依赖 DeerFlow adapter 注册此工具**，adapter 未实现前跳过）
- `bash`：✅ 已实现 CodeBlock 展示
- `web_fetch`：增强标题显示（当前仅有单 badge，需与 web_search 视觉区分）
- `read_file` / `write_file`：✅ 已实现 artifact link button
- **新增：** 工具执行失败状态 UI（❌ + 错误摘要，fallback 到默认样式）
- **新增：** 结果为空时显示"无结果"

**验收标准：**
- 不同工具类型的结果有差异化展示
- 搜索结果可点击
- bash 命令在代码块中显示
- 工具失败时有明确的 fallback UI

---

## 横切关注点

以下关注点适用于所有 P0/P1 功能，在实现时必须覆盖：

### 错误处理策略

每个新功能必须定义以下场景的处理：

| 场景 | 处理方式 |
|------|---------|
| 网络超时 | 显示 ErrorMessage + 重试按钮 |
| 后端 4xx/5xx | toast 提示错误详情（中文） |
| 并发操作 | 操作期间禁用触发按钮 |
| 部分成功 | 保留已成功的部分，提示失败部分 |

### 无障碍基线

- 所有交互元素支持 Tab 键导航
- 按钮有 `aria-label`
- 状态变化通过 `aria-live="polite"` 通知屏幕阅读器
- 颜色不作为唯一状态指示（配合图标/文字）

### Dark Mode 适配

**⚠️ 审查新增** — 所有新增组件（HumanInputCard、语音输入按钮、Branch 按钮、选中文本工具条、Citation HoverCard）必须同时支持深色/浅色主题。现有组件中已有硬编码颜色（如 `ChainOfThought.vue` line 776 `color: #ef4444`），新组件应使用 CSS 变量或 `data-theme` 选择器。

### 结构化日志（支撑成功指标）

**⚠️ 审查新增** — 成功指标引用了后端日志统计（`ask_clarification` 调用次数、thread fork 事件等），但当前未定义日志格式。每个新功能的关键事件必须输出结构化日志：

| 事件 | 日志字段 |
|------|---------|
| 澄清请求发起 | `event=clarification_requested, thread_id, interrupt_id` |
| 澄清卡片回复 | `event=clarification_answered, thread_id, interrupt_id, answer_type=choice\|text` |
| 分支创建 | `event=thread_forked, source_thread_id, new_thread_id, checkpoint_id` |
| 语音输入使用 | `event=voice_input_used, duration_ms, language` |
| 文本引用使用 | `event=text_quoted, source_message_id` |

---

## 实现顺序建议

```
P0（第 1 周）:
  Day 1 AM: LangGraph interrupt/resume 可行性 spike（验证 deerflow-harness sync stream 路径）
  Day 1 PM - Day 3: Human Input Card 后端 interrupt/resume pipeline（1a）
  Day 4-5: Human Input Card 前端 HumanInputCard.vue（1b）+ 集成
  Day 5 PM: Reasoning 计时器 + 自动收起（如时间不够顺延到 Week 2 AM）

P1（第 2-3 周）:
  Week 2 AM: Markdown 错误边界（独立 PR，0.5 天可 ship）
  Week 2 PM - Week 3 AM: 语音输入
  Week 3 AM: Branch fork API spike（0.5 天验证 LangGraph checkpoint fork）
  Week 3 PM: Branch 前端 + 选中文本引用

P2（第 4 周）:
  Week 4: Citation HoverCard + 工具富结果增量（失败状态 + 空结果 UI）
```

## 成功指标

### P0 完成后评估（第 1 周末）

| 指标 | 目标 | 衡量方式 |
|------|------|---------|
| Agent 澄清使用率 | ≥10% 的深度研究对话触发至少一次澄清 | 后端日志统计 `ask_clarification` 调用次数 |
| 澄清回复率 | ≥80% 的澄清卡片被用户回复 | 前端提交事件 / 后端 interrupt 事件 |
| Reasoning 计时器感知 | 用户反馈中提及"知道 agent 在想" | 可选：应用内反馈 |

### P1 完成后评估（第 3 周末）

| 指标 | 目标 | 衡量方式 |
|------|------|---------|
| 语音输入使用率 | ≥5% 的移动端用户使用过 | 麦克风按钮点击统计 |
| Branch 使用率 | ≥3% 的深度研究对话创建分支 | thread fork 事件统计 |
| 文本引用使用率 | ≥5% 的对话使用过引用 | selection toolbar 点击统计 |

### 继续/停止决策点

- P0 完成后，如果澄清使用率 <5% 且回复率 <50%，暂停 P1/P2，重新评估交互模式
- P1 完成后，如果 Branch + 语音使用率均 <2%，P2 降级为按需实现

## 风险与约束

1. **Human Input Card 依赖 LangGraph interrupt/resume** — 后端需新增 `ask_clarification` 工具 + resume endpoint，这是本期最大的后端工作量。**⚠️ 审查新增：** `runs_stream.py` 的 `command` 字段是死代码（`sse_gateway.py` 不转发），`worker.py` 的 300s cleanup 会 GC interrupted run，需跳过 interrupted 状态的 run
2. **deerflow-harness sync stream 路径兼容性** — **⚠️ 审查新增：** `DeerFlowClient.stream()` 使用 `run_in_executor` 做同步迭代，LangGraph `interrupt()` 是否能在同步路径中正确暂停图执行需要 spike 验证（P0 Day 1）
3. **语音输入浏览器兼容性** — Safari 需要 `webkitSpeechRecognition` 前缀，Firefox 不支持，**iOS WebView (WKWebView) 完全不支持**（已知限制）
4. **Branch 的 checkpoint fork** — LangGraph SDK 的 fork 能力需要验证，**⚠️ 审查确认：** `threads.py` 的 `POST /{thread_id}/state` 只修改同一 thread，不提供 fork 到新 thread 的能力，需新增 fork endpoint
5. **工具富结果依赖 adapter 工具注册** — `image_search` 前端实现需等 DeerFlow adapter 注册该工具
6. **Reasoning 计时器历史模式** — **⚠️ 审查新增：** checkpoint 中 `additional_kwargs.reasoning_content` 不包含时长元数据，历史会话的"已思考 N 秒"可能需要后端新增持久化

---

## 审查附录

### 审查执行记录

- **审查时间：** 2026-07-13
- **审查类型：** Feasibility Review + Scope Guardian
- **审查 Agent：** feasibility (opus), scope-guardian-2 (opus)

### 关键发现摘要

| 发现 | 影响 | 处置 |
|------|------|------|
| P0 Human Input Card 后端完全缺失 interrupt/resume 流程 | 阻断 agent 澄清能力 | 拆分为 1a(后端) + 1b(前端)，增加 spike 前置任务 |
| P2 工具富结果已部分实现（ChainOfThought.vue lines 243-328） | spec 描述不准确 | 修正当前状态，聚焦增量需求（失败状态 + 空结果） |
| 已实现功能表文件路径错误（3/4 项） | 误导实现 | 修正为实际路径（ai/ 和 chat/ 目录） |
| Reasoning 计时器历史模式依赖不存在的元数据 | 验收标准不可达 | 降级为"有元数据则显示，无则不显示" |
| iOS WebView 不支持 SpeechRecognition | 移动端用户无法使用语音 | 记录为已知限制，隐藏按钮 |
| Citation 引用标记存在双形态（组件 + 内联 HTML） | HoverCard 需事件委托 | 补充实现说明 |
| worker.py 300s cleanup 会 GC interrupted run | Human Input Card 无法工作 | 需跳过 interrupted 状态的 run |
| 缺少 dark mode 和结构化日志横切关注点 | 新组件可能不兼容深色主题，成功指标无法衡量 | 新增两个横切关注点章节 |

## 与现有 Spec 的关系

- 本 spec 是 [2026-06-18 AI Chat Redesign](./2026-06-18-ai-chat-redesign-design.md) 的增量补充
- 不修改已稳定的组件接口（InputBox、MessageGroup、ChainOfThought 等）
- 新增组件独立于现有体系，通过 props/events 集成
- 已实现的 Regenerate、Follow-up、骨架屏、滚动按钮不在本期范围
