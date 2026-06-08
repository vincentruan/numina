---
title: Agent 执行过程交互优化
created: 2026-06-08
status: draft
scope: frontend-main, backend-agent
---

# Agent 执行过程交互优化

## 问题背景

当前智能体问答页 `/ai/chat` 的 Agent 执行过程存在以下交互问题：

1. **用户问题重复进入 AI 回答** - 模型输出中包含用户原始问题
2. **Prompt/User Context 泄漏** - `<system_instructions>`、`<user_question>` 标签内容可能出现在输出中
3. **MCP 调用显示成两条** - 工具调用参数和结果同时显示，视觉上重复
4. **执行过程顺序问题** - 历史消息的执行过程脚注在回答底部，不符合认知顺序
5. **状态文案不友好** - 显示原始事件名而非用户可理解的描述
6. **参数默认展示** - 工具参数默认显示，包含冗长或敏感信息
7. **内容过滤缺失** - 缺乏防御性过滤机制

## 设计目标

- Agent 回答从"普通消息气泡"升级为"执行过程 + 最终结果"结构化体验
- 执行过程全宽展示，不受聊天气泡宽度限制
- 默认只展示用户可理解的概括信息，技术细节折叠
- 最终回答干净，不含用户原问题、内部 Prompt、调试信息
- 状态文案动态生成，基于 MCP 描述而非静态映射
- 前端防御性过滤作为双重保障

## 约束条件

- 不重写 DeerFlow2 agent 核心逻辑
- 不破坏现有模型选择、高可用、租户隔离、权限校验、会话机制
- 不为展示过程而暴露内部 Prompt 或敏感参数
- 优先复用现有组件和接口
- 能前端解决的，不轻易改后端协议

## 修改文件清单

### 后端 (2 文件)

| 文件 | 改动 | 原因 |
|------|------|------|
| `prompts/chat/default_system_prompt.md` | 新增"输出规范"章节 | 防止模型输出 XML 标签和重复用户问题 |
| `services/stream_events.py` | 扩展 SENSITIVE_KEYS | 增加对 Prompt 相关字段的脱敏 |

### 前端 (5 文件)

| 文件 | 改动 | 原因 |
|------|------|------|
| `pages/AIChatPage.vue` | 调整历史消息渲染顺序 | 执行过程放在回答之前 |
| `components/ai/AiStepBlock.vue` | 优化步骤显示 | 状态文案动态生成、参数默认隐藏 |
| `components/ai/AiProcessFootnote.vue` | 重构为 AiProcessSummaryCard | 放在回答之前而非底部 |
| `utils/aiEventNormalizer.ts` | 无改动 | 已正确合并 tool.call/tool.result |
| `utils/contentFilter.ts` | 新增 | 防御性内容过滤器 |

---

## 一、后端 Prompt 工程修复

### 1.1 修改文件

`server/apps/agent/prompts/chat/default_system_prompt.md`

### 1.2 新增内容

在现有 prompt 末尾添加"输出规范"章节：

```markdown
## 输出规范

**绝对禁止**：
1. 在回答开头或任何位置重复用户的问题或请求
2. 输出 `<system_instructions>` 或 `<user_question>` 标签或其内容
3. 输出 `User Context:`、`System Prompt:`、`Context:` 等内部上下文块
4. 输出原始任务描述、工具参数完整 payload、调试日志
5. 输出 tenantId、内部用户标识、内部接口地址

**必须遵守**：
- 直接回答用户问题，不要"你问的是..."这类开场白
- 如果需要引用上下文，用自然语言摘要（如"根据您家庭数据..."），不输出原始块
- 工具调用结果只在必要时简要提及（如"已查询到3项资产"），不输出完整 JSON
```

### 1.3 验收标准

- 输入"我们家净资产是多少？"后，最终回答直接给结论，不重复问题
- 模型输出不含 `<system_instructions>`、`<user_question>` 标签
- 模型输出不含 `User Context:`、`System Prompt:` 等上下文块

---

## 二、前端防御性过滤

### 2.1 新增文件

`frontend/apps/main/src/utils/contentFilter.ts`

### 2.2 实现逻辑

```typescript
/**
 * 防御性内容过滤器
 * 识别并移除模型可能输出的违规内容（XML 标签、上下文块、重复问题等）
 */

// 禁止输出的模式列表
const FORBIDDEN_PATTERNS: RegExp[] = [
  // XML 标签及其内容（捕获整个标签块）
  /<system_instructions>[\s\S]*?<\/system_instructions>/gi,
  /<user_question>[\s\S]*?<\/user_question>/gi,
  
  // 上下文块标记
  /^User Context:.*$/gm,
  /^System Prompt:.*$/gm,
  /^Context:.*$/gm,
  /^Internal Context:.*$/gm,
  
  // 重复用户问题模式（中文常见开场白）
  /^你问的是[：:].*$/gm,
  /^问题是[：:].*$/gm,
  /^您的问题是[：:].*$/gm,
  /^关于您问的[：:].*$/gm,
  
  // 内部标识符泄漏
  /^tenantId:.*$/gm,
  /^family_id:.*$/gm,
  /^user_id:.*$/gm,
  /^internal_user_id:.*$/gm,
]

/**
 * 过滤 AI 回答内容
 * @param raw 原始回答文本
 * @returns 过滤后的干净文本
 */
export function filterAIContent(raw: string): string {
  let filtered = raw
  
  for (const pattern of FORBIDDEN_PATTERNS) {
    filtered = filtered.replace(pattern, '')
  }
  
  // 清理多余空行（过滤后可能留下连续空行）
  filtered = filtered.replace(/\n{3,}/g, '\n\n')
  
  // 清理开头和结尾的空白
  return filtered.trim()
}
```

### 2.3 应用位置

在 `AIChatPage.vue` 的 `handleEvent` 函数中，渲染 Markdown 之前调用过滤器：

```typescript
// 原代码
textRaw += event.token ?? ''
messages.value[msgIdx].content = textRaw

// 新增：在渲染前过滤
const filteredContent = filterAIContent(textRaw)
renderMarkdownThrottled(filteredContent, messages.value[msgIdx])
```

### 2.4 验收标准

- 模型输出含 `<system_instructions>` 时，前端最终展示不含该标签
- 模型输出含 `User Context:` 时，前端最终展示不含该文本
- 正常业务内容不受影响（过滤器不过滤合理内容）

---

## 三、执行过程展示优化

### 3.1 设计决策

**方案 B：全宽工作台** - 执行过程始终全宽展示（AgentRunCanvas），不受聊天气泡宽度限制。

### 3.2 实时消息渲染（已正确）

`AIChatPage.vue` 当前实时消息渲染顺序正确：

```
用户问题气泡 → AgentRunCanvas(AiProcessBlock) → bubble-text(最终回答)
```

无需改动实时消息逻辑。

### 3.3 历史消息渲染调整

**修改文件**: `frontend/apps/main/src/pages/AIChatPage.vue`

**改动点**: 
1. 移除 `AiProcessFootnote` 从底部
2. 在 `bubble-text` 之前添加 `AgentRunCanvas` 包装的 `AiProcessBlock`
3. 历史消息默认折叠执行过程

**具体实现**:

```vue
<!-- 历史消息：执行过程在回答之前 -->
<AgentRunCanvas
  v-if="msg.role === 'assistant' && msg.phase === 'done' && shouldShowProcessBlock(msg)"
  :status="getProcessStatus(msg)"
  :elapsed-ms="msg.processElapsedMs || 0"
  :done-step-count="getDoneStepCount(msg)"
  :total-step-count="getTotalStepCount(msg)"
>
  <AiProcessBlock
    :status="getProcessStatus(msg)"
    :elapsed-ms="msg.processElapsedMs || 0"
    :steps="msg.processSteps || buildLegacySteps(msg)"
    :default-expanded="false"  <!-- 历史消息默认折叠 -->
    :phase="msg.phase"
    :reasoning-start-time="msg.reasoningStartTime ?? null"
    :plan-steps="msg.planSteps"
    :plan-source="msg.planSource"
  />
</AgentRunCanvas>

<!-- 最终回答 -->
<div
  v-if="msg.role === 'assistant'"
  class="bubble-text"
  v-html="msg.renderedContent ?? ''"
/>
```

### 3.4 AiProcessFootnote 处理

**方案**: 不删除组件，但改变使用位置。从底部移到回答之前，作为折叠状态的紧凑摘要视图。

未来可考虑重命名为 `AiProcessSummaryCard`，但当前保持组件名不变以减少改动。

### 3.5 验收标准

- 实时消息：执行过程在回答之前，全宽展示
- 历史消息：执行过程卡片在回答之前，默认折叠
- 不再在回答底部显示"查看推理过程"链接

---

## 四、步骤显示优化

### 4.1 修改文件

`frontend/apps/main/src/components/ai/AiStepBlock.vue`

### 4.2 状态文案动态生成

**问题**: 原设计使用静态 `toolStatusMapping.ts`，难以维护。

**方案**: 利用后端已传递的 `displayName` 动态生成状态文案。

**实现**: 在 `AiStepBlock.vue` 中：

```typescript
// 状态文案动态生成（使用 MCP 描述）
const statusText = computed(() => {
  // 使用 displayName（如"获取家庭概览"）而非 name（如"numina-family-data_get_family_overview"）
  const baseName = props.displayName || props.name || '处理'
  
  // 动态添加状态后缀
  if (props.status === 'running') return `正在${baseName}`
  if (props.status === 'done') return `已${baseName}`
  if (props.status === 'error') return `${baseName}失败`
  return baseName
})
```

**后端配合**: 新增 MCP 工具时，只需在 `message_classifier.py` 的 `_TOOL_REGISTRY` 添加一行：

```python
"numina-family-data_new_tool": ("new_type", "新工具描述", "🔧"),
```

前端自动支持，无需额外改动。

### 4.3 参数显示优化

**问题**: 默认显示 `argsSummary`，包含冗长参数。

**方案**:
- running 状态：显示参数摘要（简化格式）
- done/error 状态：隐藏参数，只显示状态
- 点击展开详情时显示完整参数（脱敏后）

**实现**:

```vue
<!-- 参数显示逻辑 -->
<div 
  v-if="status === 'running' || isExpanded" 
  class="tool-args"
>
  <span v-if="!compressed" class="args-label">{{ t('aiProcess.argsLabel') }}</span>
  <span class="args-value">{{ status === 'running' ? simplifiedArgs : argsSummary }}</span>
</div>
```

### 4.4 移除"参数：参数："无意义文本

**问题**: `formatArgsSummary` 函数可能生成"参数：参数："格式。

**方案**: 检查 `formatArgsSummary` 实现，确保不产生重复前缀。

### 4.5 验收标准

- 工具调用 running 时显示"正在获取家庭概览"
- 工具调用 done 时显示"已获取家庭概览"
- 工具调用 error 时显示"获取家庭概览失败"
- 默认不显示参数，点击展开后显示脱敏参数
- 不出现"参数：参数："无意义文本

---

## 五、Markdown 流式渲染

### 5.1 现有能力确认

`AIChatPage.vue` 已有 throttled Markdown 渲染（100ms）:

```typescript
function renderMarkdownThrottled(text: string, target: { content: string; renderedContent?: string }) {
  pendingRenderText = text
  pendingRenderTarget = target
  if (renderTimer) return
  renderTimer = setTimeout(() => {
    renderTimer = null
    if (pendingRenderTarget && pendingRenderText) {
      pendingRenderTarget.renderedContent = renderMarkdown(pendingRenderText)
    }
  }, 100)
}
```

`renderMarkdown` 使用 `marked.parse` + `DOMPurify.sanitize`。

### 5.2 验证点

需要验证：
- 表格流式渲染是否正常（边输出边渲染）
- 列表、加粗、换行、代码块流式渲染是否稳定
- 新的 AgentRunCanvas/AiProcessBlock 容器是否影响 Markdown 样式

### 5.3 可能问题

如果 Markdown 样式被容器 CSS 影响，需要检查：
- `.bubble-text` 的 CSS 是否被 `.agent-run-canvas` 等容器继承或覆盖
- 表格宽度是否在窄屏下溢出

### 5.4 验收标准

- Agent 输出 Markdown 表格时，边输出边正确渲染
- 流式完成后 Markdown 格式完整
- 移动端窄屏下表格可横向滚动，不撑破页面

---

## 六、会话恢复

### 6.1 现有逻辑确认

`AIChatPage.vue` 的 `loadSessionMessages` 函数通过 `streamSessionEvents` 加载 JSONL 历史：

```typescript
async function loadSessionMessages(session: SessionSummary) {
  reader = await streamSessionEvents(session.session_id)
  const normState = createNormalizationState()
  
  while (true) {
    const { done, value } = await reader.read()
    // 解析 JSONL 事件，重建 processSteps
    normalizeAgentEvent(event, normState)
    // ...
  }
}
```

### 6.2 验证点

需要验证：
- 刷新页面后，执行过程步骤是否正确恢复
- 长任务中途退出，重新进入是否能看到最新状态
- 旧会话没有足够事件时是否降级成普通聊天消息

### 6.3 验收标准

- Agent 执行中用户刷新页面，重新进入能看到已有步骤
- 后端 JSONL 继续追加时，前端能继续接收后续事件
- 已完成任务重新进入时，展示完整执行过程和最终回答

---

## 七、安全与脱敏

### 7.1 后端脱敏

`stream_events.py` 已有 `redact_sensitive_fields` 函数处理敏感字段：

```python
SENSITIVE_KEYS: frozenset[str] = frozenset([
    "api_key", "apikey", "key", "password", "pwd", "pass",
    "token", "access_token", "auth_token", "secret", "secret_key",
    "credential", "credentials", "private_key", "private",
])
```

### 7.2 扩展脱敏字段

考虑增加 Prompt 相关字段：

```python
SENSITIVE_KEYS: frozenset[str] = frozenset([
    # ... 现有字段
    "system_prompt",
    "user_context",
    "internal_context",
    "task_description",
])
```

### 7.3 前端脱敏

`contentFilter.ts` 作为双重保障，过滤模型输出的违规内容。

### 7.4 验收标准

- 默认视图不含 system prompt、developer prompt、原始任务提示词
- 不含 token/key/secret、tenantId、内部用户标识
- 展开详情时也显示脱敏后的参数（不含 api_key 等）

---

## 八、文件/报告 Artifact 展示

### 8.1 现有能力确认

已有组件：
- `AiArtifactBadge.vue` - 右下角悬浮徽章显示 Artifact 数量
- `AiArtifactSheet.vue` - 底部弹窗列出所有 Artifact

### 8.2 验证点

需要验证：
- Agent 产出文件时是否正确触发 Artifact 注册
- 移动端文件卡片是否可点击预览/下载
- 没有文件时不显示空 Artifact 区域

### 8.3 验收标准

- Agent 产出文件时，展示为可点击卡片
- 点击后进入预览页或下载
- 没有文件时不显示 Artifact 区域

---

## 九、手动验证 Case 清单

| # | Case | 验证点 |
|---|------|--------|
| 1 | 普通短问答 | 仍可用普通气泡展示 |
| 2 | "我们家净资产是多少？" | 不重复用户问题，不泄漏 User Context/prompt，最终答案干净 |
| 3 | MCP 成功调用 | 只显示一个步骤，从 running 更新到 done，不重复 |
| 4 | MCP 失败/重试 | 步骤状态正确，错误信息友好 |
| 5 | Markdown 表格流式输出 | 边输出边渲染，完成后格式正确 |
| 6 | 长任务刷新恢复 | 重新进入会话能恢复执行过程和最终回答 |
| 7 | Artifact 输出 | 移动端展示为文件卡片/链接，可点击预览或查看 |
| 8 | 深色模式和手机窄屏 | 布局不溢出，表格可滚动，按钮可点击 |

---

## 十、后续建议

### 未覆盖项

1. **模型供应商兼容性测试** - 显式 Prompt 指令需要测试不同模型（Anthropic、OpenAI、国产模型）的响应差异
2. **旧会话降级** - 没有 processSteps 的旧会话如何优雅展示
3. **长时间运行步骤的 loading 效果** - 当前有 pulse 动画，可能需要更明显的进度指示

### 可扩展方向

1. **推理过程折叠展示优化** - 用户可选择性查看推理详情
2. **步骤错误重试交互** - 失败步骤提供一键重试按钮
3. **执行过程缩略时间线** - 对于超长任务，提供缩略视图快速定位

---

## 附录：关键文件位置

```
server/apps/agent/
├── prompts/chat/default_system_prompt.md  # Prompt 文件
├── services/stream_events.py              # 事件流构建器
├── services/message_classifier.py         # 工具元数据注册
└── services/chat_adapter.py               # Prompt 组装逻辑

frontend/apps/main/src/
├── pages/AIChatPage.vue                   # 主聊天页面
├── components/ai/
│   ├── AiProcessBlock.vue                 # 执行过程容器
│   ├── AiStepBlock.vue                    # 单个步骤渲染
│   ├── AiProcessFootnote.vue              # 执行过程脚注
│   ├── AgentRunCanvas.vue                 # 全宽工作台容器
│   ├── AiArtifactBadge.vue                # Artifact 徽章
│   └── AiArtifactSheet.vue                # Artifact 弹窗
├── utils/
│   ├── aiEventNormalizer.ts               # 事件标准化
│   ├── contentFilter.ts                   # 内容过滤器（新增）
│   └── toolDisplayMapping.ts              # 工具显示映射
└── types/agent-stream.ts                  # 类型定义
```