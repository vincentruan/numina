---
title: AI Chat 处理过程展示优化
created: 2026-06-09
status: draft
scope: frontend-main, backend-agent
---

# AI Chat 处理过程展示优化

## 问题背景

当前智能体问答页 `/ai/chat` 的处理过程展示存在以下问题：

1. **历史会话处理过程丢失** - 重新进入页面后，看不到执行过程（思考、工具调用等）
   - **Root cause:** Journal 事件命名（`tool.call_started/tool.call_completed`）与 Streaming 协议（`tool.call/tool.result`）不一致，导致 Frontend Normalizer 无法识别历史事件
2. **实时流式工具展示两次** - 工具调用从 running → done 状态切换时，参数在两个状态都可见
3. **回答宽度拥挤** - `.bubble { max-width: 86% }` 限制了展示宽度
4. **Prompt 内容泄漏** - 模型可能输出联网搜索、思考过程等提示词内容

> **问题依赖关系：** #1 由事件命名不一致引起，通过 §一、§二 解决；#2 由状态过渡无顺序控制引起，通过 §四 解决。

## 设计目标

- 历史会话和实时流式展示一致的处理过程
- 工具调用从 running → done 平滑过渡，不重复展示参数
- 统一事件命名，降低维护成本
- 回答宽度舒适，充分利用页面空间
- 最终回答干净，不含内部 Prompt 内容

## 约束条件

- 不破坏现有 streaming 协议
- 不破坏现有会话恢复机制
- 旧会话兼容性：支持已存储的旧格式事件
- Journal 写入失败不影响 streaming（防御性编程）

## Architecture Decisions

1. **统一事件命名** - Journal 使用 `tool.call` / `tool.result`，与 streaming 事件类型一致
2. **实时写入 Journal** - 在发送 streaming 事件时同时调用 journal.write
3. **CSS Transition 优化** - 使用 CSS transition 而非重新渲染来处理状态切换
4. **Frontend Normalizer 兼容** - 支持 `tool.call` 和 `tool.call_started` 两种格式

---

## 一、Backend Journal 事件命名统一

### 1.1 修改文件

`server/apps/agent/services/session_journal.py`

### 1.2 改动内容

将事件类型改为与 streaming 一致：

```python
# write_tool_call 方法
event = _make_event(
    "tool.call",  # 原为 "tool.call_started"
    session_id=session_id,
    family_id=family_id,
    actor="assistant",
    visibility="public",
    payload={
        "tool": {  # 结构与 streaming 事件一致
            "id": tool_id,
            "name": tool_name,
            "display_name": tool_name,  # 后续可扩展
            "icon": "tool",
            "arguments": arguments,
        }
    },
)

# write_tool_result 方法
event = _make_event(
    "tool.result",  # 原为 "tool.call_completed"
    session_id=session_id,
    family_id=family_id,
    actor="tool",
    visibility="public",
    payload={
        "tool_id": tool_id,
        "result": {
            "success": success,
            "execution_time_ms": execution_time_ms,
            "error": error,
        }
    },
)
```

### 1.3 验收标准

- Journal 写入的事件类型为 `tool.call` 和 `tool.result`
- Payload 结构与 streaming EventStreamBuilder 一致

---

## 二、Backend 持久化 Tool 事件

### 2.1 修改文件

- `server/apps/agent/services/orchestrator.py`
- `server/apps/agent/services/agent_dispatch.py`

### 2.2 改动内容

在发送 streaming tool 事件后，调用 journal 方法：

#### orchestrator.py - `_process_deerflow_chunk` 函数中

```python
if chunk.type == "tool_call":
    # ... 发送 streaming 事件 ...
    yield evt.to_ndjson()

    # 新增：持久化到 journal
    try:
        session_journal.write_tool_call(
            family_id=family_id,
            session_id=effective_thread_id,
            tool_name=tool_name,
            tool_id=backend_id,
            arguments=args,
        )
    except Exception as e:
        logger.warning("[orchestrator] journal write_tool_call failed: %s", e)

if chunk.type == "tool_result":
    # ... 发送 streaming 事件 ...
    yield builder.tool_result(...).to_ndjson()

    # 新增：持久化到 journal
    try:
        session_journal.write_tool_result(
            family_id=family_id,
            session_id=effective_thread_id,
            tool_id=backend_id,
            success=True,
            execution_time_ms=0,  # TODO: streaming path lacks timing metadata; keep 0 for now
        )
    except Exception as e:
        logger.warning("[orchestrator] journal write_tool_result failed: %s", e)
```

#### agent_dispatch.py - `_stream_deerflow_response` 函数中（约 571-602 行）

```python
if kind == "tool_call":
    for call in _extract_tool_calls(msg):
        # ... 发送 streaming 事件 ...
        yield evt.to_ndjson()

        # 新增：持久化到 journal
        try:
            session_journal.write_tool_call(
                family_id=family_id,
                session_id=session_id,
                tool_name=tname,
                tool_id=backend_id,
                arguments=call["args"],
            )
        except Exception as e:
            logger.warning("[agent_dispatch] journal write_tool_call failed: %s", e)
    continue

if kind == "tool_result":
    # ... 发送 streaming 事件 ...
    yield builder_events.tool_result(...).to_ndjson()

    # 新增：持久化到 journal
    try:
        session_journal.write_tool_result(
            family_id=family_id,
            session_id=session_id,
            tool_id=backend_id,
            success=True,
            execution_time_ms=0,
        )
    except Exception as e:
        logger.warning("[agent_dispatch] journal write_tool_result failed: %s", e)
    continue
```

### 2.3 验收标准

- 流式对话后，JSONL 文件包含 `tool.call` 和 `tool.result` 事件
- Journal 写入失败不影响 streaming 继续执行

---

## 三、Frontend Normalizer 兼容处理

### 3.1 修改文件

`frontend/apps/main/src/utils/aiEventNormalizer.ts`

### 3.2 改动内容

添加对旧格式的兼容处理：

```typescript
case 'tool.call':
case 'tool.call_started':  // 兼容旧格式
  if (event.tool || event.toolName) {
    // 统一处理：提取 tool 信息
    const toolInfo = event.tool || {
      id: event.toolId,
      name: event.toolName,
      display_name: event.toolName,
      icon: event.icon || 'tool',
      arguments: event.arguments || {},
    };
    // ... 创建 step ...
  }
  break;

case 'tool.result':
case 'tool.call_completed':  // 兼容旧格式
  // 统一处理
  break;
```

### 3.3 验收标准

- 新格式 `tool.call/tool.result` 正常处理
- 旧格式 `tool.call_started/tool.call_completed` fallback 处理
- 历史加载正确重建 processSteps

---

## 四、Frontend UI 平滑过渡

### 4.1 修改文件

`frontend/apps/main/src/components/ai/AiStepBlock.vue`

### 4.2 状态显示矩阵

`AiStepBlock.vue` 支持 6 种状态，需明确每种状态下 args/result 的显示规则：

| Status | Args 可见？ | Result 可见？ | Default 状态 |
|--------|-------------|---------------|--------------|
| `pending` | ❌ hidden | ❌ hidden | collapsed |
| `streaming` | ✅ visible (实时更新) | ❌ hidden | expanded |
| `running` | ✅ visible | ❌ hidden | expanded |
| `done` | ⚠️ collapsed (可展开) | ✅ visible | compressed |
| `error` | ✅ visible (诊断用途) | ✅ visible (error msg) | expanded |
| `failed` | ✅ visible | ✅ visible (failure msg) | expanded |

**说明：**
- `pending`: 工具尚未开始执行，无内容显示
- `streaming`: 流式输出中，args 实时更新（如部分参数）
- `running`: 工具执行中，显示完整 args
- `done`: 执行完成，默认折叠 args（compressed），用户可点击展开查看
- `error`/`failed`: 失败状态，args 和 result 都展开显示，便于用户诊断问题

### 4.3 CSS Transition 改动内容

添加 CSS transition 实现平滑过渡，使用 `mode="out-in"` 确保顺序过渡无重叠：

```vue
<!-- 参数显示区域：先淡出再淡入 result -->
<Transition name="args-fade" mode="out-in">
  <div v-if="status === 'running' || isExpanded" class="tool-args">
    ...
  </div>
</Transition>

<!-- 结果显示区域 -->
<Transition name="result-fade">
  <div v-if="status === 'done' || status === 'error'" class="tool-result">
    ...
  </div>
</Transition>
```

> **注意：** `mode="out-in"` 确保 args 完全淡出后 result 才开始淡入，过渡总时长为 0.4s（args leave 0.2s + result enter 0.2s）。移动端可通过 `prefers-reduced-motion` 禁用动画减少等待感。

```css
/* 参数淡出 */
.args-fade-enter-active,
.args-fade-leave-active {
  transition: opacity 0.2s ease;
}
.args-fade-enter-from,
.args-fade-leave-to {
  opacity: 0;
}

/* 结果淡入 */
.result-fade-enter-active,
.result-fade-leave-active {
  transition: opacity 0.2s ease;
}
.result-fade-enter-from,
.result-fade-leave-to {
  opacity: 0;
}
```

### 4.4 验收标准

- Tool 状态从 running → done 时，args 淡出、result 淡入
- 过渡过程中不同时显示两个状态的内容
- 移动端表现良好（可选禁用动画）

---

## 五、回答宽度优化

### 5.1 修改文件

`frontend/apps/main/src/pages/AIChatPage.vue` (CSS 部分)

### 5.2 改动内容

调整 assistant bubble 宽度：

```css
.bubble {
  max-width: 95%;  /* 原为 86% */
}

/* AgentRunCanvas 保持全宽 */
.agent-run-canvas {
  width: 100%;
  max-width: 100%;
}
```

### 5.3 验收标准

- Assistant 回答充分利用页面宽度
- 移动端不溢出屏幕

---

## 六、Prompt 内容过滤增强

### 6.1 修改文件

`frontend/apps/main/src/utils/contentFilter.ts`

### 6.2 改动内容

添加更多过滤模式：

```typescript
const FORBIDDEN_PATTERNS = [
  // ... 现有模式 ...
  
  // 新增：联网搜索、思考过程等提示词
  /^联网搜索[：:].*$/gm,
  /^正在搜索[：:].*$/gm,
  /^搜索结果[：:].*$/gm,
  /^思考过程[：:].*$/gm,
  /^分析过程[：:].*$/gm,
  /^推理步骤[：:].*$/gm,
  
  // DeerFlow/Agent 内部标识
  /^DeerFlow.*$/gm,
  /^Agent.*执行.*$/gm,
]
```

### 6.3 验收标准

- 模型输出不含"联网搜索"、"思考过程"等提示词开头
- 正常业务内容不受影响

---

## 七、验收 Checklist

| # | Case | 验证点 |
|---|------|--------|
| 1 | 实时流式对话 | 工具调用 running → done 过渡平滑，无两次展示 |
| 2 | 刷新页面重新进入 | 处理过程（思考、工具调用）完整可见 |
| 3 | 旧会话加载 | 兼容旧格式 JSONL，正常展示 |
| 4 | 回答宽度 | Assistant 回答宽度舒适，不拥挤 |
| 5 | Prompt 泄漏 | 最终回答不含提示词内容 |
| 6 | Markdown 表格 | 完整表格正确渲染，有边框/间距样式；大表格支持横向滚动 |

### 7.6 Markdown 表格渲染实现要点

`AiFinalAnswer.vue` 需添加表格 CSS 样式：

```css
/* Markdown 表格样式 */
.answer-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  overflow-x: auto;
  display: block;
}

.answer-markdown :deep(th),
.answer-markdown :deep(td) {
  border: 1px solid var(--separator);
  padding: 6px 10px;
  text-align: left;
}

.answer-markdown :deep(th) {
  background: var(--bg-secondary);
  font-weight: 500;
}

.answer-markdown :deep(tr:nth-child(even) td) {
  background: var(--bg-secondary);
}
```

> **流式表格限制：** Markdown 表格需完整结构（header + separator + rows）才能正确渲染。流式输出过程中，未闭合表格显示为普通文本；闭合后自动转为表格。此为 `marked` 库固有行为，无需特殊处理。

---

## 八、完整交互流程设计

### 8.1 交互阶段定义

智能体对话的完整交互流程，从用户发送问题到最终输出：

| 阶段 | 触发事件 | UI 状态 | AiStepBlock 行为 |
|------|----------|---------|------------------|
| 启动 | 用户发送消息 | `phase: connecting` | 显示连接动画，header shimmer |
| 思考 | `phase.thinking` / reasoning tokens | `phase: thinking` | reasoning step 流式输出，显示耗时 |
| 规划 | `plan.update` 事件 | `planSteps` 更新 | PlanProgressBar 显示 todo 列表，支持点击跳转 |
| 执行 | `tool.call` / `subagent` | `status: running` | AiStepBlock 显示工具调用参数/子任务描述 |
| 完成 | `tool.result` / `subagent.result` | `status: done` | args 折叠，result 显示，CSS 过渡 |
| 输出 | `phase.answering` / text tokens | `phase: answering` | Markdown 内容流式渲染，表格实时更新 |
| 结束 | `capability.end` | `status: done` | AiProcessBlock 收起，展示最终答案 |

**阶段过渡规则：**
- `connecting → thinking`: 收到第一个 `phase.thinking` 或 reasoning token
- `thinking → planning`: 收到第一个 `plan.update` 事件（规划阶段可选）
- `planning → running`: 收到第一个 `tool.call`（进入工具执行）
- `thinking → running`: 收到第一个 `tool.call`（无规划阶段时直接进入执行）
- `thinking → answering`: 无工具调用时直接进入输出阶段
- `running → answering`: 所有工具调用完成后
- `answering → done`: 收到 `capability.end`

> **注：** `running` 状态对应表格中的"执行"阶段，与 §四 4.2 状态矩阵一致。

### 8.2 文件/链接预览 UX（Artifact 输出）

智能体可能输出文件（报告、数据导出等），在移动端 H5 的展示规范：

| Artifact 类型 | 显示形式 | 点击行为 |
|---------------|----------|----------|
| PDF 报告 | 链接卡片 + PDF 图标 | 打开系统 PDF 预览（`<iframe>` 或系统浏览器） |
| 图片文件 | 缩略图 (80x80) + 链接标题 | 全屏预览（支持缩放、滑动关闭） |
| 数据文件 | 链接卡片 + 文件图标 | 文本预览页（限制 100 行，超出显示"点击下载查看完整内容"） |
| 外部链接 | 链接卡片 + 链接图标 | 浏览器新标签打开 |

**卡片样式规范：**
```css
.artifact-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--card-bg);
  border: 1px solid var(--separator);
  border-radius: 8px;
}

.artifact-icon {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}

.artifact-title {
  font-size: 14px;
  color: var(--text-primary);
}

.artifact-size {
  font-size: 12px;
  color: var(--text-secondary);
}
```

> **注：** 当前版本无 artifact 输出能力，此规范为前瞻设计，后续实现文件导出功能时参照。

---

## 九、风险与缓解

| Risk | Impact | Mitigation |
|------|--------|------------|
| Journal 事件格式变更导致旧会话不兼容 | High | Normalizer 添加旧格式 fallback |
| Journal 写入失败影响 streaming | Medium | try/except 包裹，失败不影响 streaming |
| CSS transition 导致移动端卡顿 | Low | `prefers-reduced-motion` 禁用动画 |

---

## 附录：关键文件位置

```
server/apps/agent/
├── services/session_journal.py     # Journal 事件写入
├── services/orchestrator.py        # Streaming + Journal 调用
├── services/agent_dispatch.py      # Streaming + Journal 调用

frontend/apps/main/src/
├── pages/AIChatPage.vue            # 主页面 + CSS
├── components/ai/AiStepBlock.vue   # 步骤展示 + Transition
├── utils/aiEventNormalizer.ts      # 事件标准化
├── utils/contentFilter.ts          # 内容过滤
```