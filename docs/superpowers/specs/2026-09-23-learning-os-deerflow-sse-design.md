---
date: 2026-09-23
module: learning, agent, backend
problem_type: architecture
tags: [deerflow, sse, stream-bridge, redis, learning-tutor, reconnection]
applies_when: Implementing DeerFlow SSE integration for learning-tutor skill, switching agent bridge from memory to Redis, enabling cross-process event sharing
---

# Learning OS — DeerFlow SSE 完整集成设计

## Context

Learning OS 实现计划 (`docs/superpowers/plans/2026-09-23-learning-os.md`) 已完成了数据层、后端 CRUD 服务、前端页面框架和 seed 数据。但 AI 辅导核心——DeerFlow SSE 集成——仍是 placeholder：

- `learning-tutor` SKILL.md 声明了 3 个 `allowed-tools`，全部是 `NotImplementedError` 桩（code review OQ-1）
- `LearningSessionPage.vue` 显示静态文本，无 SSE 连接、无聊天 UI（code review OQ-5）
- Child app 零 SSE 基础设施（无 `sseReader.ts`、无 LangGraph SDK、无 chat composable）
- Agent 侧无 `learning-tutor` runner，无 gateway 端点，无 tool 注册

本文档描述 DeerFlow SSE 完整集成的架构设计，解决上述所有问题，并建立可复用的 "agent 写 bridge → backend 读 bridge" 模式。

## 架构概述

### 核心原则

**Agent 是 bridge 的生产者（writer），Backend 是 bridge 的消费者（reader）。** 对话历史由 DeerFlow checkpointer 持久化，事件流由 Redis StreamBridge 跨进程分发。不新增缓存层——复用 DeerFlow 已有组件。

**Design Rationale — 为什么不用现有 HTTP SSE pump 模式：**

现有架构（`bridge_consumer.py`）采用 "agent 内存 bridge → HTTP SSE → backend `_pump_agent_sse_to_bridge()` → backend bridge" 模式。该模式下 agent 设置了 `on_disconnect: "continue"`（agent 不会因 backend 断开而停止），但 pump 任务死亡后，agent 继续产出的事件**无法到达 backend bridge**——即前端恢复后丢失 pump 断开期间的所有对话事件。

Learning OS 的核心场景是儿童与 AI 辅导的持续对话，断连恢复是关键需求（网络不稳定、切换 app 等）。Redis StreamBridge 使 agent 直接写入持久化的 Redis Stream，backend 可从任意位置续读，彻底解耦 agent 产出与 backend 消费的生命周期。

**Trade-off**: 现有架构声明 "agent has ZERO infrastructure dependencies"。本次设计引入 Redis 依赖到 agent 进程，换取事件持久化和跨进程重连能力。这是有意为之的架构取舍。

### DeerFlow 参考来源

本次设计基于 DeerFlow 上游 harness（pinned at commit `6556d09d`，见 `server/apps/agent/deerflow_config/HARNESS_VERSION`）的原生组件：

| DeerFlow 组件 | 路径 | 用途 |
|---------------|------|------|
| `RedisStreamBridge` | `references/deerflow/backend/packages/harness/deerflow/runtime/stream_bridge/redis.py` | 跨进程事件分发，`supports_cross_process = True`，使用 Redis Streams (`XADD`/`XREAD`) |
| `StreamBridgeConfig` | `references/deerflow/backend/packages/harness/deerflow/config/stream_bridge_config.py` | bridge 配置（type、redis_url、stream_ttl_seconds 等） |
| `STREAMING.md` | `references/deerflow/backend/docs/STREAMING.md` | 双路流式架构（Gateway async/HTTP SSE vs Client sync/in-process） |
| `RUN_EVENT_STREAM.md` | `references/deerflow/backend/docs/RUN_EVENT_STREAM.md` | 持久化事件日志（`RunJournal` / `RunEventStore`），append-only |
| DeerFlow Helm Redis | `references/deerflow/deploy/helm/deer-flow/templates/redis-statefulset.yaml` | Docker 部署自带 Redis StatefulSet |

**关键行为契约（来自 DeerFlow 上游）：**

- **Gap recovery**: 当 subscriber cursor 落后于 `MAXLEN` 保留窗口时，bridge 发送 `gap` SSE 帧（`code: "stream_replay_gap"`），client 须丢弃瞬态状态、重新加载 checkpoint + 历史，然后以 `latest_available_event_id` 续读
- **Last-Event-ID 重连**: Redis bridge 通过 `XRANGE`/`XREAD` 支持从任意 cursor 位置续读
- **Stream TTL**: 默认 86400s（24h），每次 `publish()` 刷新
- **MAXLEN 裁剪**: 默认保留 256 条数据事件/run，超出从前端裁剪
- **Docker 部署默认 Redis**: `config.example.yaml` 文档说明 Docker Compose 自动设置 `DEER_FLOW_STREAM_BRIDGE_REDIS_URL`，即 Docker 部署默认使用 Redis Streams

**Numina 适配**: `packages/stream_bridge/` 是 DeerFlow StreamBridge 的适配实现，新增 `NuminaRedisStreamBridge`（tenant 隔离：key 格式 `numina:stream:{family_id}:{run_id}`）。

### 数据流

```
Child App (Vue)                    Backend (FastAPI)               Agent (DeerFlow)
─────────────                      ────────────────                ────────────────
LearningSessionPage                /child/learning/sessions/
  │                                  {id}/assess/stream             
  │── POST ──────────────────────> │                                │
  │   {session_id}                 │── AgentClient.post() ────────> │
  │                                │   /internal/gateway/runs/      │
  │                                │    learning-tutor/{thread_id}  │
  │                                │   (触发 run，fire-and-forget)   │
  │                                │                                │── _run_learning_tutor_agent()
  │                                │                                │   └─ RunPipeline
  │                                │                                │      └─ DeerFlowAdapter
  │                                │                                │         └─ DeerFlowClient.stream()
  │                                │                                │
  │                                │                                │── bridge.publish() ──► Redis Stream
  │                                │                                │   (NuminaRedisStreamBridge)
  │                                │                                │
  │                                │<─ MCP tool: get_learning_topic ─ │
  │                                │── MCP response ───────────────>  │   (MCP protocol, in-process)
  │                                │                                │
  │                                │  订阅同一 Redis Stream          │
  │                                │  bridge.subscribe(run_id)      │
  │                                │                                │
  │<── SSE frames ──────────────── │                                │
  │   (text/event-stream)          │                                │
```

### 子系统定位

| 子系统 | 职责 | 数据存储 |
|--------|------|---------|
| **Frontend** | UI 渲染、SSE 消费、用户输入 | — |
| **Backend** | 会话管理、权限校验、SSE 分发（从 Redis 读取）、MCP tool 数据端点 | LearningSession (thread_id, status) |
| **Agent** | DeerFlow 编排、LLM 对话、tool 调用、写 bridge | Checkpointer (对话历史)、Redis StreamBridge (事件流) |

### 关键变化（相比现有实现）

| 维度 | 现有 | 本次设计 |
|------|------|---------|
| Agent bridge | MemoryStreamBridge (进程内, bounded 256) | **NuminaRedisStreamBridge** (跨进程, TTL 24h) — 所有 runner 统一 |
| Backend 消费方式 | `_pump_agent_sse_to_bridge()` 解析 HTTP SSE 行 | **直接订阅 Redis Stream** — 所有 runner 统一（**删除 pump 层**） |
| 对话历史 | Checkpointer (已有) | **复用 Checkpointer** (无变化) |
| 断连恢复 | Backend 侧 Redis bridge (Pattern B 部分实现) | **Redis StreamBridge + Checkpointer** (完整) |
| 新增缓存层 | — | **无** (全部复用 DeerFlow 组件) |
| `_pump_agent_sse_to_bridge()` | 5 个 runner 的 HTTP SSE → bridge 中间层 | **删除** — agent 写 Redis，backend 直接读 |

### 架构决策记录 (ADR)

#### ADR-1: 全量迁移所有 runner 到 Redis StreamBridge

**状态**: ✅ 已确认（用户明确要求）

**决策**: 本次不仅为 learning-tutor 引入 Redis bridge，而是**一次性将所有 6 个 runner（含 learning-tutor）从 memory bridge + HTTP SSE pump 迁移到 Redis StreamBridge**。

**原始需求原文**: "这个功能点需要先回顾检视一下 backend 与 agent 的协作关系，以达到最佳复用性"，"去掉过度封装的 Backend sse 缓存层，改为使用 deerflow 的 redis bridge"。

**理由**:
1. 用户希望借此机会重构 backend→agent 的断联缓存架构，引入 Redis 作为基础设施依赖
2. 支持完整 DeerFlow 能力（跨进程事件分发、Last-Event-ID 重连、gap recovery）
3. 两种 SSE 消费模式并存（pump + Redis）增加维护成本且违反架构一致性
4. Pump 死亡导致事件丢失是已知设计缺陷，不应保留给任何 runner

**影响**: 这是一次基础设施重构，范围超出 learning-tutor 功能本身。5 个现有 runner 的 pump 调用全部替换为 Redis subscribe。生产环境 Redis 成为硬依赖。

#### ADR-2: Tool 注册采用 MCP 协议而非 AgentClient HTTP callback

**状态**: ✅ 已确认

**决策**: 3 个 learning tool 通过 MCP 协议注册，而非原始需求中提到的 "AgentClient 模式"。

**原始需求原文**: "复制 backend API（AgentClient 模式）的实现"。

**偏离理由**:
1. **一致性** — 现有 5 个调度 app 的数据 tools（`get_assets`、`get_liabilities`、`get_amortization_schedule` 等）全部通过 MCP 协议暴露给 agent
2. **自动发现** — agent 的 `MultiServerMCPClient` 自动获取 tool 列表，无需手动注册
3. **直接 DB 访问** — MCP tools 在 backend 进程内执行，无 HTTP 开销
4. **Tenant 隔离** — MCP session 自动携带 `family_id` context
5. **职责边界** — AgentClient 适合 "agent→backend 回调"（触发通知、写入结果），MCP 适合 "agent 在对话中查询数据"

**结论**: 原始需求中的 "AgentClient 模式" 描述的是 "通过 agent 模块实现 SSE" 的整体能力，而非特指 tool 注册机制。Tool 层采用 MCP 与现有架构一致，SSE 能力通过 AgentClient 触发 run 实现。

## 详细设计

### 1. Agent 侧：Redis StreamBridge

**文件**: `server/apps/agent/services/runtime/lifespan.py`

将 `init_runtime()` 中的 bridge 从 memory 切换为 redis：

```python
# 现有
config = StreamBridgeConfig(type="memory", queue_maxsize=256)

# 改为 (带 graceful fallback)
try:
    config = StreamBridgeConfig(
        type="redis",
        redis_url=settings.STREAM_BRIDGE_REDIS_URL or settings.REDIS_URL or "redis://redis:6379/0",
        queue_maxsize=256,
        stream_ttl_seconds=86400,  # 24h
    )
    # 验证 Redis 连通性
    await _verify_redis_bridge(config.redis_url)
except (ConnectionError, TimeoutError) as e:
    logger.warning(f"Redis bridge unavailable, falling back to memory: {e}")
    config = StreamBridgeConfig(type="memory", queue_maxsize=256)
```

**影响分析**:
- **所有 runner 统一切换**: 5 个现有 runner（chat, asset-report, finance-coach, literacy-report, dashboard-narrative）+ learning-tutor 全部写入 Redis
- 现有 `sse_consumer()` 通过 `bridge.subscribe(run_id)` 读取事件——切换到 Redis 后接口不变，`NuminaRedisStreamBridge.subscribe()` 实现了相同的 `AsyncIterator[StreamItem]` 协议
- 现有 HTTP SSE 端点 (`/api/threads/{id}/runs/stream`) 继续工作——`sse_consumer` 从 Redis 读取而非内存，行为等价（保留用于调试和直接 API 调用）
- `supports_cross_process = True`：Redis bridge 支持跨进程读写，这是 backend 直接订阅的前提
- Redis key 格式：`numina:stream:{family_id}:{run_id}`（NuminaRedisStreamBridge 自动处理 tenant 隔离）

**环境变量**: 新增 `STREAM_BRIDGE_REDIS_URL` (agent) 或使用现有 `REDIS_URL`。Agent 的 `AgentSettings` 需要增加此配置。

**Graceful fallback**: 当 Redis 不可用时，回退到 MemoryStreamBridge 并 log warning。开发环境可配置 `STREAM_BRIDGE_TYPE=memory`。注意：fallback 到 memory bridge 后，cross-process subscription 不可用——**此时 agent 的 HTTP SSE 端点仍可用于调试，但 backend 不再消费它**。生产环境 Redis 是硬依赖（与 DeerFlow 上游一致：`config.example.yaml` 文档说明 "the redis bridge is fail-hard in v1... a mid-run Redis outage fails the active run"）。

**部署约束**: Agent 和 Backend **必须**连接同一个 Redis 实例。Docker Compose 中使用同一个 `redis://redis:6379/0`；生产环境需确保 `STREAM_BRIDGE_REDIS_URL`（agent）与 Backend 的 `REDIS_URL` 指向同一集群。建议启动时增加 Redis 连通性检查（已在上方代码中体现）。

### 2. Agent 侧：learning-tutor Runner

**文件**: `server/apps/agent/services/runtime/worker.py`

新增 `_run_learning_tutor_agent()` runner，遵循现有 runner 模式（与 `_run_numina_agent`、`_run_asset_report_agent` 一致），通过 `RunPipeline` → `DeerFlowAdapter.typed_stream_dispatch` 执行：

```python
async def _run_learning_tutor_agent(
    record: RunRecord,
    bridge: StreamBridge,
    *,
    family_id: str,
    user_id: str,
    metadata: dict,
) -> None:
    """Learning tutor — AI 辅导对话 (DeerFlow skill: learning-tutor)."""
    async with RunPipeline(record, bridge, ...) as pipeline:
        # 通过 DeerFlowAdapter 执行，与现有 runner 路径一致
        await pipeline.run(
            adapter=family_adapter_cache.get_family_adapter(family_id),
            user_message=record.user_message,
            thread_id=record.thread_id,
            skill_name="learning-tutor",
        )
        # RunPipeline 自动通过 bridge.publish() 发送事件
        # DeerFlow 的 learning-tutor skill 会调用 MCP tools 获取数据
```

在 `run_agent()` 的 `metadata["app"]` 分支中添加：
```python
elif app == "learning-tutor":
    await _run_learning_tutor_agent(...)
```

### 3. Agent 侧：Gateway 端点

**文件**: `server/apps/agent/app/routers/gateway.py`

新增 internal trigger 端点：

```python
@router.post("/internal/gateway/runs/learning-tutor/{thread_id}")
async def trigger_learning_tutor_run(
    thread_id: str,
    request: Request,
    family_id: str = Header(...),
    user_id: str = Header(...),
):
    """Backend → Agent: 触发 learning-tutor run."""
    await verify_service_token(request)
    body = SimpleNamespace(
        input={"messages": [...]},
        metadata={"app": "learning-tutor", **extra_metadata},
    )
    return await start_run(body, thread_id, request, family_id, user_id, internal=True)
```

**注意**: `start_run` 返回 `StreamingResponse`（HTTP SSE）。对于 learning-tutor，backend 不使用这个 HTTP SSE 响应——它直接订阅 Redis Stream。HTTP SSE 仅用于确认 run 已启动（或作为其他调用方的 fallback）。

**端点模式**: 遵循现有 runner 的 dedicated endpoint 模式（`gateway.py` 中每个 app 有独立端点：`/runs/asset-report/{thread_id}`、`/runs/finance-coach/{thread_id}` 等）。新增 `/internal/gateway/runs/learning-tutor/{thread_id}`，使用 `verify_service_token` 认证（`X-Agent-Token` header），与现有 runner 保持一致。`internal=True` 参数自动绕过 R1 前端直接调度门控。

### 4. Agent 侧：Tool 注册

> **设计决策 — MCP tool 模式 vs AgentClient HTTP callback 模式**
>
> 原始需求描述为"复制 backend API（AgentClient 模式）的实现"。经评估，选择 MCP tool 模式而非 AgentClient HTTP callback。理由：
> 1. **一致性** — 现有 5 个调度 app 的数据 tools（`get_assets`、`get_liabilities`、`get_amortization_schedule` 等）全部通过 MCP 协议暴露给 agent，learning tools 不应引入新模式
> 2. **自动发现** — agent 的 `MultiServerMCPClient` 自动获取 tool 列表，无需手动注册或维护 URL 映射
> 3. **直接 DB 访问** — MCP tools 在 backend 进程内执行，直接查询 DB，无 HTTP 开销和序列化成本
> 4. **Tenant 隔离** — MCP session 自动携带 `family_id` context，无需额外 header 传递
> 5. **AgentClient 模式的适用场景** — AgentClient 适合"agent 主动调用 backend 端点"的回调场景（如触发通知、写入结果），不适合"agent 在对话中查询数据"的 tool 场景

**Tool 注册方式**: 遵循现有 MCP tool 模式（与 `get_assets`、`get_liabilities` 等一致）。3 个 learning tool 注册为 backend MCP server 的 tools，agent 通过 MCP client 自动发现。

**SKILL.md 声明**: `learning-tutor` SKILL.md 的 `allowed-tools` 已声明 3 个 tool 名称：
```yaml
allowed-tools:
  - get_learning_topic
  - get_child_learning_profile
  - record_learning_result
```

`sync_tool_patch.py` 的 `_apply_active_skill_tool_filter()` 会在运行时按精确名称匹配过滤 tools。只要 backend MCP server 暴露了同名 tool，agent 的 `MultiServerMCPClient`（`tool_name_prefix=False`）会自动发现并使用。

**Backend MCP Tool 实现**:

**新增文件**: `server/apps/backend/app/services/learning/mcp_learning_tools.py`

3 个 MCP tool 函数（直接访问 DB，不走 HTTP）：

```python
from apps.backend.app.services.mcp_tool_registry import register_tool

@register_tool
async def get_learning_topic(topic_id: int, child_id: int) -> dict:
    """获取 topic 详情 + child 的掌握程度。"""
    # 直接查询 LearningTopic + LearningProgress
    # family_id 从 MCP session context 获取（自动 tenant 隔离）
    ...

@register_tool
async def get_child_learning_profile(child_id: int, subject: str | None = None) -> dict:
    """获取 child 学习档案：已掌握/学习中/可用数量。"""
    ...

@register_tool
async def record_learning_result(session_id: int, evaluation: dict) -> dict:
    """记录 AI 评估结果，更新 progress，触发奖励。"""
    # Schema 验证 evaluation 结构
    # 更新 LearningProgress + 触发 coin/badge 奖励
    ...
```

**关键约束**:
- Tool 名称必须精确匹配 SKILL.md 的 `allowed-tools`：`get_learning_topic`、`get_child_learning_profile`、`record_learning_result`
- MCP tools 使用 base names（无前缀），因为 `MultiServerMCPClient(tool_name_prefix=False)`
- `record_learning_result` 需要严格的 schema 验证（LLM 输出不可信）

### 5. Backend 侧：MCP Tool 实现（替代原 Internal HTTP 端点方案）

**新增文件**: `server/apps/backend/app/services/learning/mcp_learning_tools.py`

详见 Section 4。3 个 learning tool 作为 MCP tools 在 backend 进程内执行，直接查询 DB，无需额外的 internal HTTP 端点。

**注意**: 原设计中的 `learning_internal.py` router（3 个 internal HTTP 端点）已不再需要。MCP tools 通过 MCP 协议暴露给 agent，数据访问在 backend 进程内完成。如未来需要非 MCP 场景的 REST API（如家长端查看学习数据），可另行添加。

### 6. Backend 侧：Assessment Stream 端点

**文件**: `server/apps/backend/app/routers/learning_child.py`

新增 streaming 端点：

```python
@router.post("/sessions/{session_id}/assess/stream")
async def stream_assessment(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    child_id: int = Depends(get_current_child_id),
):
    """启动 AI 评估并返回 SSE 流。"""
    # 1. 验证 session + 创建 DeerFlow thread
    session = session_service.get_session_with_thread(db, session_id, child_id)

    # 2. 触发 agent run (fire-and-forget — agent 写 Redis)
    agent_client = AgentClient(family_id=str(request.state.family_id), user_id=str(child_id))
    await agent_client.post(
        f"/internal/gateway/runs/learning-tutor/{session.thread_id}",
        json={...},
    )

    # 3. 订阅同一 Redis Stream，转发 SSE 给前端
    redis_bridge = get_backend_redis_bridge()  # 创建 NuminaRedisStreamBridge reader
    return StreamingResponse(
        _stream_sse_from_redis(redis_bridge, session.thread_id, run_id),
        media_type="text/event-stream",
    )
```

**Backend Redis Bridge Reader**: Backend 创建自己的 `NuminaRedisStreamBridge` 实例（共享同一个 Redis），通过 `bridge.subscribe(run_id, last_event_id=...)` 读取 agent 写入的事件。这替代了现有的 `_pump_agent_sse_to_bridge()` HTTP SSE 消费模式。

**替换现有 pump 模式（不再共存）**:

现有 `_pump_agent_sse_to_bridge()` 是一个脆弱的中间层：agent HTTP SSE → 逐行解析 SSE 帧 → `bridge.publish()`。该 pump 作为后台任务运行，一旦 pump 死亡，agent 继续产出的事件**无法到达 backend bridge**——前端恢复后丢失 pump 断开期间的所有对话事件。

照搬 DeerFlow 的实现（Docker 部署默认使用 `RedisStreamBridge`，见 `STREAMING.md` + `config.example.yaml`），本次设计将 Redis bridge 提升为**所有 runner 的统一模式**，彻底删除 pump 层：

```
旧架构（所有 runner）:
  Agent [memory bridge] → HTTP SSE → Backend pump [parse SSE] → Backend bridge → Frontend
                                  ↑ 脆弱中间层

新架构（所有 runner）:
  Agent [Redis bridge] → Redis Stream ← Backend subscribe → Frontend
                       ↑ 统一持久化层，无 HTTP SSE 中间层
```

**迁移范围：**

1. Agent bridge 切换为 Redis（所有 runner 的 `bridge.publish()` 自动写入 Redis）
2. Backend shared bridge 切换为 Redis（`consume_task_stream()` 和 `_spawn_lifecycle_consumer()` 自动从 Redis 读取）
3. 5 个现有 backend router 的 pump 调用替换为 Redis subscribe（`ai_report`、`ai_finance_coach`、`ai_literacy_report`、`dashboard`、`ai_chat`）
4. 删除 `_pump_agent_sse_to_bridge()` 及 SSE 行解析逻辑

**Trade-off**: 这是一次性全量迁移（6 个 runner），而非渐进式共存。选择全量迁移的理由：
1. **消除架构分裂** — 两种 SSE 消费模式并存增加认知负担和维护成本
2. **Pump 是已知脆弱点** — pump 死亡导致事件丢失是设计缺陷，不应保留给任何 runner
3. **DeerFlow 验证** — 上游 Docker 部署默认使用 Redis bridge，已生产验证
4. **迁移成本低** — `NuminaRedisStreamBridge` 已实现，`get_shared_bridge()` 已支持 Redis

> **实现细节**（具体迁移步骤、pump 功能替代方案、各 router 的代码模式）将在 plan 阶段使用 agent-dev 技能细化。

**Thread 管理**: 遵循现有 runner 的 "session ID as thread ID" 模式（与 chat、asset-report 一致）：
1. Backend 创建 `LearningSession` 行（Snowflake ID）
2. 用 `str(session.id)` 作为 thread_id 传给 agent gateway（无需显式调 `POST /api/threads`）
3. Agent gateway 在首次 run 请求时隐式创建 thread（幂等：已存在则复用）
4. 将 skill 上下文（topic_id, session_type, child 信息）作为 `user_message` 传给 agent

**注意**: `LearningSession` 模型不需要额外的 `thread_id` 字段 — session ID 本身就是 thread ID。这与现有 `AIChatSession` 模式一致（`session.thread_id or str(session.id)` fallback 逻辑）。

### 7. Backend 侧：注册变更

| 文件 | 变更 |
|------|------|
| `bootstrap/agents.py` | 添加 `learning-tutor` 系统 agent |
| `routers/ai_skills.py` | `RESERVED_NAMES` 添加 `"learning-tutor"` |
| `app/main.py` | 注册 MCP learning tools（替代原 `learning_internal` router） |

### 8. Backend 侧：清理

**Learning tools 桩清理:**

删除 `mcp_tools.py` 中的 `NotImplementedError` 桩（3 个 tool 已由 `mcp_learning_tools.py` 以 MCP tool 方式实现）。

**SSE pump 层清理（全量迁移的核心产出）:**

| 清理项 | 涉及文件 |
|--------|---------|
| 删除 `_pump_agent_sse_to_bridge()` 及 SSE 行解析逻辑 | `bridge_consumer.py` |
| 5 个 router 的 pump 调用替换为 Redis subscribe | `ai_report.py`, `ai_finance_coach.py`, `ai_literacy_report.py`, `dashboard.py`, `ai_chat.py` |
| Backend shared bridge 默认改为 redis | `bridge_consumer.py` |

> **实现细节**（各 router 的具体替换模式、pump 功能的替代方案）将在 plan 阶段使用 agent-dev 技能细化。

### 9. Frontend 侧：SSE 基础设施

**新增文件**: `frontend/packages/shared/src/utils/sseReader.ts`

提取 main app 的 `sseReader.ts` 到 `@numina/shared` 包，child app 和 main app 共同引用。（不复制——直接提取共享，避免两份代码漂移。）

**新增文件**: `frontend/apps/child/src/composables/useLearningChat.ts`

轻量级 learning chat composable（~200 行），不使用 LangGraph SDK，使用 `fetch()` + `sseReader`：

```typescript
export function useLearningChat() {
  const messages = ref<ChatMessage[]>([])
  const status = ref<'idle' | 'connecting' | 'streaming' | 'completed' | 'error'>('idle')
  const lastEventId = ref<string | null>(null)

  async function startAssessment(sessionId: string) {
    status.value = 'connecting'
    const response = await fetch(`/api/v1/child/learning/sessions/${sessionId}/assess/stream`, {
      method: 'POST',
      credentials: 'include',
    })
    status.value = 'streaming'
    await readSSEStream(response, {
      onMessage(data) { /* 追加消息到 messages */ },
      onCustom(data) { /* 处理 tool_call, tool_result, learning-tutor.result */ },
      onError(data) { status.value = 'error' },
      onEnd(data) { status.value = 'completed' },
      onMetadata(data) { /* 提取 run_id */ },
    })
  }

  async function reconnect(sessionId: string) {
    // 带 Last-Event-ID 重连
    // 或先 GET status 判断 run 状态，再决定是读历史还是续流
  }

  return { messages, status, startAssessment, reconnect, sendMessage }
}
```

### 10. Frontend 侧：LearningSessionPage 改造

**文件**: `frontend/apps/child/src/pages/learning/LearningSessionPage.vue`

替换 placeholder 为完整 chat UI：
- 消息列表（支持 text、tool_call、tool_result 渲染）
- 输入框（child 可以输入回答）
- 流式显示（打字机效果）
- 头部状态切换（tutorial 蓝色 → assessment 橙色）
- "完成会话" 按钮
- 断连重连指示器

### 11. 断连与重连

#### 断连场景

| 场景 | Agent 行为 | 数据存储 | 恢复方式 |
|------|-----------|---------|---------|
| **Frontend ↔ Backend 断开** | 不受影响（agent 写 Redis，不感知 backend 状态） | Redis Stream 持续累积 + Checkpointer 持续写入 | Backend 从 Redis Stream 续传 Last-Event-ID |
| **Backend ↔ Agent 断开** | 不受影响（bridge 是 Redis，不依赖 HTTP 连接） | 同上 | Backend 重新订阅 Redis Stream（同一 run_id） |
| **Agent 进程崩溃** | 停止写入 | Checkpointer 持久化（对话历史完整）；Redis Stream 已写入事件保留 | Backend 从 Checkpointer 读对话历史，标记 run 为 interrupted |

#### 重连流程

```
前端重连:
  │
  ├── 1. GET /child/learning/sessions/{id}/status
  │      → { run_status: "running" | "completed" | "interrupted",
  │          thread_id, last_event_id? }
  │
  ├── 2a. completed → 从 Checkpointer 读消息历史 (via agent thread API)
  │       渲染完整对话，显示 "会话已结束"
  │
  ├── 2b. running → POST /sessions/{id}/assess/stream (带 last_event_id)
  │       Backend 从 Redis Stream 的 last_event_id 位置续读
  │       前端继续渲染新事件
  │
  └── 2c. interrupted → 提示 "连接中断"，可选重新开始或继续
```

### 12. 会话生命周期

```
createSession (DB)
    │
    ▼
startAssessment
    ├── 创建 DeerFlow thread (agent /api/threads)
    ├── 存 thread_id → LearningSession
    ├── 调 agent /internal/gateway/runs/learning-tutor/{thread_id}
    │   └── agent: RunPipeline → DeerFlow → bridge.publish → Redis
    └── Backend 订阅 Redis → SSE 给前端

对话进行中
    ├── LLM 调用 get_learning_topic → MCP tool → backend 进程内 DB 查询
    ├── LLM 调用 get_child_learning_profile → 同上
    └── LLM 调用 record_learning_result → 同上

endSession
    ├── 标记 session.ended_at
    ├── 更新 score + ai_evaluation
    └── 更新 LearningProgress 状态
```

## Deferred Items 处理

本次从 code review deferred 列表中挑选与 DeerFlow SSE 集成直接相关的项：

| Deferred Item | 处理 |
|---------------|------|
| **OQ-1**: MCP Tools are stubs | ✅ 本次实现 — 3 个 tool 通过 MCP 协议实现（见 Section 4 设计决策） |
| **OQ-5**: LearningSessionPage AI chat placeholder | ✅ 本次实现 — 完整 chat UI + SSE 连接 |

**本次新增的架构重构（ADR-1 确认的全量迁移，用户明确要求借此机会重构断联缓存架构）：**

| 重构项 | 范围 | 说明 |
|--------|------|------|
| **Agent bridge 切换** | `lifespan.py` | memory → Redis，所有 runner 统一 |
| **删除 `_pump_agent_sse_to_bridge()`** | `bridge_consumer.py` | 去掉 HTTP SSE 中间层，backend 直接订阅 Redis |
| **5 个现有 router 迁移** | ai_report / ai_finance_coach / ai_literacy_report / dashboard / ai_chat | pump 调用替换为 Redis subscribe |

以下 deferred items **不在本次范围**：

| Item | 原因 |
|------|------|
| OQ-2: Translation service placeholder | 独立功能，不涉及 SSE |
| OQ-3: `learning_streak_3_failures` notification | 通知系统，不涉及 SSE |
| OQ-4: "Today learning" card | UX 装饰 |
| OQ-6: Seed quality validation | 数据质量 |
| OQ-7: Badge count discrepancy | Spec 对齐 |
| OQ-10~17: 各种 minor items | 代码质量 / UX |

## 安全考量

1. **Agent tool 输入不可信**: `get_learning_topic(topic_id, child_id)` 的 `topic_id` 和 `child_id` 来自 LLM 输出，必须校验格式（整数范围）和权限（child_id 属于当前 family）
2. **Backend internal 端点使用 `verify_service_token`**: `Authorization: Bearer {agent_jwt}` + `X-Family-Id` header，与现有 internal 端点一致。Agent `BackendClient._make_headers()` 自动生成正确 header。
3. **`record_learning_result` 防滥用**: 评估结果结构需要 schema 验证（`evidence_results` 数组、`overall_score` 0-1 范围、`recommendation` 枚举值）
4. **Thread 隔离**: DeerFlow checkpointer 按 `thread_id` 隔离，与现有模式一致
5. **Redis Stream tenant 隔离**: `NuminaRedisStreamBridge` 的 key 格式 `numina:stream:{family_id}:{run_id}` 确保跨家庭不可见
6. **更新 `agent/CLAUDE.md` §Security Rules**: 新 runner + 新 skill 需要更新安全规则 + sim-test Area 11

## 测试策略

### Agent 侧

- `tests/agent/integration/test_learning_mcp_tools.py` — 3 个 MCP tool 的 DB 查询逻辑（mock SQLAlchemy session）
- `tests/agent/integration/test_learning_tutor_dispatch.py` — worker dispatch + RunPipeline 集成
- `tests/agent/integration/test_redis_bridge.py` — Redis bridge publish/subscribe 跨进程

### Backend 侧

- `tests/backend/integration/test_learning_assess_stream.py` — assessment stream 端到端

### Frontend 侧

- `useLearningChat` composable 单元测试（mock SSE response）
- `LearningSessionPage` 组件测试

## 实现依赖

```
Agent bridge 切换 (Redis)
    │
    ├── Agent runner + gateway + tools ──┐
    │                                     ├── Backend internal endpoints
    ├── Backend assess/stream endpoint ──┤
    │                                     ├── Backend 注册变更
    │                                     │
    └── Frontend SSE + UI ───────────────┘
         (依赖 backend 端点就绪)
```

## 文件变更清单

> 以下列出新增和关键修改的文件。具体的 pump 迁移代码模式、各 router 的替换细节，将在 plan 阶段使用 agent-dev 技能细化。

### 新增文件 (7)

| 文件 | 职责 |
|------|------|
| `server/apps/backend/app/services/learning/mcp_learning_tools.py` | 3 个 MCP tool 函数 |
| `frontend/packages/shared/src/utils/sseReader.ts` | SSE 帧解析器（从 main app 提取到共享包） |
| `frontend/apps/child/src/composables/useLearningChat.ts` | Learning chat composable |
| `server/tests/agent/integration/test_learning_mcp_tools.py` | MCP tool 集成测试（mock DB） |
| `server/tests/agent/integration/test_learning_tutor_dispatch.py` | Agent dispatch 集成测试 |
| `server/tests/agent/integration/test_redis_bridge.py` | Redis bridge 跨进程测试 |
| `server/tests/backend/integration/test_learning_assess_stream.py` | Stream 集成测试 |

### 修改文件

| 分类 | 文件 | 变更 |
|------|------|------|
| **Agent bridge** | `lifespan.py`, `config.py` | bridge: memory → redis（所有 runner 统一） |
| **Agent runner** | `worker.py`, `gateway.py` | 新增 learning-tutor runner + trigger |
| **Pump 删除** | `bridge_consumer.py` | 删除 `_pump_agent_sse_to_bridge()` + SSE 解析；默认 bridge 改 redis |
| **Pump 迁移** | `ai_report`, `ai_finance_coach`, `ai_literacy_report`, `dashboard`, `ai_chat` | pump 调用替换为 Redis subscribe |
| **Learning 新增** | `learning_child.py`, `session_service.py`, `bootstrap/agents.py`, `ai_skills.py`, `main.py` | assess/stream 端点 + 注册 |
| **Frontend** | `LearningSessionPage.vue`, `learning.ts`, main app `sseReader.ts` → `@numina/shared` | 替换 placeholder + SSE API + sseReader 提取共享 |

### 删除/清理

| 文件 | 处理 |
|------|------|
| `mcp_tools.py` | 删除 NotImplementedError 桩 |
| `bridge_consumer.py` 中的 pump 函数 + SSE 解析 | **删除** — 全量迁移到 Redis subscribe |

---

## Open Questions (from doc review 2026-09-23)

> All 4 resolved — see inline Design Rationale, Section 4, Section 6 updates.

### ~~OQ-SSE-1: Redis bridge vs HTTP SSE pattern 设计理据~~ ✅ Resolved
**Resolution:** 已在 "核心原则" 后添加 Design Rationale 子节，说明 HTTP SSE pump 模式下 pump 死亡导致事件丢失风险，以及 Redis bridge 提供事件持久化和跨进程重连能力。

### ~~OQ-SSE-2: Tool 注册机制~~ ✅ Resolved
**Resolution:** 改为 MCP tool 模式（与现有 `get_assets` 等一致）。3 个 tools 注册为 backend MCP server tools，agent MCP client 自动发现。详见 Section 4 更新。

### ~~OQ-SSE-3: Backend bridge 消费模式共存~~ ✅ Resolved
**Resolution:** 不再共存。照搬 DeerFlow 实现（Docker 默认 Redis bridge），本次一次性将所有 runner 从 HTTP SSE pump 迁移到 Redis 直读。删除 `_pump_agent_sse_to_bridge()`，6 个 runner（含 learning-tutor）统一使用 Redis Stream subscribe。详见 Section 6 "替换现有 pump 模式"。

### ~~OQ-SSE-4: Thread 创建流程细节~~ ✅ Resolved
**Resolution:** 已在 Section 6 "Thread 管理" 明确：使用 `LearningSession.id` 作为 thread_id（与 chat/report 模式一致），无需显式创建 thread。
