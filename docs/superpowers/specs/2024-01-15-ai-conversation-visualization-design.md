# AI 会话可视化交互设计方案

> 参考 DeerFlow 2 设计，统一 `/ai/chat` 与智能体功能的过程展示与结果呈现

## 1. 项目现状梳理

### 1.1 `/ai/chat` 页面实现

| 层面 | 位置 | 关键点 |
|-----|------|-------|
| 路由 | `frontend/apps/main/src/router/index.ts:274-277` | `path: 'ai/chat'`, 组件 `AIChatPage.vue` |
| 页面 | `frontend/apps/main/src/pages/AIChatPage.vue` | 1200+ 行，消息列表、会话历史、流式响应、deep think/web search 开关 |
| 流式请求 | `frontend/apps/main/src/api/ai.ts:422-459` | `sendChatMessageStream()` → POST `/api/v1/ai/chat/stream` |
| 事件解析 | `frontend/apps/main/src/composables/useAgentEventStream.ts` | NDJSON 行解析 |

### 1.2 流式响应机制

已支持 **SSE/NDJSON over fetch ReadableStream**，非 WebSocket。

事件类型定义在 `frontend/apps/main/src/types/agent-stream.ts`:
```typescript
type AgentEventType =
  | 'session.start' | 'phase.connecting' | 'phase.thinking'
  | 'phase.answering' | 'tool.call' | 'tool.result'
  | 'token.stream' | 'capability.end' | 'capability.error'
```

### 1.3 AI 消息数据结构

UI 侧 Message 接口 (`AIChatPage.vue:485-517`):
```typescript
interface Message {
  id: string
  role: 'user' | 'assistant'
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  content: string
  thinkContent?: string       // 思考内容
  thinkOpen?: boolean         // 思考块展开状态
  thinkDone?: boolean         // 思考完成
  thinkSeconds?: number       // 思考耗时
  thinkManuallyToggled?: boolean // 用户手动切换过
  toolTimeline?: ToolTimelineItem[] // 工具调用时间线
}
```

**已有 `toolTimeline` 数据结构**，支持 `tool.call` / `tool.result` 事件。

### 1.4 "重新生成"交互

已存在 (`AIChatPage.vue:1296-1306`):
- 找到上一条 user 消息
- 删除该 user 消息和当前 assistant 响应
- 将原用户输入填入输入框
- 调用 `onSend()` 重新发送

### 1.5 其他 AI 智能体功能

| 功能 | 页面 | 流式模式 |
|-----|------|---------|
| AI 财务报告 | `AIReportPage.vue` | NDJSON via `useAITask` |
| 资产预警 | `AIAlertsPage.vue` | NDJSON via `useAITask` |
| 资产处置建议 | `AIDisposalPage.vue` | NDJSON via `useAITask` |
| 负债顾问 | `AILiabilityAdvisorPage.vue` | NDJSON via `useAITask` |
| 预算分配 | `AIAllocationPage.vue` | NDJSON via `useAITask` |
| 支出漏洞 | `SpendingLeaksCard.vue` | NDJSON via `useAITask` |

**统一使用 `useAITask` composable + `TaskConsole.vue` 展示**。

### 1.6 已有组件资产

| 组件 | 位置 | 能力 |
|-----|------|------|
| `TaskConsole.vue` | `components/ai/` | 过程展示：状态、phase、思考折叠、答案 Markdown、耗时、错误重试 |
| `ReportCard.vue` | `components/ai/` | 报告卡片：图标+标题+评分徽章+叙述 |
| 消息气泡 | `AIChatPage.vue` 内联 | `.message-row.user`/`.assistant`，`.bubble` 样式 |
| Markdown渲染 | 内联 `marked`+`DOMPurify` | 无独立组件，无语法高亮 |

### 1.7 UI 框架

**Vant 4** (v4.9.22)，通过 `unplugin-vue-components` 自动导入。

---

## 2. DeerFlow 交互模型映射

### 2.1 核心交互模式映射表

| DeerFlow 模式 | 当前项目状态 | 改进方案 |
|---------------|-------------|---------|
| Conversation 容器 | `AIChatPage.vue` 消息列表 | 保持现有，增加自动折叠逻辑 |
| 用户消息气泡 | 已有 `.bubble.user` | 保持现有样式 |
| AI 处理中消息 | `thinkContent` + `toolTimeline` 分离 | 统一为 **AiProcessBlock** |
| AI 最终消息 | `content` + `marked` 渲染 | 统一为 **AiFinalAnswer** |
| Reasoning 折叠 | `thinkOpen` / `thinkDone` | 运行中展开，完成后折叠 |
| Tool Call 展示 | 简单列表，原始名称 | 步骤化展示 + 友好文案 |
| Subagent/Task | 无展示 | 可扩展，暂不在 MVP |
| 报告突出展示 | `TaskConsole` + 外部卡片 | 过程折叠 + 报告主体 |

### 2.2 视觉设计要点

- **过程块样式**：渐变背景 + 圆角卡片，左侧 AI logo 动图
- **展开/收起指示**：右上角箭头图标 (◀/▼)，无文字提示
- **状态图标**：完成 ✓ (绿色)、运行中 pulse 动画 (蓝紫)、失败 ✗ (红色)
- **光影效果**：思考/调用中的文字 shimmer 动画
- **工具友好文案**：`web_search` → "搜索文档"，`read_file` → "读取文件"
- **长内容截断**：默认截断，可点击展开

---

## 3. 组件清单

### 3.1 新增组件

| 组件 | 用途 | MVP 必需 |
|-----|------|---------|
| `AiProcessBlock.vue` | 过程块容器：思考 + 工具调用步骤列表 | ✓ |
| `AiProcessStep.vue` | 单个步骤：思考/工具调用/进度 | ✓ |
| `AiToolCallStep.vue` | 工具调用步骤：参数摘要 + 结果摘要 | ✓ |
| `AiFinalAnswer.vue` | 最终答案：Markdown 渲染 | ✓ |

### 3.2 复用/改造组件

| 组件 | 改造内容 |
|-----|---------|
| `AIChatPage.vue` | 集成 `AiProcessBlock`，替换内联思考块 |
| `TaskConsole.vue` | 保留作为简单场景，复杂场景用新组件 |
| `useAITask.ts` | 保持不变，数据结构兼容 |
| 消息气泡样式 | 保持现有 CSS |

### 3.3 组件接口设计

#### AiProcessBlock

```typescript
interface AiProcessBlockProps {
  status: 'running' | 'done' | 'error'
  elapsedMs: number
  steps: AiProcessStep[]
  defaultExpanded?: boolean // 运行中 true，完成后 false
}

interface AiProcessBlockEmits {
  (e: 'toggle-expand', expanded: boolean): void
}
```

#### AiProcessStep

```typescript
type AiProcessStep =
  | { type: 'reasoning'; id: string; content: string; status: 'streaming' | 'done'; elapsedMs?: number }
  | { type: 'tool_call'; id: string; toolName: string; displayName: string; icon: string; argsSummary: string; status: 'pending' | 'running' | 'done' | 'error'; resultSummary?: string; elapsedMs?: number }
  | { type: 'progress'; id: string; title: string; description?: string; status?: 'running' | 'done' | 'error' }
```

#### AiFinalAnswer

```typescript
interface AiFinalAnswerProps {
  content: string
  streaming?: boolean
  isReport?: boolean // 智能体功能为 true，添加报告样式
  reportTitle?: string
  reportMeta?: { generatedAt: string; itemCount: number }
}
```

---

## 4. 数据 Adapter 清单

### 4.1 事件标准化

新增 `frontend/apps/main/src/utils/aiEventNormalizer.ts`:

```typescript
type NormalizedAiEvent =
  | { type: 'message_delta'; messageId: string; content: string }
  | { type: 'reasoning_delta'; messageId: string; content: string }
  | { type: 'tool_call'; messageId: string; toolCallId: string; name: string; args: unknown }
  | { type: 'tool_result'; toolCallId: string; content: unknown }
  | { type: 'phase_change'; phase: 'connecting' | 'thinking' | 'answering' | 'done' }
  | { type: 'error'; error: string }

function normalizeAiStreamEvent(event: AgentEvent): NormalizedAiEvent
```

### 4.2 工具友好文案映射

新增 `frontend/apps/main/src/utils/toolDisplayMapping.ts`:

```typescript
const TOOL_DISPLAY_MAP: Record<string, { displayName: string; icon: string; argsTemplate: string; resultTemplate: string }> = {
  'web_search': { displayName: '搜索文档', icon: '🔍', argsTemplate: '查询：{query}', resultTemplate: '找到 {count} 个结果' },
  'read_file': { displayName: '读取文件', icon: '📄', argsTemplate: '文件：{path}', resultTemplate: '读取 {lines} 行' },
  'get_asset_list': { displayName: '获取资产列表', icon: '📊', argsTemplate: '筛选：{filter}', resultTemplate: '返回 {count} 条资产' },
  // ...
}

function getToolDisplayInfo(toolName: string, args: unknown, result: unknown): { displayName: string; icon: string; argsSummary: string; resultSummary: string }
```

### 4.3 长内容截断

新增 `frontend/apps/main/src/utils/contentTruncator.ts`:

```typescript
function truncateContent(content: string, maxChars: number = 200): { truncated: string; isTruncated: boolean; fullContent: string }
function truncateJson(obj: unknown, maxChars: number = 300): { summary: string; isTruncated: boolean; fullJson: string }
```

---

## 5. `/ai/chat` 状态流转设计

### 5.1 用户发送消息

```
用户输入 → 追加 UserBubble → 创建 AssistantTurn(status=running, expanded=true)
         → 开启 SSE 连接 → 接收事件 → 更新 ProcessBlock.steps
```

### 5.2 运行中

```
phase.connecting → ProcessBlock 显示 "连接中..."
phase.thinking   →追加 reasoning step，content 流式追加
tool.call        → 追加 tool_call step，status=running
tool.result      → 更对应 step，status=done，添加 resultSummary
phase.answering  → FinalAnswer 开始流式展示
```

### 5.3 完成后

```
capability.end   → ProcessBlock.status = done
                 → ProcessBlock.defaultExpanded = false（自动折叠）
                 → FinalAnswer.streaming = false
                 → 显示操作按钮（复制、重新生成）
```

### 5.4 错误/中断

```
capability.error → ProcessBlock.status = error
                 → 显示错误信息 + 重试按钮
```

---

## 6. 智能体功能状态流转设计

### 6.1 运行中

```
点击生成 → 页面主体显示 AssistantTurn
         → ProcessBlock(expanded=true) 显示步骤
         → FinalAnswer(streaming=true) 报告骨架屏 → 实时填充
         → 结构化报告卡片同步生成
```

### 6.2 完成后

```
ProcessBlock(expanded=false) 自动折叠
FinalAnswer(isReport=true) 突出展示报告
结构化报告数据完整呈现
显示重新生成按钮
```

### 6.3 已完成记录再次进入

```
加载历史数据 → 直接展示 FinalAnswer(isReport=true)
             → ProcessBlock(expanded=false) 折叠，steps 从历史数据恢复
             → 用户可展开查看历史过程
             → 重新生成按钮可用
```

---

## 7. 重新生成交互保留

### 7.1 `/ai/chat` 重新生成

保持现有逻辑：
- 找上一条 user 消息
- 删除 user + assistant
- 重新发送

适配：
- 清空 `ProcessBlock.steps`
- 重置 `ProcessBlock.status = running`
- 重置 `FinalAnswer.content = ''`

### 7.2 智能体功能重新生成

- 重置 `ProcessBlock.steps = []`
- 重置 `ProcessBlock.status = running`
- 清空报告数据
- 重新发起 SSE 请求

---

## 8. 风险与应对

| 风险 | 影响 | 应对策略 |
|-----|------|---------|
| 后端事件缺字段 | 无法展示完整步骤 | adapter 层提供默认值，不阻塞展示 |
| reasoning 内容不可用 | 思考步骤空白 | 跳过 reasoning step，只展示 tool call |
| 工具结果过大 | UI 膨胀 | 截断 + 展开，限制默认展示 200 字符 |
| 流式中断 | 状态卡死 | 超时检测 + error 状态 + 重试按钮 |
| 历史记录回放 | steps 数据缺失 | 从 messages-tuple 重建，或标记"过程不可用" |
| 移动端展示 | 过程块过宽 | 响应式设计，移动端默认折叠 |

---

## 9. MVP 范围

### 9.1 必需完成

- `/ai/chat` 用户气泡 + AI 最终回答（保持现有）
- **AiProcessBlock**：过程块容器
- **AiProcessStep**：思考 + 工具调用步骤
- reasoning 展示（流式追加）
- tool call / tool result 展示（参数摘要 + 结果摘要）
- 运行中展开，完成后自动折叠
- 右上角箭头展开/收起（无文字提示）
- 智能体功能复用 AiProcessBlock + AiFinalAnswer
- 已完成结果进入页面时折叠过程块并展示报告
- 重新生成按钮保持可用

### 9.2 暂缓内容

- 复杂 artifact 侧边栏
- 多分支 message branch
- token usage 细分统计
- follow-up suggestions
- subagent 复杂详情页
- tool result 富媒体预览
- 语法高亮代码块

---

## 10. 分阶段落地计划

### Phase 1：基础组件 (1-2 天)

1. 创建 `AiProcessBlock.vue`
2. 创建 `AiProcessStep.vue` / `AiToolCallStep.vue`
3. 创建 `AiFinalAnswer.vue`
4. 创建 `aiEventNormalizer.ts`
5. 创建 `toolDisplayMapping.ts`
6. 创建 `contentTruncator.ts`

### Phase 2：集成到 `/ai/chat` (1 天)

1. 改造 `AIChatPage.vue` 使用新组件
2. 适配现有事件处理逻辑
3. 保持重新生成交互
4. 测试多轮对话

### Phase 3：集成到智能体功能 (1 天)

1. 改造 `AIReportPage.vue`
2. 改造其他智能体页面
3. 测试历史记录回放

### Phase 4：打磨与测试 (1 天)

1. 响应式适配
2. 动效优化
3. 边界情况测试
4. 性能优化

---

## 11. 验收标准

### `/ai/chat`

- 用户发送消息后，用户气泡立即出现
- AI 运行时，过程块展开并持续更新
- reasoning/tool call 能按事件顺序展示
- AI 最终答案能流式展示
- AI 完成后，过程块自动折叠
- 用户可以展开查看完整过程
- 用户可以继续下一轮对话
- 重新生成仍然可用

### 智能体功能

- 运行中展示过程块
- 完成后过程块折叠
- 报告信息突出展示
- 已完成历史记录进入页面时不重新运行
- 重新生成仍然可用

### 工程质量

- 不新增 agent runtime/harness
- 不引入竞争性 agent 框架
- UI 组件可复用
- 数据 adapter 与 UI 解耦
- 长 tool result 有截断/展开机制
- 流式中断有错误态
- TypeScript 类型清晰
- 保留现有业务功能和交互