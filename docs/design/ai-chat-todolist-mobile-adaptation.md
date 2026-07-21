---
date: 2026-07-21
module: frontend (main) + agent
problem_type: design-spec
tags: [ai-chat, todolist, mobile, vant, plan-mode, deerflow-parity]
applies_when: 实现/维护 /ai/chat 的 TodoList 移动端组件、todos channel 接入或 TodoMiddleware 挂载
---

# AI 对话 TodoList 移动端适配设计 (U7 / D5)

本设计对齐 DeerFlow `frontend/src/components/workspace/todo-list.tsx` 的 **read-only** 语义，映射到 numina 的 Vue 3 + Vant 4 移动端栈（375×812 基准）。它是 U7 的实现参考，不是独立 API 契约。

## 1. 产品语义 (read-only)

- **Agent 拥有 todo 状态。** 只有 agent 通过 `write_todos` 工具调用改写 `channel_values["todos"]`；用户**不可勾选/编辑**。
- 状态三态：`pending`（未开始，空指示）、`in_progress`（进行中，主色填充）、`completed`（已完成，勾选）。
- todo item 形状：`{ content: string, status: "pending" | "in_progress" | "completed" }` —— **无 `id`**，前端按 `index + content` 键（对齐 DeerFlow `todo-list.tsx:76` `key={i + (todo.content ?? "")}`）。
- 持久化：todos 落在 LangGraph checkpoint 的 `todos` channel（`merge_todos` reducer：`new is None → 保留 existing`，否则 `new` 整体替换 —— DeerFlow `thread_state.py:85-94`）。numina 不新增 DB 列。

## 2. 渲染门控

- `TodoListBar` 仅当 `todos.length > 0` 时渲染（`hasTodos` 计算属性）。
- 渲染位置：`AIChatBox.vue` 中 `InputBox` 上方，与（未来 U5 的）`GoalStatusBar` 共置。当前分支 U5 未落地，故 `TodoListBar` 独占该位。
- 线程切换 / 历史加载时 `todos` 清空或重水合（由 `useThreadChat` 负责）。

## 3. 组件选型 (Vant 4)

| 需求 | 选型 | 理由 |
|------|------|------|
| 可折叠容器 | 自定义 sticky bar + `van-icon` chevron | `van-collapse` 的 item padding/动画对移动端密度过高，且默认整行点击区不可控；自定义更易满足 ≥44px 触控 + 压缩高度 |
| completed 指示 | `van-checkbox` (`disabled` + `v-model="true"`) | 只读勾选形态，语义最贴近 DeerFlow `QueueItemIndicator completed` |
| in_progress 指示 | `van-tag` (`color` 主色 / `plain`) + 行主色文字 | 无三态 checkbox，用 tag 颜色区分 |
| pending 指示 | 空圆点（`van-icon` `circle`）| 空状态，无填充 |
| header 图标 | `van-icon name="orders-o"`（列表图标，对齐 DeerFlow `ListTodoIcon`）| Vant 内置，无额外依赖 |

**不使用 `van-collapse` 的决定性理由：** `van-collapse-item` 的 title slot 点击区受其内置 padding 限制，且展开动画基于 `max-height` 难以精确压缩到移动端密度。自定义 header + `v-show`/高度过渡更可控。

## 4. 布局密度 (375px 基准)

- 容器：`width: 100%`，`border-top-left-radius: 12px` + `border-top-right-radius: 12px`，`border` 仅顶部（贴在 InputBox 上方，底部无缝）。
- header：`min-height: 44px`（触控达标，见 §6），`padding: 0 12px`，`display: flex; align-items: center; justify-content: space-between`。
  - 左：`van-icon orders-o` (16px) + `t('aiChat.todosLabel')` 文案，`gap: 6px`，`font-size: 13px`，`color: var(--van-text-color-2)`（次级）。
  - 右：`van-icon arrow-up`（16px），`transition: transform 0.3s`，展开时 `transform: rotate(180deg)`。
- 展开区：`max-height: 180px` + `overflow-y: auto`（约 4–5 项可见，超出滚动；对齐 DeerFlow `h-28`≈112px 但移动端略放大以容纳中文长内容）。
- 每项：单行 + `text-overflow: ellipsis; white-space: nowrap; overflow: hidden`，`min-height: 36px`，`padding: 6px 12px`。
- 默认折叠：`collapsed = ref(true)`（对齐 DeerFlow `internalCollapsed=true`）。

## 5. 交互契约

- **header 点击** → toggle `collapsed`。无后端调用，纯本地 UI 状态。
- **item 点击** → 无操作（read-only）。`van-checkbox` 设 `disabled`，阻止勾选。
- 状态指示随 `todos` prop 响应式更新（agent `write_todos` → `values` SSE 事件 → `useThreadChat.todos` ref → `useThreadTodos` → `TodoListBar` prop）。
- 用户点击 checkbox **不触发任何后端调用**（无持久化，无 `write_todos` 反向调用）。

## 6. 触控目标 (移动端达标)

- header `min-height: 44px`（Apple HIG 最小触控目标；DeerFlow 桌面 `min-h-8`≈32px 偏小，移动端上调）。
- chevron 图标容器 `min-width: 44px; min-height: 44px; display: flex; align-items: center; justify-content: center`，确保右侧点击区达标。
- item 行 `min-height: 36px`（非主操作，略低于 44px 可接受；整行无点击行为）。

## 7. 数据流

```
agent write_todos tool_call
  → LangGraph todos channel (merge_todos reducer)
  → DeerFlowClient.stream() "values" event (data.todos)
  → adapter.typed_stream_dispatch yields ("values", {todos, ...})
  → worker._stream_once → bridge.publish(run_id, "values", data)
  → SSE "values" frame
  → useThreadChat: chunk.event === 'values' → todos.value = data.todos
  → useThreadTodos(chat): { todos, hasTodos } (reactive derivation)
  → AIChatBox: v-if="hasTodos" → <TodoListBar :todos="todos" />
```

**关键点：** `useThreadChat` 的 `ValuesData` 接口需新增 `todos?: Array<{ content: string; status: string }>` 字段；`values` 事件分支捕获 `data.todos` 覆写 `todos.value`。`loadHistory` 从 `state.values.todos` 重水合。

## 8. 后端接入 (TodoMiddleware)

- 文件：`server/apps/agent/services/deerflow_adapter/todo_middleware.py`
- 基类：`langchain.agents.middleware.TodoListMiddleware`（已验证 numina venv 可 import，提供 `write_todos` 工具 + 默认 system_prompt/tool_description）。
- 子类：`TodoMiddleware(TodoListMiddleware)`，移植自 DeerFlow `todo_middleware.py`：
  - **sync `before_model`**（R2 关键）：context-loss reminder —— 当 `todos` 非空但 `write_todos` 工具调用已离开上下文窗口（被摘要截断），注入隐藏 `HumanMessage(name="todo_reminder", additional_kwargs={"hide_from_ui": True})`。
  - **sync `after_model`**（R2 关键）：premature-exit prevention —— agent 产出无 tool_call 的最终回复但 todos 未全完成时，队列化 completion reminder + `jump_to: "model"` 强制继续，带 `_MAX_COMPLETION_REMINDERS=2` 防死循环。
  - `wrap_model_call`：把排队的 reminder 注入下次 model 请求（不持久化为可见消息）。
  - async 版本（`abefore_model`/`aafter_model`/`awrap_model_call`）委托 sync 版本，兼容 async 路径。
- **plan_mode gate**：仅 `plan_mode=True` 时由 worker 注入（对齐 DeerFlow `factory.py:227-231`）。
- **单例（R3 关键）：** 模块级单例 `_TODO_MIDDLEWARE_SINGLETON`，worker 每次传同一实例 → `id()` 稳定 → `family_adapter_cache.py:726` 的 LRU key 不失效 → 不重建 agent。

## 9. worker 注入点

`server/apps/agent/services/runtime/worker.py` `_run_numina_agent` 中 `create_family_adapter(...)`（约 line 2085）：
- `call_plan_mode=True` 时追加 `middlewares=[get_todo_middleware()]`（单例）。
- `call_plan_mode=False` 时不传 `middlewares`（保持 None，不影响缓存 key 的 `()` 分支）。

**注意：** `plan_mode` 已在 LRU cache key 中（`family_adapter_cache.py:727`），故 plan_mode=True 与 False 走不同 client 实例；middlewares 单例保证 plan_mode=True 分支内 `id()` 稳定。

## 10. i18n

- `aiChat.todosLabel`：header 文案（zh-CN `待办清单` / en-US `To-dos`，对齐 DeerFlow 硬编码 "To-dos"）。
- 状态文案（用于 `van-tag` / aria，非必须显示）：`aiChat.todoStatusPending` / `todoStatusInProgress` / `todoStatusCompleted`。
- 复用既有 `aiChat` 命名空间（非 `inputBox`，与 U1/U6 的 slash 文案同级）。

## 11. 测试场景

### 前端 (vitest)
- Happy: `todos` 非空 → `TodoListBar` 渲染于 InputBox 上方；每项 content + 状态指示正确。
- Edge: `todos` 空/null → 不渲染；默认折叠，点击 header 展开/收起；375px 宽无横向溢出。
- Integration: agent 标记 in_progress → UI 反映；completed → 勾选态；read-only（点击 checkbox 无 emit/无 API 调用）。
- Touch: header `min-height: 44px`（getComputedStyle 断言）。

### 后端 (pytest)
- `TodoMiddleware` sync `before_model`/`after_model` 在 sync stream 路径触发（R2 验证）。
- 单例 `id()` 稳定（R3 —— 多次 `get_todo_middleware()` 返回同一对象）。
- `before_model` context-loss：todos 非空且无 `write_todos` 在 messages → 返回 reminder；todos 空或 write_todos 可见 → 返回 None。
- `after_model` premature-exit：未完成 todos + 无 tool_call 最终回复 → `jump_to: "model"`；全完成 → None。
