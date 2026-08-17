---
date: 2026-08-15
module: architecture
problem_type: architectural-decision
tags: [streambridge, gateway, worker, deerflow, architecture]
applies_when: 重构 AI 任务韧性系统的架构，将 Gateway 职责从 Agent 移到 Backend
---

# Architecture Decision: Gateway/Worker 职责分离

## Problem

当前 AI 任务韧性系统（U1-U8）的实现违反了职责分离原则，将 Gateway 职责（StreamBridge、RunManager、gc.py）错误地放在了 Agent 模块，而不是 Backend 模块。

### 核心需求

用户中途离开页面或切换页面时，AI 任务应该继续运行。用户返回页面时，能看到最新状态。这需要 Backend 作为中间层，解耦前端影响。

### 当前架构（错误实现）

```
Backend
  └─ bridge_consumer (订阅 Redis) ❌ 职责不清
  
Agent
  ├─ StreamBridge (发布事件) ❌ 应该在 Backend
  ├─ RunManager ❌ 应该在 Backend
  ├─ gc.py (drain/reconcile) ❌ 应该在 Backend
  ├─ sse_gateway.py ❌ 应该在 Backend
  └─ shutdown_state.py ✅ 可以（各自管理）
```

### 问题

1. **Agent 模块被过度修改**：修改了 `stream_bridge/`、`gc.py`、`lifespan.py`、`sse_gateway.py` 等，违反了"Agent 聚焦 DeerFlow agent 能力"的原则。

2. **职责混乱**：
   - StreamBridge 应该在 Gateway（Backend）层，用于解耦前端和 Worker
   - RunManager 应该在 Gateway 层，管理任务生命周期
   - gc.py（drain/reconcile）应该在 Gateway 层
   - Agent 应该只负责执行 AI 任务，发布事件到 Bridge

3. **不符合 DeerFlow 架构**：DeerFlow 的 Gateway + Worker 架构中，Gateway 拥有 StreamBridge 和 RunManager，Worker 只负责执行任务。

## DeerFlow 的正确架构

```
Gateway (Backend)
  ├─ StreamBridge (发布和订阅)
  ├─ RunManager (任务生命周期)
  ├─ sse_consumer (SSE 转发)
  ├─ gc.py (drain/reconcile)
  └─ HTTP → Worker

Worker (Agent)
  ├─ 执行 AI 任务
  ├─ 调用 bridge.publish() 发布事件
  └─ 不关心 StreamBridge 实现细节
```

### DeerFlow 参考代码

- `deerflow/runtime/stream_bridge/` - StreamBridge 抽象（内存/Redis）
- `deerflow/runtime/runs/manager.py` - RunManager（任务生命周期）
- `deerflow/app/gateway/services.py` - sse_consumer（SSE 转发）
- `deerflow/app/gateway/routers/thread_runs.py` - Gateway HTTP 端点

## 正确的重构方向

### Backend 应该拥有

1. **StreamBridge**：内存或 Redis 实现，用于解耦前端和 Agent
2. **RunManager**：任务生命周期管理（创建、运行、完成、失败）
3. **sse_consumer**：SSE 转发逻辑，处理 Last-Event-ID、StreamGap
4. **gc.py**：drain（优雅关停）、reconcile（孤儿恢复）
5. **shutdown_state**：关停状态管理

### Agent 应该保持

1. **纯粹的 DeerFlow agent 能力**：执行 AI 任务
2. **调用 `bridge.publish()` 发布事件**：但不关心 Bridge 实现细节
3. **不修改 Agent 的 StreamBridge、RunManager、gc.py 等**：这些应该在 Backend

### 重构步骤

1. **移动 `stream_bridge/` 从 Agent 到 Backend**
   - `server/apps/agent/services/runtime/stream_bridge/` → `server/apps/backend/app/services/stream_bridge/`
   - 更新所有导入路径

2. **移动 RunManager 初始化到 Backend**
   - Backend 的 `lifespan.py` 初始化 RunManager 和 StreamBridge
   - Agent 不再初始化这些组件

3. **移动 gc.py 逻辑到 Backend**
   - `server/apps/agent/services/runtime/gc.py` → `server/apps/backend/app/services/task_lifecycle.py`
   - drain/reconcile 逻辑在 Backend 执行

4. **Backend 直接调用 Agent 的任务执行**
   - Backend 通过 HTTP 调用 Agent 的任务执行端点
   - Agent 只负责执行 AI 任务，发布事件到 Bridge

5. **Agent 简化**
   - Agent 只暴露任务执行端点（`/api/ai/tasks/execute`）
   - Agent 调用 `bridge.publish()` 发布事件
   - Agent 不关心 StreamBridge、RunManager、gc.py

## 影响范围

### 当前实现（已提交）

- ✅ 所有测试通过（后端 1551 passed，前端 1165 passed）
- ✅ 功能完整（U1-U8 全部实现）
- ⚠️ 架构不完美（Agent 模块被过度修改）

### 重构后

- ✅ 符合 DeerFlow 架构
- ✅ Agent 聚焦 agent 能力
- ✅ Backend 承担 Gateway 职责
- ⚠️ 需要大量重构工作
- ⚠️ 需要更新测试

## 决策

**当前选择**：保持当前实现，记录架构问题，后续单独重构。

**理由**：
1. 当前实现可以工作，测试全部通过
2. 架构重构是大改动，需要仔细设计和测试
3. 可以先发布当前版本，后续再重构
4. 记录架构决策，为未来重构留出空间

**未来重构计划**：
- 单独的重构任务（建议命名为 `refactor/gateway-worker-separation`）
- 详细的重构计划文档
- 分阶段重构（先移动 StreamBridge，再移动 RunManager，最后移动 gc.py）
- 每个阶段都有完整的测试覆盖

## 经验教训

1. **参考 DeerFlow 架构时，要理解职责分离**：Gateway 和 Worker 的职责要清晰
2. **Agent 应该聚焦 agent 能力**：不要将基础设施（StreamBridge、RunManager）放在 Agent 模块
3. **架构决策要记录**：即使当前实现不完美，也要记录问题和未来计划
4. **先发布，后重构**：如果当前实现可以工作，可以先发布，后续再重构

## 相关文件

- `server/apps/agent/services/runtime/stream_bridge/` - 当前在 Agent（应该移到 Backend）
- `server/apps/agent/services/runtime/gc.py` - 当前在 Agent（应该移到 Backend）
- `server/apps/agent/services/runtime/lifespan.py` - 当前在 Agent（应该移到 Backend）
- `server/apps/backend/app/services/bridge_consumer.py` - 当前在 Backend（正确）

## DeerFlow 参考

- `deerflow/runtime/stream_bridge/base.py` - StreamBridge 抽象
- `deerflow/runtime/stream_bridge/redis.py` - Redis 实现
- `deerflow/runtime/stream_bridge/memory.py` - 内存实现
- `deerflow/runtime/runs/manager.py` - RunManager
- `deerflow/app/gateway/services.py` - sse_consumer
- `deerflow/app/gateway/routers/thread_runs.py` - Gateway HTTP 端点
