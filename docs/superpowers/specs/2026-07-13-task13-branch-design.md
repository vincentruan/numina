---
title: Task 13 — Branch (分支对话) 详细设计
created: 2026-07-13
status: draft
scope: frontend-main, server-agent
priority: P1
dependencies:
  - LangGraph checkpointer fork 语义验证（spike）
  - 现有 thread/checkpoint 基础设施（threads.py, resume.py）
---

# Task 13 — Branch (分支对话) 详细设计

## 背景

Branch 功能允许用户从对话历史中的任意轮次创建分支，探索不同的假设路径。这是深度研究场景的核心交互——用户可以对比"如果投资股票 vs 基金"的不同分析路径，而无需重复前面的对话。

**DeerFlow 参考：**
- 后端：`backend/app/gateway/routers/threads.py:579-665` — `POST /{thread_id}/branches`
- 前端：`message-list.tsx:564-592` — `GitBranchPlusIcon` + `onBranchTurn`
- Hook：`hooks.ts:2001-2028` — `useBranchThread()` mutation
- API：`threads/api.ts:71-97` — `branchThreadFromTurn()`

**当前状态：** 无 Branch 功能。`threads.py` 的 `POST /{thread_id}/state` 支持 `checkpoint_id` 但只修改同一 thread，不提供 fork 到新 thread 的能力。

---

## 前置 Spike（0.5 天）

**目标：** 验证 LangGraph SDK 是否支持 checkpoint-level fork 到新 thread_id。

**验证项：**

DeerFlow 已在生产环境验证了方案 A（直接复制 checkpoint 对象），Numina 的 spike 主要是确认 Numina 的 checkpointer 配置（AsyncSqliteSaver）支持相同的操作。

1. **Checkpointer API 能力**
   - `checkpointer.aget_tuple(config)` 返回 `CheckpointTuple`，包含 `checkpoint`, `metadata`, `parent_config`, `config`, `pending_writes`
   - `checkpointer.aput(config, checkpoint, metadata, writes)` 写入新 checkpoint
   - `checkpointer.alist(config, limit=N)` 遍历 checkpoint 历史（用于 `_find_branch_checkpoint`）

2. **Fork 语义（方案 A — DeerFlow 已验证）**
   ```python
   # DeerFlow 参考：threads.py:626-641
   source_config = {"configurable": {"thread_id": source_thread_id, "checkpoint_id": checkpoint_id}}
   source_tuple = await checkpointer.aget_tuple(source_config)
   
   target_config = {"configurable": {"thread_id": target_thread_id, "checkpoint_ns": ""}}
   new_checkpoint = copy.deepcopy(getattr(source_tuple, "checkpoint", {}) or {})
   new_metadata = copy.deepcopy(getattr(source_tuple, "metadata", {}) or {})
   new_checkpoint["id"] = str(uuid6())  # 生成新的 checkpoint ID
   new_metadata.update({
       "source": "branch",
       "updated_at": now,
       "created_at": now,
       "family_id": family_id,  # preserve tenant isolation
       # branch metadata
       "numina_branch": True,
       "branch_parent_thread_id": thread_id,
       "branch_parent_checkpoint_id": parent_checkpoint_id,
       "branch_parent_message_id": message_id,
       "branch_created_at": now,
   })
   
   # DeerFlow 复制 channel_versions 以保持版本一致性
   new_versions = dict(new_checkpoint.get("channel_versions", {}) or {})
   await checkpointer.aput(target_config, new_checkpoint, new_metadata, new_versions)
   ```

3. **Numina 特有风险**
   - Numina 使用 `AsyncSqliteSaver`（DeerFlow 也是），但需确认 `alist()` 在 Numina 的 checkpointer 实例上正常工作
   - Numina 的 checkpoint metadata 包含 `family_id`（DeerFlow 没有），需确认 deep copy 后 `family_id` 被正确覆盖

4. **集成测试验证**
   - 创建 source thread + 多轮对话
   - Branch 从中间轮次
   - 验证 target thread 的 `get_thread_state` 返回与 source 在 branch point 相同的 messages
   - 验证 target thread 可以独立继续对话（不影响 source）

**验收标准：**
- 产出 spike 报告：可行 / 需要 workaround / 不可行需降级
- 如果不可行，Task 13 降级为 P2 并重新评估技术方案

---

## 后端设计（假设 Spike 可行）

### 1. Branch Endpoint

**文件：** `server/apps/agent/routers/threads.py`（新增 endpoint）

**DeerFlow 参考接口：**
```
POST /api/threads/{thread_id}/branches
Request Body:
{
  "message_id": "ai-message-uuid",      // 必填：分支起点的 AI 消息 ID
  "message_ids": ["ai-message-uuid"],   // 必填：同一 turn 的所有 AI 消息 ID
  "title": "可选的分支标题"              // 可选
}

Response:
{
  "thread_id": "new-thread-uuid",
  "parent_thread_id": "original-thread-uuid",
  "parent_checkpoint_id": "checkpoint-uuid",
  "branched_from_message_id": "ai-message-uuid",
  "workspace_clone_mode": "none" | "full"
}
```

**Numina 适配接口（保持 DeerFlow 兼容性，增加 family_id 隔离）：**
```
POST /api/threads/{thread_id}/branches
Request Body:
{
  "message_id": "ai-message-uuid",      // 必填：分支起点的 AI 消息 ID
  "message_ids": ["ai-message-uuid"],   // 必填：同一 turn 的所有 AI 消息 ID
  "title": "可选的分支标题"              // 可选
}

Response:
{
  "thread_id": "new-thread-uuid",
  "parent_thread_id": "original-thread-uuid",
  "parent_checkpoint_id": "checkpoint-uuid",
  "branched_from_message_id": "ai-message-uuid"
}
```

**关键设计决策（对齐 DeerFlow）：**

1. **前端发送 `message_id`，后端查找 checkpoint**
   - DeerFlow 实现 `_find_branch_checkpoint()` 扫描 checkpoint 历史，找到包含目标 message_id 的 checkpoint
   - 这比前端发送 `checkpoint_id` 更可靠（前端不需要知道 checkpoint 概念）
   - 避免了 timestamp 匹配的不精确问题

2. **使用 `message_id` 而非 `checkpoint_id` 作为分支点标识**
   - 前端已经有 message 对象（包含 id）
   - 后端负责 message_id → checkpoint_id 的映射

**实现逻辑（对齐 DeerFlow）：**

```python
# 新增常量（对齐 DeerFlow threads.py:62-63）
_BRANCH_METADATA_KEY = "numina_branch"

# 新增 Request/Response Models（对齐 DeerFlow threads.py:375-388）
class ThreadBranchRequest(BaseModel):
    message_id: str = Field(description="AI message ID to branch from")
    message_ids: list[str] = Field(
        default_factory=list,
        description="All AI message IDs in the same turn",
    )
    title: str | None = Field(default=None, description="Optional branch title")

class ThreadBranchResponse(BaseModel):
    thread_id: str
    parent_thread_id: str
    parent_checkpoint_id: str
    branched_from_message_id: str

# 新增 helper function（对齐 DeerFlow threads.py:135-184）
async def _find_branch_checkpoint(
    checkpointer, thread_id: str, target_message_ids: set[str]
):
    """Find the checkpoint containing the target message IDs.
    
    DeerFlow 参考：threads.py:135-145
    扫描 checkpoint 历史，找到包含目标 message_id 的最新 checkpoint。
    """
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    async for checkpoint_tuple in checkpointer.alist(config, limit=100):
        checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
        messages = checkpoint.get("channel_values", {}).get("messages", [])
        
        # Check if any message in this checkpoint matches target IDs
        for msg in messages:
            msg_id = getattr(msg, "id", None) or (msg.get("id") if isinstance(msg, dict) else None)
            if msg_id and msg_id in target_message_ids:
                return checkpoint_tuple
    
    return None

@router.post("/{thread_id}/branches", response_model=ThreadBranchResponse)
async def branch_thread(
    thread_id: str,
    body: ThreadBranchRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadBranchResponse:
    """Create a new branch from a completed assistant turn.
    
    DeerFlow 参考：threads.py:579-665
    对齐 DeerFlow 的 branch 实现，增加 Numina 的 family_id 租户隔离。
    
    # [Integrated with Numina Multi-Tenant] — family_id validation + propagation
    """
    import copy
    from langgraph.checkpoint.base import uuid6
    
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)
    
    # 1. Validate source thread exists and belongs to this family
    source_record = await repo.get_session(thread_id)
    if source_record is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    
    source_family_id = source_record.get("family_id")
    if not source_family_id or str(source_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    
    # 2. Find checkpoint containing the target message
    target_message_ids = {body.message_id, *body.message_ids}
    checkpoint_tuple = await _find_branch_checkpoint(checkpointer, thread_id, target_message_ids)
    
    if checkpoint_tuple is None:
        raise HTTPException(
            status_code=409,
            detail="This turn can no longer be branched from.",
        )
    
    parent_checkpoint_id = (
        getattr(checkpoint_tuple, "config", {})
        .get("configurable", {})
        .get("checkpoint_id")
    )
    if not parent_checkpoint_id:
        raise HTTPException(
            status_code=409,
            detail="This turn can no longer be branched from.",
        )
    
    # 3. Generate new thread ID and copy checkpoint
    new_thread_id = str(uuid.uuid4())
    now = now_iso()
    
    # DeerFlow 参考：threads.py:611-617
    branch_metadata = {
        _BRANCH_METADATA_KEY: True,
        "branch_parent_thread_id": thread_id,
        "branch_parent_checkpoint_id": parent_checkpoint_id,
        "branch_parent_message_id": body.message_id,
        "branch_created_at": now,
    }
    
    # DeerFlow 参考：threads.py:626-636
    checkpoint = copy.deepcopy(getattr(checkpoint_tuple, "checkpoint", {}) or {})
    metadata = copy.deepcopy(getattr(checkpoint_tuple, "metadata", {}) or {})
    checkpoint["id"] = str(uuid6())
    metadata.update({
        "source": "branch",
        "updated_at": now,
        "created_at": now,
        "family_id": x_family_id,  # preserve tenant isolation
        **branch_metadata,
    })
    
    # Derive title from source thread（DeerFlow 参考：threads.py:619-622）
    source_title = source_record.get("title") or ""
    if body.title:
        display_title = body.title
    elif source_title:
        display_title = f"分支: {source_title}"
    else:
        display_title = None
    
    if display_title:
        metadata["title"] = display_title
        if source_title:
            metadata["original_title"] = source_title
    
    # 4. Write checkpoint to new thread（DeerFlow 参考：threads.py:638-644）
    write_config = {"configurable": {"thread_id": new_thread_id, "checkpoint_ns": ""}}
    new_versions = dict(checkpoint.get("channel_versions", {}) or {})
    try:
        await checkpointer.aput(write_config, checkpoint, metadata, new_versions)
    except Exception:
        logger.exception("Failed to write branch checkpoint for thread %s", new_thread_id)
        raise HTTPException(status_code=500, detail="Failed to create branch") from None
    
    # 5. Create session row in backend DB（DeerFlow 参考：threads.py:646-656）
    try:
        await repo.upsert(
            session_id=new_thread_id,
            family_id=x_family_id,
            user_id=x_user_id,
            agent_id=source_record.get("agent_id"),
            last_model=source_record.get("last_model"),
            source="branch",
        )
        if display_title:
            await repo.update_summary(
                session_id=new_thread_id,
                family_id=x_family_id,
                summary=None,
                title=display_title,
            )
    except Exception:
        logger.exception("Failed to write branch session for thread %s", new_thread_id)
        raise HTTPException(status_code=500, detail="Failed to create branch") from None
    
    # 6. Log structured event for success metrics
    logger.info(
        "event=thread_branched, source_thread_id=%s, new_thread_id=%s, message_id=%s, family_id=%s",
        thread_id,
        new_thread_id,
        body.message_id,
        x_family_id,
    )
    
    # 7. Return response（对齐 DeerFlow ThreadBranchResponse）
    return ThreadBranchResponse(
        thread_id=new_thread_id,
        parent_thread_id=thread_id,
        parent_checkpoint_id=parent_checkpoint_id,
        branched_from_message_id=body.message_id,
    )
```

**错误处理（对齐 DeerFlow）：**
- `404` — source thread 不存在
- `404` — family_id 不匹配（租户隔离）
- `409` — 找不到包含目标 message 的 checkpoint（"This turn can no longer be branched from."）
- `500` — checkpointer 写入失败
- `500` — session 写入失败

**并发控制：**
- 同一 source thread 的并发 branch 请求：允许（每次创建独立的 new thread）
- 快速连续点击：前端禁用按钮（`branchingMessageId` 状态追踪）

---

### 2. 前端 API

**文件：** `frontend/apps/main/src/api/ai-chat.ts`（新增函数）

**DeerFlow 参考：** `threads/api.ts:71-97` — `branchThreadFromTurn()`

```typescript
// 对齐 DeerFlow ThreadBranchResponse
export interface ThreadBranchResponse {
  thread_id: string
  parent_thread_id: string
  parent_checkpoint_id: string
  branched_from_message_id: string
}

// 对齐 DeerFlow BranchThreadFromTurnInput
export interface BranchThreadFromTurnInput {
  messageId: string
  messageIds?: string[]
  title?: string
}

export async function branchThreadFromTurn(
  threadId: string,
  input: BranchThreadFromTurnInput,
): Promise<ThreadBranchResponse> {
  const res = await fetch(
    `${getAgentApiBase()}/api/threads/${encodeURIComponent(threadId)}/branches`,
    {
      method: 'POST',
      headers: {
        ...getAgentHeaders(),
      },
      credentials: 'include',
      body: JSON.stringify({
        message_id: input.messageId,
        message_ids: input.messageIds ?? [input.messageId],
        ...(input.title ? { title: input.title } : {}),
      }),
    },
  )
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Failed to branch' }))
    throw new Error(error.detail || 'Failed to branch conversation')
  }
  return (await res.json()) as ThreadBranchResponse
}
```

**关键变化（对比原设计）：**
- 前端发送 `message_id` + `message_ids`，而非 `checkpoint_id`
- 后端负责 message_id → checkpoint_id 的映射
- 返回值包含 `parent_thread_id`、`parent_checkpoint_id`、`branched_from_message_id`

---

### 3. 前端 UI 集成

**DeerFlow 参考：**
- `message-list.tsx:564-592` — Branch 按钮在 `renderAssistantActions` 中
- `message-list.tsx:282-284` — `branchingMessageId` 状态追踪
- `[thread_id]/page.tsx:212-237` — `handleBranchTurn` 回调

**文件：** `frontend/apps/main/src/components/ai-chat/MessageGroup.vue`

**变更：** 在 AI 消息的悬浮工具栏添加 Branch 按钮（与 copy、retry 同行）

```vue
<!-- 对齐 DeerFlow message-list.tsx:564-592 -->
<div class="message-actions">
  <!-- Existing actions: copy, retry, etc. -->
  <button
    v-if="!isStreaming && actionTarget?.id && onBranchTurn"
    class="branch-button"
    :disabled="!canBranch || branchingMessageId === actionTarget.id"
    @click="handleBranch(actionTarget.id, assistantMessageIds)"
    :aria-label="t('ai.chat.branch.button')"
  >
    <van-icon
      name="exchange"
      :class="{ 'animate-pulse': branchingMessageId === actionTarget.id }"
    />
  </button>
</div>
```

**逻辑（对齐 DeerFlow page.tsx:212-237）：**

```typescript
// 对齐 DeerFlow branchingMessageId 状态（message-list.tsx:282-284）
const branchingMessageId = ref<string | null>(null)

// canBranch 由父组件控制（对齐 DeerFlow canBranch prop）
const canBranch = computed(() => {
  return !props.isStreaming && props.threadId != null
})

// 对齐 DeerFlow handleBranchTurn（page.tsx:212-237）
async function handleBranch(messageId: string, messageIds: string[]) {
  if (!props.threadId || branchingMessageId.value) return
  
  branchingMessageId.value = messageId
  try {
    const response = await branchThreadFromTurn(props.threadId, {
      messageId,
      messageIds,
    })
    
    showSuccessToast(t('ai.chat.branch.success'))
    
    // 对齐 DeerFlow：router.push 到新 thread
    router.push({
      path: '/ai/chat',
      query: { thread_id: response.thread_id },
    })
  } catch (error) {
    console.error('Branch failed:', error)
    showFailToast(
      error instanceof Error ? error.message : t('ai.chat.branch.error')
    )
  } finally {
    branchingMessageId.value = null
  }
}
```

**关键变化（对比原设计）：**
- 使用 `branchingMessageId` 状态追踪正在 branch 的消息（而非 `isBranching`）
- 前端发送 `message_id` + `message_ids`，不再需要 `getThreadHistory()` 懒加载
- 按钮位置与 copy、retry 同行（对齐 DeerFlow `renderAssistantActions`）
- 按钮图标使用 `exchange`（Vant 没有 GitBranchPlus，用 exchange 代替）

**message_ids 的获取：**

```typescript
// 在 MessageGroup.vue 中，从 group.messages 提取同一 turn 的所有 AI message IDs
const assistantMessageIds = computed(() => {
  return props.group.messages
    .filter(msg => msg.role === 'assistant' && msg.id)
    .map(msg => msg.id!)
})
```

---

### 4. UI 位置

**DeerFlow 参考：** `message-list.tsx:562-593`

**Branch 按钮位置：**
- 在 AI 消息的悬浮工具栏（hover 时显示，`group-hover/assistant-turn:opacity-100`）
- 位置：与 copy、retry 按钮同行（`renderAssistantActions`）
- 图标：`<van-icon name="exchange" />`（Vant 没有 GitBranchPlus，用 exchange 代替）
- Tooltip：`t('ai.chat.branch.button')` = "创建分支"
- 动画：branching 时 `animate-pulse`（对齐 DeerFlow `branchingMessageId === actionTarget.id && "animate-pulse"`）

**可见性（对齐 DeerFlow message-list.tsx:564-571）：**
- 仅在 AI 消息上显示（`group.type === 'assistant'`）
- 仅在非 streaming 时显示（`!isStreaming`）
- 仅在 `onBranchTurn` 回调存在时显示
- 仅在 `canBranch` 为 true 时启用（由父组件控制，例如不在新对话中显示）
- 移动端：长按消息显示工具栏

---

### 5. i18n Keys

**文件：** `frontend/apps/main/src/i18n/locales/zh-CN.ts`

```typescript
'ai.chat.branch.button': '创建分支',
'ai.chat.branch.branching': '创建中...',
'ai.chat.branch.success': '分支创建成功',
'ai.chat.branch.error': '无法创建分支',
```

**文件：** `frontend/apps/main/src/i18n/locales/en-US.ts`

```typescript
'ai.chat.branch.button': 'Create Branch',
'ai.chat.branch.branching': 'Branching...',
'ai.chat.branch.success': 'Branch created successfully',
'ai.chat.branch.error': 'Failed to create branch',
```

---

### 5. 结构化日志

**后端日志（用于成功指标，对齐 spec 横切关注点）：**

```python
logger.info(
    "event=thread_branched, source_thread_id=%s, new_thread_id=%s, message_id=%s, family_id=%s",
    thread_id,
    new_thread_id,
    body.message_id,
    x_family_id,
)
```

---

## 错误处理

**对齐 DeerFlow 的错误模式：**

| 场景 | 后端处理 | 前端处理 |
|------|---------|---------|
| source thread 不存在 | `404 detail="Thread {id} not found"` | toast "无法创建分支" |
| family_id 不匹配 | `404 detail="Thread {id} not found"` | toast "无法创建分支" |
| 找不到包含目标 message 的 checkpoint | `409 detail="This turn can no longer be branched from."` | toast 显示后端错误信息 |
| checkpointer 写入失败 | `500 detail="Failed to create branch"` | toast "无法创建分支" |
| session 写入失败 | `500 detail="Failed to create branch"` | toast "无法创建分支" |
| 网络超时 | N/A | toast 显示错误信息 |
| 并发操作（快速点击） | 允许（每次创建独立 thread） | `branchingMessageId` 追踪 + 禁用按钮 |

---

## 无障碍（对齐 DeerFlow message-list.tsx:567）

- Branch 按钮支持 Tab 键导航
- `aria-label="创建分支"`（对齐 DeerFlow `aria-label={t.common.branch}`）
- 点击后按钮显示 `animate-pulse` 动画（视觉反馈）
- 成功后 `showSuccessToast` 通知

---

## Dark Mode

- Branch 按钮使用 CSS 变量：`color: var(--text-secondary)`
- Hover 状态：`background: var(--button-hover-bg)`
- Disabled 状态：`opacity: 0.5`
- 对齐 DeerFlow 的 `variant="ghost"` + `size="icon-sm"` 样式

---

## 测试计划

**对齐 DeerFlow 测试覆盖：**

### 后端测试

1. **单元测试：** `test_branch_endpoint.py`（对齐 DeerFlow `test_threads_router.py:574-768`）
   - `test_branch_thread_from_assistant_turn_creates_new_thread` — 正常 branch 流程
   - `test_branch_thread_message_not_found` — 找不到包含目标 message 的 checkpoint
   - `test_branch_thread_family_mismatch` — family_id 不匹配
   - `test_branch_thread_from_older_turn_truncates_messages` — 从历史轮次 branch 时消息被截断
   - `test_branch_thread_metadata_propagation` — branch metadata 正确传播（`is_branch`, `branch_parent_thread_id` 等）

2. **集成测试：** `test_branch_flow.py`
   - 创建 source thread + 多轮对话
   - Branch 从中间轮次
   - 验证 new thread 的 messages 只包含到 branch point 的消息
   - 验证 new thread 可以独立继续对话（不影响 source）

### 前端测试

1. **组件测试：** `MessageGroup.branch.spec.ts`
   - `test_branch_button_visible_on_assistant_turn` — Branch 按钮在 AI 消息上显示
   - `test_branch_button_hidden_during_streaming` — streaming 时隐藏按钮
   - `test_branch_button_disabled_when_branching` — 操作中禁用按钮（`branchingMessageId` 匹配）
   - `test_branch_success_navigation` — 成功后导航到新 thread
   - `test_branch_error_toast` — 失败时显示 toast

2. **E2E 测试（对齐 DeerFlow `branch-thread.spec.ts`）：**
   - 创建对话 → hover assistant turn → 点击 Branch → 验证新 thread URL
   - 验证新 thread 显示 branch point 之前的消息

---

## 成功指标

| 指标 | 目标 | 衡量方式 |
|------|------|---------|
| Branch 使用率 | ≥3% 的深度研究对话创建分支 | 后端日志统计 `event=thread_branched` |
| Branch 成功率 | ≥95% | 后端日志统计 branch 成功/失败比例 |
| Branch 后继续对话率 | ≥50% | 新 thread 是否有后续消息 |

---

## 风险与约束

1. **LangGraph checkpointer fork 语义未验证** — 需要 spike 验证方案 A 的可行性（DeerFlow 已验证，但 Numina 的 checkpointer 配置可能不同）
2. **`_find_branch_checkpoint` 性能** — 扫描 checkpoint 历史（`alist(limit=100)`）在长对话中可能较慢。DeerFlow 限制 100 个 checkpoint，Numina 应对齐
3. **message_id 稳定性** — 如果 LangChain message 没有 `id` 字段（旧版本），`_find_branch_checkpoint` 无法匹配。需要确保所有 message 都有稳定 ID
4. **并发 branch** — 允许并发，但可能导致大量 orphan threads（需要 GC 策略）

---

## 实现顺序

1. **Spike（0.5 天）** — 验证 LangGraph checkpointer fork 语义（方案 A）
2. **后端 endpoint（1 天）** — `POST /api/threads/{thread_id}/branches` + `_find_branch_checkpoint`
3. **前端 API（0.5 天）** — `branchThreadFromTurn()`
4. **前端 UI（1 天）** — Branch 按钮 + `branchingMessageId` 状态 + 交互逻辑
5. **测试（0.5 天）** — 单元测试 + 组件测试
6. **i18n（0.5 天）** — 添加所有 key

**总计：4 天**

---

## 与现有 Spec 的关系

- 本设计是 [2026-07-12 DeerFlow UX Parity Phase 2](./2026-07-12-deerflow-ux-parity-phase2-design.md) 的 Task 13 详细设计
- 遵循 Phase 2 的设计原则：复刻 DeerFlow 交互模式，增量集成到现有组件体系
- 不修改已稳定的组件接口（threads.py 的其他 endpoint、MessageGroup.vue 的其他功能）
- 新增 branch endpoint 独立于现有 thread CRUD 操作

---

## 附录：DeerFlow vs Numina 对照表

| 方面 | DeerFlow | Numina（本设计） |
|------|----------|----------------|
| Endpoint path | `POST /{thread_id}/branches` | `POST /{thread_id}/branches` ✅ 对齐 |
| Branch point | `message_id` + `message_ids` | `message_id` + `message_ids` ✅ 对齐 |
| Checkpoint 发现 | `_find_branch_checkpoint()` 扫描 `alist(limit=100)` | 同 ✅ 对齐 |
| Response | `ThreadBranchResponse` | `ThreadBranchResponse` ✅ 对齐 |
| Metadata keys | `deerflow_branch`, `branch_parent_thread_id`, ... | `numina_branch`, `branch_parent_thread_id`, ... ✅ 对齐 |
| Workspace clone | `_copy_branch_user_data()` (latest turn only) | **不做** — Numina 无 workspace 文件系统 |
| Sidecar rejection | 409 if sidecar thread | **不做** — Numina 无 sidecar 概念 |
| Button icon | `GitBranchPlusIcon` (Lucide) | `<van-icon name="exchange" />` (Vant) |
| Button location | `renderAssistantActions` | `renderAssistantActions` ✅ 对齐 |
| Loading state | `branchingMessageId` | `branchingMessageId` ✅ 对齐 |
| Navigation | `router.push(/workspace/chats/${id})` | `router.push({path: '/ai/chat', query: {thread_id: id}})` |
| Hook | `useBranchThread()` (React Query mutation) | 直接 `async function` (Vue composable) |
