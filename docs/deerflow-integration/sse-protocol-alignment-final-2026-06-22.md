# Numina SSE Protocol Alignment & Streaming Resilience

## 执行摘要

本次任务完成了 Numina AI 聊天 SSE 协议与 DeerFlow Reference 的对齐，以及流式传输的断连感知和资源释放增强。

### 完成了什么
- 审计了 DeerFlow Reference 的 SSE 协议基线（messages/custom/values 三轨事件）
- 审计了 Numina 当前的 AI Chat 调用链
- 发现 Numina **已经** 正确实现了 SSE 三轨输出，核心差距在**断连感知和取消传播**
- 在 4 个后端流式路径中添加了 `request.is_disconnected()` 检查
- 在 `agent_dispatch.py` 中添加了 `cancellation_event` 机制
- 在 `agent_stream.py` 中添加了断连检查和取消事件传播
- 改进了前端 `useThreadChat.ts` 的取消逻辑，添加服务端取消调用
- 改进了前端 `ToolCallList.vue` 的工具状态展示组件

### 源码确认 vs 真机验证
- **源码确认**: DeerFlow Reference SSE 协议、Numina 调用链、SSE 格式 — 全部通过源码静态分析确认
- **源码确认**: DeerFlow Reference 后端 `services.py` 中 `format_sse()` 和 `sse_consumer()` 的 SSE 帧格式
- **未真机验证**: DeerFlow Reference 的登录被 CSRF 保护阻止，无法通过 curl 捕获原始 SSE 流
- **未真机验证**: Numina 的本地服务未运行，无法进行完整的集成测试

---

## DeerFlow Reference 基线

### SSE 样例（源码还原）

DeerFlow Reference 后端通过 `format_sse()` 生成 SSE 帧：

```
event: messages
data: {"type":"ai","content":"Hello","id":"msg-uuid","tool_calls":[...]}

event: custom
data: {"type":"tool_call","tool_call_id":"...","tool_name":"...","args":{...}}

event: values
data: {"messages":[...],"title":"...","artifacts":[...]}

event: end
data: null

event: error
data: {"message":"...","name":"ValueError"}
```

### 三轨事件结构

| 事件 | 描述 | 数据格式 |
|------|------|----------|
| `messages` | AI 文本块 / 工具调用块 | `{type:"ai"|"tool", content, id, tool_calls?, usage_metadata?, additional_kwargs?}` |
| `custom` | 工具执行、进度、建议 | `{type:"tool_call"|"suggestions"|..., ...}` |
| `values` | 状态快照 | `{messages:[...], title?:, artifacts?:}` |
| `end` | 流结束 | `null` |
| `error` | 流错误 | `{message, name, ...}` |
| `metadata` | 运行元数据 | `{run_id, attempt, ...}` |

### 前端消费方式

- 使用 `fetch` + `ReadableStream` (非 EventSource)
- `useStream` React hook 消费 SSE 帧
- 消息分组为 6 种类型: human, assistant, tool_call, tool_result, assistant:thinking, assistant:processing

### 关键源码路径

| 路径 | 文件 |
|------|------|
| SSE 格式化 | `backend/app/gateway/services.py:format_sse()` |
| SSE 消费生成器 | `backend/app/gateway/services.py:sse_consumer()` |
| 运行创建 | `backend/app/gateway/services.py:start_run()` |
| 断连处理 | `backend/app/gateway/services.py:sse_consumer()` finally 块 |
| 前端 SSE 消费 | `frontend/src/core/api/stream-mode.ts` |
| 前端流式 hook | `frontend/src/components/workspace/chats/use-thread-chat.ts` |
| 前端消息分组 | `frontend/src/core/messages/utils.ts` |

---

## Numina 现状审计

### 当前调用链

```
Frontend (AIChatBox.vue)
  → useThreadChat.sendMessage()
    → getClient().runs.stream() [LangGraph SDK]
      → POST /api/threads/{id}/runs/stream [Backend Proxy / gateway.py]
        → POST /api/threads/{id}/runs/stream [Agent / runs.py]
          → create_family_adapter().typed_stream_dispatch()
            → DeerFlow Harness astream()
          → format_sse() → yield SSE frames
```

也有旧的代理路径：
```
Frontend → POST /api/v1/ai/chat/stream [Backend / ai_chat.py]
  → POST /agent/{agent_id}/stream [Agent / agent_stream.py]
    → stream_agent_dispatch() [agent_dispatch.py]
      → make_lead_agent().astream()
      → NDJSON events
```

### 发现的问题

| # | 问题 | 风险等级 | 位置 |
|---|------|----------|------|
| 1 | `request.is_disconnected()` 未检查 | **P0** | `runs.py _sse_generator`, `agent_dispatch.py astream loop`, `ai_chat.py proxy_stream`, `gateway.py _simple_stream` |
| 2 | 断连时取消未传播到 agent astream | **P0** | `agent_dispatch.py` 没有取消信号机制 |
| 3 | 前端取消未发服务端 cancel | **P1** | `useThreadChat.ts cancelStream()` |
| 4 | ToolCallList 状态展示不完整 | **P1** | `ToolCallList.vue` 缺少状态图标和标签 |
| 5 | AIChatBox.vue 可进一步模块化 | **P1** | 组件逻辑可拆分为 composable |

### 已确认正常的功能 ✅

- SSE 三轨输出 (`messages`, `custom`, `values`, `error`, `end`)
- 前端 SSE 消费 (`messages-tuple`, `values`, `custom`, `error`, `end`)
- 异步流式 (`async for`, 无事件循环阻塞)
- 租户隔离 (`X-Family-Id` 贯穿全链路)
- SSE 格式 (`format_sse()` 输出标准 `event:` / `data:` 帧)
- try/finally 资源释放

---

## Gap Matrix

| 维度 | DeerFlow Reference | Numina 修改前 | Numina 修改后 | 风险关闭 |
|------|-------------------|---------------|---------------|----------|
| **SSE 协议** | event: messages/custom/values/end/error | ✅ 已实现 | ✅ 不变 | ✅ |
| **SSE 格式** | `event: X\ndata: Y\n\n` | ✅ `format_sse()` | ✅ 不变 | ✅ |
| **Token 流式** | type: "ai", content 增量 | ✅ `messages-tuple` | ✅ 不变 | ✅ |
| **工具事件** | type: "tool_call", "tool_result" | ✅ `custom` 事件 | ✅ 不变 | ✅ |
| **状态快照** | values → messages[] | ✅ 已消费 | ✅ 不变 | ✅ |
| **结束事件** | end → null | ✅ 已实现 | ✅ 不变 | ✅ |
| **错误事件** | error → {message, name} | ✅ 已实现 | ✅ 不变 | ✅ |
| **断连检测** | `request.is_disconnected()` + cancel | ❌ 缺失 | ✅ 4 路径添加 | ✅ |
| **取消传播** | run_mgr.cancel() | ❌ 缺失 | ✅ cancellation_event | ✅ |
| **前端取消** | AbortController | ✅ 已使用 | ✅ + 服务端 cancel | ✅ |
| **工具 UI** | 状态图标 + 标签 | ❌ 仅显示工具名 | ✅ 状态 + 图标 + 标签 | ✅ |
| **租户隔离** | X-Family-Id | ✅ 已实现 | ✅ 不变 | ✅ |
| **资源释放** | finally 块 | ✅ try/finally | ✅ 不变 | ✅ |

---

## 核心改动说明

### 后端

| 文件 | 改动 | 原因 |
|------|------|------|
| `server/apps/agent/routers/runs.py` | 在 `_sse_generator()` 循环中添加 `request.is_disconnected()` 检查 | 断连时停止流式传输，释放资源 |
| `server/apps/agent/services/agent_dispatch.py` | 添加 `cancellation_event` 参数，在 astream 循环中检查 | 使 agent 流式可被取消 |
| `server/apps/agent/routers/agent_stream.py` | 添加断连检查 + cancellation_event 传播 + try/finally | 断连时通知 agent_dispatch 停止 |
| `server/apps/backend/app/routers/ai_chat.py` | 在 `proxy_stream()` 中添加断连检查 | 后端代理层断连感知 |
| `server/apps/backend/app/routers/gateway.py` | 在 `_simple_stream()` 中添加断连检查 | LangGraph SDK 代理层断连感知 |

### 前端

| 文件 | 改动 | 原因 |
|------|------|------|
| `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` | 在 `cancelStream()` 中添加服务端 `client.runs.cancel()` 调用 | 确保取消传播到服务端 |
| `frontend/apps/main/src/components/chat/ToolCallList.vue` | 添加状态图标、标签、中文文案 | 工具执行状态可视化 |

---

## 重构前后核心方案对比

| 项目 | 重构前 | 重构后 |
|------|--------|--------|
| **SSE 协议** | messages/custom/values/error/end | 不变（已对齐） |
| **并发模型** | async for 无阻塞 | 不变（已正确） |
| **资源释放** | try/finally 仅覆盖正常完成 | try/finally + 断连检测 + 取消传播 |
| **租户隔离** | X-Family-Id 贯穿全链路 | 不变 |
| **前端体验** | 工具名显示 + 英文 Stop 按钮 | 状态图标 + 中文标签 + 服务端取消 |
| **错误处理** | SSE error 事件 | 不变 + 断连日志 |

---

## 验证结果

### 通过的命令

| 命令 | 结果 |
|------|------|
| `ruff check` (所有修改文件) | ✅ 通过 |
| `pytest tests/agent/unit/` | ✅ 通过 |
| `pnpm typecheck` (frontend/apps/main) | ✅ 通过 |

### 未执行（本地服务未运行）

| 验证 | 原因 |
|------|------|
| curl SSE 验证 | 后端服务未启动 |
| 端到端流式对话测试 | 前端 + 后端均未启动 |
| 断连场景手动验证 | 需要运行后端服务 + curl |

---

## 剩余风险与后续建议

1. **低风险**: `agent_stream.py` 中的 `_stream_events()` 现在在断连时设置 `cancellation_event` 并 break，但 astream 内部可能仍有一些缓冲数据未处理。建议后续在 agent_dispatch 中添加更细粒度的取消检查点。

2. **低风险**: 前端 `cancelStream()` 使用 `client.runs.cancel()` 是 fire-and-forget，不等待服务端确认。这在网络延迟高时可能 cancel 请求晚于流式请求完成。当前实现已经足够好——AbortController 会先中断 HTTP 流。

3. **中风险**: DeerFlow Harness 的 `typed_stream_dispatch()` 内部没有取消机制。如果 DeerFlow 升级后引入了原生取消支持，应迁移使用。当前通过断连后 `break` 出循环的方式依赖于 Python 的 async generator 垃圾回收来释放资源。

4. **建议**: 后续可添加：
   - 可观测性指标：流式请求延迟、断连率、资源释放延迟
   - 更丰富的前端工具卡片 UI（类似 DeerFlow Reference 的展开/折叠）
   - 历史消息回放的 event-by-event 重放（当前使用 state snapshot）
