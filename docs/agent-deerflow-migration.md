# Agent DeerFlow 迁移说明

本文档记录 `numina/agent/` 从基础 LLM 服务升级为 DeerFlow harness 架构的迁移过程、设计决策和边界约定。

## 迁移目标

将 `agent/` 升级为具备以下能力的内部智能执行层：

- 规划与子任务拆解（DeerFlow planning）
- 自定义领域 skills（家庭财务场景）
- 统一结构化输出契约
- PII 脱敏保护层
- 策略控制与审计
- 新旧路径并存与灰度切换

## 架构边界

### 保持不变

- `Vue → Backend → Agent` 的主调用链
- Backend 对 Agent 的受认证内部 HTTP 接口（`X-Agent-Token` + `X-Family-Id`）
- Frontend 和 Backend 不感知 DeerFlow 内部结构

### 新增

| 组件 | 路径 | 职责 |
|------|------|------|
| `Orchestrator` | `services/orchestrator.py` | 统一调度入口，串联所有中间件 |
| `PIIRedactor` | `services/pii_redactor.py` | 结构化 + 自由文本双路径脱敏 |
| `PolicyGuard` | `services/policy_guard.py` | 能力开关、管理员限制 |
| `DeerFlowAdapter` | `services/deerflow_adapter/` | DeerFlow harness 封装，有界并发 |
| `FallbackEngine` | `services/fallback_engine.py` | Legacy 路径兜底，永不抛出 |
| `OutputMapper` | `services/output_mapper.py` | 统一输出映射为 AgentResponse |
| `AuditLogger` | `services/audit_logger.py` | 结构化审计日志 |

## DeerFlow 集成方式

DeerFlow 以 vendor copy 方式集成，不作为 git submodule：

```
agent/vendor/deerflow-harness/   ← 从参考工程复制的 harness 代码
agent/.vendor-manifest.json      ← 记录来源 commit SHA
```

更新 DeerFlow 版本时，运行：

```bash
./scripts/vendor-deerflow.sh
```

## 配置分层

```
deerflow_config/
├── base/config.yaml    ← 基础配置（checkpointer、memory、sandbox）
├── dev/config.yaml     ← 开发环境 overlay
└── prod/config.yaml    ← 生产环境 overlay（更严格的内存限制和沙盒）
```

生产环境关键配置：
- `sandbox.allow_host_bash: false`
- `memory.allowed_fact_categories`：仅允许行为偏好类低敏信息
- `memory.max_facts: 50`

## 灰度切换

通过 `USE_DEERFLOW` 环境变量控制：

```
USE_DEERFLOW=false  → 全走 legacy 路径（默认）
USE_DEERFLOW=true   → 走 DeerFlow 路径，失败自动降级到 legacy
```

## 数据流

```
Request
  │
  ├─ [1] Token 验证（路由层）
  ├─ [2] PolicyGuard.check()
  ├─ [3] BackendClient.fetch_context()
  ├─ [4] PIIRedactor.redact()
  ├─ [5a] DeerFlowAdapter.dispatch()  ← USE_DEERFLOW=true
  │   └─ [5b] FallbackEngine.run()   ← DeerFlow 失败时
  ├─ [5c] FallbackEngine.run()       ← USE_DEERFLOW=false
  ├─ [6] OutputMapper → AgentResponse
  └─ [7] AuditLogger.log_call()
```

## 安全约束

以下事项由 `backend/` 或 `agent/` 业务层管理，不下放给 LLM：

- 用户身份与权限
- 家庭管理员开关
- 数据脱敏
- 原始资产/负债事实
- 审计日志

## 已知限制

- `suggest` 和 `allocation` 端点的请求体字段通过 `free_text` JSON 传入 orchestrator，legacy 路径暂不解析这些字段（返回通用提示）
- DeerFlow 长期记忆仅保存行为偏好，不跨家庭共享
- 并发限制：`ThreadPoolExecutor(max_workers=4)` + `asyncio.Semaphore(4)`
