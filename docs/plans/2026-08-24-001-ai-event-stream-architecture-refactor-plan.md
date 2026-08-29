---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

# AI 事件流架构重构：恢复 DeerFlow 进程内 Bridge + Backend-Owned Buffer

## Summary

当前 AI 事件流使用 Redis Streams 作为 Agent ↔ Backend 的共享中间层，但这是一个**结构性问题**——Numina 把 DeerFlow 的单进程 bridge 拆成了跨进程，用 Redis 做胶水，却没有重新定义 buffer 所有权。结果是 Agent 和 Backend 各自创建独立 bridge 实例读写同一个 Redis stream，lifecycle 管理变成双路径。U1-U4 修复（commit 10ff61a6）解决了功能正确性症状，但保留了产生这些症状的架构。

**本文档的核心发现：不需要引入新的复杂度（HTTP push bridge），而是应该恢复 DeerFlow 的原生设计——bridge 是进程内的。**

---

## 根因分析：结构性问题

### DeerFlow 原生模式 vs Numina 当前模式

DeerFlow 的设计哲学：**bridge 是进程内的，publish 和 subscribe 共享同一个 bridge 实例。**

```
DeerFlow 原生（单进程）:
┌─────────── Agent 进程 ───────────┐
│                                   │
│  start_run()                      │
│    ├─ bridge = app.state.bridge   ← 单例（MemoryStreamBridge）
│    ├─ asyncio.Task(run_agent(bridge=bridge))
│    │     └─ bridge.publish(event) → 写入 memory buffer
│    └─ return StreamingResponse(sse_consumer(bridge, ...))
│          └─ bridge.subscribe()    → 从同一 memory buffer 读取
│                → format_sse() → HTTP response body
│                                   │
│  ✓ 一个 bridge 实例               │
│  ✓ 没有 Redis                     │
│  ✓ 没有 lifecycle consumer        │
│  ✓ HTTP response = 事件流         │
└───────────────────────────────────┘
```

Numina 把 DeerFlow 的单进程拆成了两个进程（Backend + Agent），然后引入 Redis 作为跨进程胶水：

```
Numina 当前（双进程 + Redis）:
┌── Backend 进程 ──┐         ┌── Agent 进程 ──┐
│                   │  HTTP   │                 │
│  trigger ─────────┼────────→│ run_agent()     │
│                   │         │   bridge.publish │
│  bridge_consumer ─┼──Redis──┼──→ XADD         │
│   (SSE forwarder) │  XREAD  │                 │
│   (lifecycle)     │←────────┼─ bridge 实例 B   │
│                   │         │                 │
│  bridge 实例 A    │         │  bridge 实例 C   │
└───────────────────┘         └─────────────────┘

✗ 三个 bridge 实例，共享同一个 Redis stream
✗ Buffer 无主 — Agent 控制 cleanup(60s)，Backend 期望 24h TTL
✗ Lifecycle 无主 — Agent RunManager + Backend lifecycle consumer 双路径
✗ Agent 需要 Redis 依赖
```

### 组件溯源：DeerFlow vs Numina 发明

| 组件 | 来源 | 说明 |
|------|------|------|
| StreamBridge 协议 + Memory 实现 | **DeerFlow** | 进程内 bridge |
| RedisStreamBridge（可选） | **DeerFlow** | **故意不导出** — "redis is an optional extra" |
| RunManager + RunRecord + RunStatus | **DeerFlow** | 生命周期状态机 |
| sse_consumer + format_sse | **DeerFlow** | HTTP response = 事件流 |
| Last-Event-ID + StreamGap | **DeerFlow** | 重连机制 |
| DisconnectMode.cancel/continue | **DeerFlow** | 断连策略 |
| **`_spawn_lifecycle_consumer`** | **Numina 发明** | DeerFlow 无此概念 |
| **`NuminaRedisStreamBridge`** | **Numina 发明** | 租户隔离 Redis keys |
| **`RunPipeline`** | **Numina 发明** | 5-app runner 脚手架 |
| **`packages/stream_bridge/`** | **Numina 发明** | 独立包（"Self-contained, no DeerFlow dependency"） |

**结论：`_spawn_lifecycle_consumer` 是 Numina 为解决跨进程任务状态跟踪而发明的模式。DeerFlow 原生不需要它，因为 publish 和 subscribe 在同一进程。**

### 为什么单实例还需要 Redis？

因为 Backend 和 Agent 是两个独立进程（Docker 容器）。DeerFlow 的 `sse_consumer` 在 Agent 进程里，通过 HTTP response 返回事件流。Backend 无法直接使用 Agent 进程内的 memory bridge。

**但 Redis 不是唯一解。** 两个进程之间的通信方式有：
1. **Redis Streams**（当前）— 共享中间层，两边各自创建 bridge 实例
2. **HTTP SSE**（推荐）— Backend 消费 Agent 的 HTTP 响应流，缓存到自己内部 buffer
3. **gRPC streaming** — 类似 HTTP SSE 但更高效

### 对比上一份 Plan（2026-08-23-001）

上一份 plan 的根因分析和修复：

| 根因 | 修复（U1-U4） | 本质 |
|------|-------------|------|
| RC1: lifecycle consumer 不区分成功/失败 | U2: `_verify_task_result` | **症状修复** — 在错误的架构上加补丁 |
| RC2: error 事件未通过 bridge 传递 | U1: `bridge.publish("error")` | **症状修复** — 为什么 Agent 直接写 Redis？没回答 |
| RC3: Redis 未启用 | docker-compose 加 Redis | **架构加固** — 巩固了错误的架构 |

上一份 plan 明确把架构重构列为 "Deferred"：
> "Deferred: 重构架构：Backend-owned EventBuffer + Agent HTTP 推送 — 需要更大的重构"

**核心问题：上一份 plan 把架构违规当作了"约束条件"而非根因。** U1-U4 在错误的架构上打了 4 个补丁，每个 patch 又引入了新的问题（sleep 竞态、字段不一致、verify 查错 report），形成了补丁套补丁的循环。

---

## 目标架构：恢复 DeerFlow 哲学

### 设计原则

1. **Bridge 是进程内的** — Agent 恢复 DeerFlow 原生 memory bridge
2. **Backend 拥有 buffer** — Backend 通过 HTTP SSE 接收 Agent 事件并缓存
3. **Lifecycle 单一所有权** — 只有 Backend 管理 AITask 状态
4. **Agent 零基础设施依赖** — Agent 不需要 Redis，不需要知道 Backend 的 buffer 实现

### 目标数据流

```
┌── Backend 进程 ──────────────────────────────┐  ┌── Agent 进程 ──────────────────────┐
│                                               │  │                                     │
│  POST /ai/report/generate/events              │  │  POST /internal/gateway/runs/...     │
│    ├─ create AITask                           │  │    ├─ start_run()                    │
│    ├─ AgentClient.post(url, json={...})       │──→│    ├─ bridge = memory bridge (单例)  │
│    │   └─ on_disconnect=continue              │  │    ├─ asyncio.Task(run_agent())      │
│    │                                          │  │    │   └─ bridge.publish(event)      │
│    ├─ 消费 Agent HTTP SSE 响应                │←──│    └─ sse_consumer(bridge) → SSE    │
│    │   └─ 存入 backend-owned buffer           │  │       (HTTP response body)           │
│    │       (memory 单实例 / redis 集群)       │  │                                     │
│    ├─ SSE forwarder → Frontend                │  │  ✓ DeerFlow 原生模式                 │
│    └─ lifecycle manager → complete/fail task  │  │  ✓ 一个 bridge 实例（memory）        │
│                                               │  │  ✓ 无 Redis 依赖                     │
│  Frontend 重连:                               │  │                                     │
│  GET /ai/tasks/detail/{id}/stream             │  │                                     │
│    → 从 backend buffer 读取                   │  │                                     │
│    → Last-Event-ID 重放                       │  │                                     │
└───────────────────────────────────────────────┘  └─────────────────────────────────────┘

✓ Buffer 有主 — Backend 控制 lifecycle 和 TTL
✓ Lifecycle 有主 — 只有 Backend 管理 AITask
✓ Agent 零基础设施依赖
✓ 单实例无需 Redis，集群时 Backend 内部用 Redis
```

### 与 DeerFlow 原生的差异点

| 维度 | DeerFlow 原生 | Numina 目标 | 原因 |
|------|-------------|------------|------|
| Bridge 位置 | 单进程内 | Agent 进程内 + Backend 缓存 | 双进程架构 |
| SSE 消费者 | 前端直接消费 Agent HTTP | Backend 消费 → 转发前端 | Backend 需要缓存 + lifecycle |
| Buffer | bridge 内 | Backend-owned buffer | 支持前端重连 |
| Lifecycle | RunManager（Agent 内） | AITaskService（Backend 内） | Backend 是任务所有者 |

---

## 深度 Code Review（当前实现）

### Review 发现汇总

共 9 个 verified findings，全部可追溯到 "Agent 直接写 Redis" 这个结构性根因。

| # | 严重度 | 问题 | 文件 | 根因关联 |
|---|--------|------|------|----------|
| C1 | CRITICAL | Agent cleanup(delay=60) 删除 Redis stream | `run_pipeline.py:476` | Agent 不应控制 buffer lifecycle |
| C2 | CRITICAL | sleep(0.5) 竞态（lifecycle vs SSE consumer） | `bridge_consumer.py:309` | 两个独立 consumer 无协调 |
| H1 | HIGH | _verify_task_result 查 ANY report 非 THIS run | `bridge_consumer.py:152` | Lifecycle consumer 是补丁 |
| H2 | HIGH | Agent 直接写 Redis — 架构边界破坏 | `lifespan.py:44` | 跨进程 bridge 拆分的后遗症 |
| H3 | HIGH | 每个 SSE 连接创建新 Redis 客户端 | `bridge_consumer.py:80` | Backend 需要自己的 bridge 实例读 Redis |
| H4 | HIGH | reconnect() 是死代码（134 行） | `useReportStream.ts:483` | 前端重连路径分裂 |
| H5 | HIGH | SSE 解析代码重复 ~180 行 | `useReportStream.ts:394` | 补丁累积 |
| H6 | HIGH | 错误字段名 3 种格式 | `worker.py` / `run_pipeline.py` / `bridge_consumer.py` | Agent+Backend 各自定义格式 |
| H7 | HIGH | Lifecycle consumer 失败 → task 永远 running | `bridge_consumer.py:256` | 跨进程状态同步脆弱 |

### 目标架构能消除的问题

实施目标架构后，以下 findings **直接消失**（不需要单独修复）：

| Finding | 消失原因 |
|---------|----------|
| C1: Agent cleanup(delay=60) | Agent 不再访问 Redis，无 cleanup 概念 |
| H2: Agent 直接写 Redis | Agent 恢复 memory bridge，无 Redis |
| H3: Redis 连接泄漏 | Backend 不再每连接创建 Redis client |
| H6: 错误字段 3 种格式 | 只有 Agent 发布事件，格式统一 |
| C2: sleep(0.5) 竞态 | Backend 内部单一 consumer，无竞态 |

---

## 重构方案

### Phase 0: 紧急修复（可在当前分支完成，不改架构）

修复 C1 和 C2，不需要架构重构。

#### 0.1 移除 Agent 的 bridge.cleanup(delay=60)
- **File:** `run_pipeline.py:476`
- **Change:** 删除 `bridge.cleanup(run_id, delay=60)` 调用
- **Reason:** Redis TTL（86400s）已处理自然过期。Agent 不应控制 buffer lifecycle。
- **Risk:** 无。Redis stream 由 TTL 自然清理。

#### 0.2 修复 _verify_task_result 查询范围
- **File:** `bridge_consumer.py:152`
- **Change:** 检查 report 的 `generated_at` 是否在合理时间窗口内（如最近 10 分钟），而非仅检查 "任何 report 存在"
- **Risk:** 低。只是收紧查询条件。

#### 0.3 删除死代码
- `_stream_asset_report_sse`（ai_report.py:95-155）— 旧的 HTTP 代理
- `_watch_report_task_completion`（ai_report.py:158-222）— 冗余轮询 watcher

### Phase 1: Backend 消费 Agent HTTP SSE（核心重构）

**目标：** Agent 恢复 DeerFlow 原生模式。Backend 通过 HTTP SSE 接收 Agent 事件并缓存。

#### 1.1 Backend: 触发 Agent 时改为 streaming POST

当前（non-streaming POST）:
```python
resp = await agent_client.post(agent_url, json={...})
run_id = extract_from_header(resp.headers, "Content-Location")
```

改为（streaming POST → 缓存到 backend buffer）:
```python
async with agent_client.stream("POST", agent_url, json={...}) as resp:
    async for line in resp.aiter_lines():
        event = parse_sse_line(line)
        await backend_buffer.append(run_id, event)
        # lifecycle 在 buffer 内部管理
        if event.type == "end":
            lifecycle.complete_or_fail(task_id)
```

**关键：** 这就是旧 `_stream_asset_report_sse` 的模式，但增加 Backend buffer 缓存。

#### 1.2 Backend: EventBufferManager（Backend-owned buffer）

```python
class EventBufferManager:
    """Backend 拥有的事件缓冲区。memory（单实例）或 redis（集群）。"""

    def __init__(self, backend_type: str = "memory"):
        # 单实例: 用 MemoryStreamBridge
        # 集群: 用 NuminaRedisStreamBridge（但只有 Backend 进程访问）
        ...

    async def append(self, run_id: str, event: str, data: Any): ...
    async def subscribe(self, run_id: str, last_event_id: str = None): ...
    async def mark_end(self, run_id: str): ...
    async def cleanup(self, run_id: str, delay: float = 300): ...
    # delay=300: 任务结束后保留 5 分钟，允许前端重连
```

#### 1.3 Agent: 恢复 DeerFlow 原生 memory bridge

- Agent 的 `lifespan.py` 改为始终使用 `MemoryStreamBridge`
- 删除 `STREAM_BRIDGE_TYPE` 和 `REDIS_URL` 环境变量
- `RunPipeline.__aexit__` 不再调用 `bridge.cleanup()`（由 Backend 控制）
- Agent 的 `sse_consumer` 正常返回 SSE 流（DeerFlow 原生）

#### 1.4 Agent: 移除 Redis 依赖

- `docker-compose.production.yml`: Agent 删除 `STREAM_BRIDGE_TYPE` 和 `REDIS_URL`
- `lifespan.py`: 删除 Redis bridge 创建逻辑
- `packages/stream_bridge/`: Agent 不再 import 此包

#### 1.5 Backend: 统一 lifecycle 管理

- `_spawn_lifecycle_consumer` 改为从 backend buffer 订阅（不再创建新 Redis bridge）
- 合并 SSE forwarder + lifecycle consumer 为单一 consumer（消除 sleep 竞态）
- 删除 `_watch_report_task_completion`

#### 1.6 迁移步骤

1. Backend: 新增 `EventBufferManager` + 统一 consumer
2. Backend: trigger endpoints 改为 streaming POST → buffer → SSE
3. Agent: 恢复 memory bridge（始终）
4. Agent: 删除 Redis 配置和依赖
5. Docker: Agent 删除 Redis 环境变量
6. 删除 `_stream_asset_report_sse` + `_watch_report_task_completion`
7. 集成测试

### Phase 2: 前端清理

#### 2.1 删除 reconnect() 死代码
- `useReportStream.ts`: 删除 `reconnect()` 方法（134 行）
- 删除 `doFetch()` 中的 `Last-Event-ID` header 发送

#### 2.2 消除 SSE reader 重复
- 提取 `_readSSEStream(reader, handlers)` 共享函数
- `connect()` 复用

#### 2.3 统一错误字段
- 前端统一读取 `error` 字段（Agent 统一为 `{error, error_type}` 格式）

---

## Scope Boundaries

### In scope
- Phase 0 紧急修复（当前分支可完成）
- Phase 1 核心重构（Agent 恢复 memory + Backend 消费 HTTP SSE）
- Phase 2 前端清理

### Deferred
- 集群部署的 Backend Redis buffer 实现（Phase 1 先用 memory，验证后再加 Redis）
- Agent HTTP push bridge（如果 Backend 消费 HTTP SSE 足够，则不需要单独的 push 端点）
- 前端 useTaskResume 重构（当前可工作）

### Out of scope
- DeerFlow harness 修改
- LLM prompt engineering
- 新 skill 类型开发

---

## Risks & Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backend 消费 Agent SSE 断连 | Backend 丢失后续事件 | `on_disconnect=continue` + Backend 侧 reconnect |
| Backend buffer 内存增长 | 大量并发任务占用内存 | TTL 清理 + 最大事件数限制（maxlen=256） |
| Streaming POST 阻塞 Backend worker | Agent 运行时间长（report ~2min） | FastAPI async + 后台 task 消费 SSE |
| 迁移期间双模式 | 部分 skill 用 Redis，部分用 memory | 逐 skill 迁移，feature flag |

---

## Verification Contract

### Phase 0 验证
1. `bridge.cleanup(delay=60)` 已删除
2. `_verify_task_result` 检查时间窗口
3. 死代码已删除
4. 现有测试通过

### Phase 1 验证
1. Agent 进程无 redis import（`grep -r redis server/apps/agent/`）
2. Agent 使用 `MemoryStreamBridge`（日志确认）
3. Backend streaming POST 消费 Agent SSE（日志确认）
4. Backend buffer 管理 AITask lifecycle
5. 前端重连从 Backend buffer 读取

### 端到端验证
1. demouser 登录 → 触发报告生成 → 进度显示 → 报告渲染
2. 报告生成中切换到 dashboard → 返回 → 从最新点继续
3. 报告生成中 F5 刷新 → 自动重连或显示已完成结果
4. 模拟 LLM 失败 → error 显示 + 重试按钮
5. 生产：Agent 容器无 Redis 连接

---

## 实施优先级讨论

### 推荐顺序

| 优先级 | 内容 | 工作量 | 风险 | 价值 |
|--------|------|--------|------|------|
| **P0** | Phase 0 紧急修复（C1 + C2 + 死代码） | 0.5d | 低 | 消除最严重的正确性问题 |
| **P1** | Phase 1 核心重构 | 2-3d | 中 | 消除 5 个 review findings，恢复架构正确性 |
| **P2** | Phase 2 前端清理 | 0.5d | 低 | 消除前端代码债务 |

### 关键决策点

1. **Phase 1 的实现方式**：
   - 方案 A: Backend streaming POST 消费 Agent SSE（类似旧 `_stream_asset_report_sse` + buffer）
   - 方案 B: Agent HTTP push bridge（Agent 主动 POST 每个事件到 Backend）
   - **推荐方案 A** — 更接近 DeerFlow 原生，Agent 零修改（只需切回 memory bridge）

2. **Redis 在 Backend 中的角色**：
   - Phase 1 先用 memory buffer（单实例足够）
   - 集群部署时再加 Redis buffer（只有 Backend 访问，Agent 无关）

3. **是否需要 HttpPushStreamBridge**：
   - 如果方案 A 可行（Backend 消费 Agent SSE），则不需要
   - Agent 只需恢复 DeerFlow 原生 memory bridge + sse_consumer
   - **大幅降低重构复杂度**
