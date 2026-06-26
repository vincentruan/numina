---
date: 2026-06-24
topic: deerflow-chat-replication
replaces:
  - 2026-05-27-deerflow-chat-ux-fusion-requirements.md (superseded — broader scope)
related:
  - 2026-06-20-deerflow-sse-protocol-alignment-requirements.md (backend SSE protocol)
---

# DeerFlow Chat Replication — AI 对话全交互复刻

## Summary

在 DeerFlow SSE 协议对齐（backend 三轨 SSE：messages/custom/values）完成后，于 Numina `/ai/chat` 页面完整复刻 DeerFlow 的前端交互体验：用户输入气泡展示、agent 流式答复与规划/工具调用步骤可视化、实时 token 用量显示、AI 生成的追问建议、全部内容复制、以及生成文件（HTML/Python 等）的 artifact 预览面板。保留 Numina 的 4 档输入模式选择器（flash/thinking/pro/ultra），映射到 DeerFlow 的 stream context 参数。

---

## Problem Frame

Numina 的 AI 对话页面已完成后端 SSE 三轨协议对齐（messages/custom/values），但前端仍然只消费 `messages-tuple` 事件来渲染文本流。这意味着：

- 用户看不到 agent 的规划过程（tool call / websearch / skill 调用步骤）
- token 用量不展示（之前的 UX Fusion 文档将其 scoped out 为"对家庭用户无意义"，但用户明确要求复刻）
- 没有追问建议引导用户继续对话
- 没有复制功能
- 没有 artifact 预览面板展示生成的文件

DeerFlow 的原生交互已被用户验证为成熟体验，Numina 需要完整复刻这一体验，同时保持自身的 4 档模式选择和设计语言。

---

## Actors

- **A1. 家庭用户**：通过 `/ai/chat` 页面与 AI 对话，需要清晰的流式反馈、过程透明度和便捷的交互（复制、追问）
- **A2. AI Agent**：后端 DeerFlow 驱动的智能体，通过三轨 SSE 返回 token 流、工具调用进度、状态快照

---

## Key Flows

- **F1. 完整流式对话流程（带工具调用）**
  - **Trigger:** 用户在 4 档模式下提问，agent 需要调用工具
  - **Actors:** A1, A2
  - **Steps:**
    1. 用户选择模式（flash/thinking/pro/ultra），输入问题，提交
    2. 前端创建/加载 thread，发送 `POST /api/langgraph/threads/{id}/runs/stream` 请求，`stream_mode` 包含 `["messages-tuple","values","updates","custom","events"]`
    3. 前端消费 SSE 事件流：
       - `metadata` → 记录 run_id
       - `values` → 更新消息状态快照
       - `updates` → 中间件/节点过渡（可忽略或用于调试）
       - `messages` → 渲染 AI 文本流 + 工具调用卡片
       - `custom` → 渲染工具进度事件（websearch 查询、页面抓取等规划步骤）
       - `events` → LangGraph 原生事件
    4. 规划步骤在可折叠面板中实时展示（websearch 显示搜索词，page-fetch 显示 URL）
    5. 同时轮询 `GET /api/threads/{id}/token-usage` 更新 token 用量显示
    6. 流式文本在规划面板下方渲染（markdown：表格、链接、引用、代码块）
    7. 流完成后从已消费的 SSE `custom` 事件中提取 suggestion 类型的追问建议（3 条）
    8. 追问建议以药丸按钮形式显示在输入框上方
    9. SSE 流中断时：自动重试最多 3 次（指数退避），保留已渲染的部分内容。3 次重试均失败后，底部显示错误提示条（"连接中断，点击重试"），用户点击后重新发送当前问题。不自动重试超过 3 次（避免工具调用重复产生副作用）。
  - **Outcome:** 用户看到完整的 agent 工作过程、实时 token 消耗、丰富的 markdown 回答、追问引导
  - **Covered by:** R1, R2, R3, R4, R5, R6, R7, R8, R9

- **F2. 简单对话流程（无工具调用）**
  - **Trigger:** 用户在 flash 模式或简单问题下提问
  - **Steps:**
    1. 用户提交问题
    2. SSE 流仅产生 `messages` 事件（文本流），无 `custom` 事件
    3. 规划步骤面板不显示（或显示为空）
    4. 流式文本直接渲染
    5. 完成后显示追问建议
  - **Outcome:** 简洁流畅的对话体验，无冗余过程展示
  - **Covered by:** R1, R5, R8, R10, R11, R12

- **F3. 文件生成与 Artifact 预览**
  - **Trigger:** Agent 生成文件（Python 脚本、HTML 页面等）
  - **Steps:**
    1. SSE `messages` 或 `values` 事件中包含 artifact 信息
    2. 全屏预览页打开，显示文件名和预览内容
    3. 面板提供"复制到剪贴板"和"关闭"按钮
  - **Outcome:** 用户可预览和复制生成的文件
  - **Covered by:** R17, R18, R19

---

## Requirements

### 用户输入气泡

- **R1.** 用户提交的问题在对话区域显示为气泡（右对齐或左对齐，与 DeerFlow 保持一致），气泡内显示问题文本
- **R2.** 用户气泡支持复制到剪贴板（气泡旁显示复制按钮）

### Agent 流式答复与规划步骤

- **R3.** 消费 SSE `custom` 事件，将工具调用进度渲染为规划步骤列表。每个步骤显示：
  - 类型图标（websearch = 🔍，page-fetch = 🌐，skill = 🧩，mcp = 🔌，code = 💻）
  - 步骤摘要文本（websearch 显示搜索查询词，page-fetch 显示"查看网页"+URL）
- **R4.** 规划步骤放在可折叠面板中，默认展开（与 DeerFlow 行为一致）。面板顶部显示"隐藏步骤"/"查看其他 N 个步骤"切换按钮
- **R5.** SSE `messages` 事件中的 AI 文本流式渲染为 markdown（支持标题、表格、链接、引用标记、代码块、加粗等）。流式输出期间自动滚动到最新内容；用户手动上滚时暂停自动滚动，底部显示"回到底部"按钮，点击后恢复自动滚动。规划面板展开/折叠时保持当前阅读位置不变
- **R6.** 表格上方显示"Copy table as markdown"和"Download table"操作按钮
- **R7.** 流式输出期间在流式文本末尾（最后一行之后）显示弹跳三点动画指示器（⚫⚪），随文本增长自然下移，配合 R5 自动滚动始终在可视区域底部。流完成后消失

### Token 用量

- **R8.** 每个 agent 答复下方显示 token 用量行：`Tokens 输入: X 输出: Y 总计: Z`，带小图标
- **R9.** Token 用量在流式过程中实时更新（轮询 `GET /api/threads/{id}/token-usage`，间隔 1-2 秒）

### 追问建议

- **R10.** AI 答复完成后，在输入框上方显示 3 个追问建议药丸按钮
- **R11.** 追问建议从 SSE `custom` 事件中的 suggestion 类型获取（后端在流式过程中生成建议，通过 custom 轨发送）
- **R12.** 用户点击药丸按钮，自动填入输入框并发送

### 复制功能

- **R13.** 用户气泡支持复制（按钮触发 `navigator.clipboard.writeText`）
- **R14.** AI 答复内容支持复制（在消息操作栏提供"复制"按钮，复制完整 markdown 文本）
- **R15.** 表格支持"Copy table as markdown"和"Download table"
- **R16.** 生成的文件（artifact）支持"复制到剪贴板"

### Artifact 预览面板

- **R17.** 当 agent 生成文件（Python、HTML 等）时，对话区显示 artifact 入口卡片（文件名 + 类型图标），点击后跳转到全屏预览页
- **R18.** 全屏预览页显示文件名、文件内容（代码高亮或 HTML 预览）、顶部导航栏含"复制到剪贴板"和"返回"按钮
- **R19.** _（已移除 — 移动端全屏预览无需宽度调整）_

---

## Acceptance Examples

- **AE1. [R1, R2]** 用户输入"你好"并提交，对话区域显示用户问题气泡，气泡旁有复制按钮。点击复制按钮，问题文本被复制到剪贴板。

- **AE2. [R3, R4, R5, R7]** 用户在 pro 模式下提问"2026年全球新能源汽车销量排名"，agent 开始调用 websearch 工具。规划步骤面板自动展开，实时显示：🔍 "在网络上搜索 '2026 global EV sales ranking'" → 🌐 "查看网页 evcarlatest.com/..." → 🔍 "在网络上搜索 'BYD Tesla Q1 sales'" → 🌐 "查看网页 cleantechnica.com/..."。流式输出期间底部显示弹跳三点动画。面板顶部显示"隐藏步骤"按钮。

- **AE3. [R6]** AI 答复包含一个排名表格，表格上方显示"Copy table as markdown"和"Download table"按钮。点击"Copy table as markdown"，表格的 markdown 格式被复制。

- **AE4. [R8, R9]** AI 答复下方显示"Tokens 输入: 200.2K 输出: 7,424 总计: 207.6K"。流式过程中数字持续更新。

- **AE5. [R10, R11, R12]** AI 答复完成后，输入框上方出现 3 个追问药丸按钮（如"基于Q1销量格局变化，下半年新能源汽车产业链有哪些投资主线？"）。点击药丸，文本自动填入输入框并发送。

- **AE6. [R13, R14, R15, R16]** 用户气泡旁的复制按钮、AI 答复底部的复制按钮、表格上方的"Copy table as markdown"按钮、artifact 面板中的"复制到剪贴板"按钮，均可正确复制对应内容。

- **AE7. [R17, R18]** 用户提问"用 Python 写一个斐波那契函数并生成 HTML 页面"，agent 生成 `fibonacci.py` 文件。对话区显示 artifact 入口卡片，点击后跳转到全屏预览页，显示文件名 `fibonacci.py`、Python 代码内容（语法高亮）、顶部导航栏含"复制到剪贴板"和"返回"按钮。

- **AE8. [F2]** 用户在 flash 模式下提问"你好"，无规划步骤面板，AI 直接流式输出回答，完成后显示追问建议。

---

## Success Criteria

- 用户在 agent 调用工具时能实时看到规划步骤（搜索词、抓取的 URL），过程完全透明
- 流式文本渲染为丰富的 markdown（表格、链接、引用、代码块），与 DeerFlow 视觉质量一致
- Token 用量实时更新，用户可了解每次对话的消耗
- 追问建议引导用户继续深入对话，提高对话轮次
- 所有内容（问题、回答、表格、文件）均可一键复制
- 生成文件在全屏预览页预览，不影响对话阅读
- 简单对话（无工具调用）的体验不因新增功能而变重

---

## Scope Boundaries

- **In scope:**
  - 三轨 SSE 事件消费（messages/custom/values/events）
  - 规划步骤可折叠面板
  - Token 用量实时显示
  - AI 生成追问建议
  - 全文复制（气泡、回答、表格、文件）
  - Artifact 全屏预览页（移动端）
  - 流式 markdown 渲染
  - 所有新增组件遵循现有暗黑模式方案（CSS 变量 + `van-config-provider`）

- **Out of scope (deferred):**
  - 模型选择器（Numina 模型由服务端配置，不暴露给用户 — 与 May 27 UX Fusion 决策一致）
  - 推理深度独立控制（由 4 档模式推导，不单独暴露 — 与 May 27 UX Fusion 决策一致）
  - 会话重放 UI（values 轨支持未来重放，但完整重放 UI 延期）
  - 反馈事件（点赞/点踩）
  - PDF/Word/Excel 文件生成（HTML/Python 代码文件为 v1 范围；PDF/Word/Excel 需后端 skill 支持，延期）
  - 消息分支导航（1 of N）
  - 子任务卡片（SubtaskCard）编排 — v1 先聚焦单步工具调用可视化

---

## Key Decisions

- **保留 Numina 4 档模式选择器**（flash/thinking/pro/ultra）— 替代 DeerFlow 的 Pro toggle + 推理深度下拉 + 模型选择器。4 档模式映射到 DeerFlow 的 stream context 参数（mode, reasoning_effort, thinking_enabled, is_plan_mode, subagent_enabled）。用户无需额外学习 DeerFlow 的三控件组合。

- **追问建议通过 SSE custom 事件获取** — 而非独立的 REST API 端点。Numina 后端在流式过程中通过 custom 轨发送 suggestion 类型事件。前端在消费 custom 事件时提取建议数据，流完成后渲染为药丸按钮。与 DeerFlow 的独立 `POST /suggestions` 端点不同，Numina 采用流内建议的方式，减少额外请求。

- **Artifact 文件通过独立端点获取** — `GET /api/sessions/{session_id}/artifacts/{filepath:path}`。SSE `values` 事件中的 artifacts 数组提供文件路径列表，前端通过独立端点获取文件内容并在全屏预览页展示。

- **Token 用量通过独立轮询获取** — 不嵌入 SSE 流。前端在流式过程中每 1-2 秒轮询 `GET /api/threads/{id}/token-usage`，返回 `{total_input_tokens, total_output_tokens, total_tokens, by_caller: {lead_agent, subagent, middleware}}`。该端点已存在于 `server/apps/agent/routers/threads.py`。

- **规划步骤面板默认展开** — 与 DeerFlow 行为一致。用户可手动折叠。步骤列表展示所有 `custom` 事件中的工具调用进度。

- **Artifact 全屏预览复用现有 useArtifacts composable** — 现有类型系统（Artifact, ProcessStep, NormalizedAiEvent）已具备 artifact 支持，扩展为移动端全屏预览页。

- **SSE 事件消费扩展 useThreadChat** — 现有 composable 已处理 `messages-tuple` 和 `values` 事件。新增 `custom` 和 `events` 轨的消费，用于规划步骤和工具进度展示。

---

## Dependencies / Assumptions

- **Backend SSE 三轨协议已对齐** — `2026-06-20-deerflow-sse-protocol-alignment-requirements.md` 的后端工作已完成（messages/custom/values 三轨 SSE 转发）。前端依赖后端正确转发 `custom` 事件（工具调用进度、websearch 查询、suggestion 建议等）。

- **Token usage 端点已存在** — `GET /api/threads/{id}/token-usage` 已实现在 `server/apps/agent/routers/threads.py`，返回结构化数据 `{total_tokens, total_input_tokens, total_output_tokens, by_caller: {lead_agent, subagent, middleware}}`。

- **Suggestions 通过 SSE custom 事件传递** — Numina 后端不采用 DeerFlow 的独立 `POST /suggestions` 端点，而是在流式过程中通过 `custom` 轨发送 suggestion 类型事件。前端需在消费 custom 事件时提取建议数据。

- **Artifact 文件通过独立端点获取** — `GET /api/sessions/{session_id}/artifacts/{filepath:path}` 已实现在 `server/apps/backend/app/routers/ai_chat.py`。SSE `values` 事件中的 artifacts 数组提供文件路径列表。

- **Custom SSE 事件格式需确认** — websearch/page-fetch/suggestion 等 custom 事件的具体数据结构需要确认。预期格式类似 `{type: "websearch", query: "..."}` 或 `{type: "suggestion", suggestions: ["...", "...", "..."]}`。

- **LangGraph SDK 客户端兼容** — 现有 `@langchain/langgraph-sdk` Client 的 `runs.stream()` 支持 `stream_mode: ["messages-tuple","values","updates","custom","events"]` 参数。需确认当前版本支持 `custom` 和 `events` 模式。

- **Markdown 渲染库** — 需选择一个 Vue 3 兼容的 markdown 渲染库（如 `markdown-it` + `shiki` 代码高亮，或 `md-editor-v3`）。DeerFlow 使用 Next.js 的 react-markdown，Numina 需要 Vue 等效方案。

- **代码高亮** — Artifact 面板中的代码文件需要语法高亮（如 `shiki` 或 `highlight.js`）。

---

## Outstanding Questions

### Resolve Before Planning

_(All resolved through backend code verification — see Dependencies / Assumptions for confirmed endpoints.)_

### Deferred to Planning

- [Affects R3][Technical] SSE `custom` 事件中 suggestion 类型的具体数据格式。需要确认事件结构（如 `{type: "suggestion", suggestions: ["...", "...", "..."]}`）以正确解析建议文本。
- [Affects R3][Technical] SSE `custom` 事件中 websearch/page-fetch 类型的具体数据格式。需要确认事件结构以正确渲染步骤图标和摘要。
- [Affects R5][Technical] Markdown 渲染库选型：`markdown-it` + `shiki` vs `md-editor-v3` vs 其他 Vue 3 方案。需评估 streaming partial markdown 的支持情况（流式过程中部分 markdown 可能不完整）。
- [Affects R7][Technical] 弹跳三点动画的 Vue 实现方案（CSS animation vs Vue Transition）。
- [Affects R19][Technical] Artifact 面板宽度可调的实现方案（CSS resize vs 自定义拖拽 handler）。
- [Affects R6][Technical] "Download table" 的文件格式（CSV? TSV? HTML table?）。

---

## Related Documents

- [`2026-06-20-deerflow-sse-protocol-alignment-requirements.md`](./2026-06-20-deerflow-sse-protocol-alignment-requirements.md) — Backend SSE 三轨协议对齐（已完成）
- [`2026-05-27-deerflow-chat-ux-fusion-requirements.md`](./2026-05-27-deerflow-chat-ux-fusion-requirements.md) — 前期 UX 融合方案（已被本文档 supersede，范围更广）
- [`2026-06-04-agent-chat-phase-a-requirements.md`](./2026-06-04-agent-chat-phase-a-requirements.md) — Agent 聊天 Phase A 需求
- [`2026-06-04-agent-chat-phase-b-requirements.md`](./2026-06-04-agent-chat-phase-b-requirements.md) — Agent 聊天 Phase B 需求
- [`2026-06-04-agent-chat-phase-c-requirements.md`](./2026-06-04-agent-chat-phase-c-requirements.md) — Agent 聊天 Phase C 需求
