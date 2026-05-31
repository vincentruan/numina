---
date: 2026-05-31
topic: agent-internal-mcp-crud
focus: 反向思考 backend 能力 → agent 内置 MCP，约束 ① MCP 启停可控 ② FastAPI 无侵入 ③ 租户严格隔离；验收三方面：架构设计、功能体验、租户隔离
mode: repo-grounded
---

# Ideation: 数鸣 ⇄ Backend 内置 MCP 化 — 反向思考

## Grounding Context

### Constraint vs Background
- **Constraint**（用户指定，违反即淘汰）：① MCP 内置管理启用状态可控；② 现有 FastAPI 无侵入修改；③ 租户严格隔离。
- **Background**：Codebase / Past learnings / External research 三节均为支撑信息。

### Codebase Context
- Numina 是 Python 3.12 + FastAPI uv monorepo：`server/apps/{backend,agent,scheduler_worker}` + `packages/{core,db,domain,security,storage}`。
- 租户边界 = `family_id`。Backend 通过 `Depends(get_current_user)` 注入 `user.family_id`，每个 service 入口 `query.filter(Model.family_id == user.family_id)`。
- Agent 与 Backend 完全 HTTP/SSE 边界：禁跨 app 直 import；agent 通过 `BackendClient` 调 `/api/v1/internal/*`，带 `X-Agent-Token` (HMAC) + `X-Family-Id`。

#### 已存在的 MCP 基础设施 — 必须复用
- `server/apps/backend/app/routers/mcp_internal.py` 暴露 `GET /api/v1/internal/mcp/{family_id}/sse` + `POST /messages`，共享一个 module-level `_transport: SseServerTransport` 单例。
- `server/apps/backend/app/services/mcp_session.py`：`MCPSession.__slots__ = ("_family_id", "_server")`；family_id 在构造时冻结。
- 已注册 5 个**只读**工具：`get_family_overview / get_assets / get_liabilities / get_members / get_recent_alerts`。
- Agent 侧 `services/deerflow_adapter/family_adapter_cache.py` 用 5 元组 key 含 `mcp_hash`。`create_family_adapter(mcp_servers=[...])` 是合法注入点。
- `services/agent_dispatch.py` 调度时 `client.get_enabled_mcp_servers()` → `EffectiveConfigBuilder` → `make_lead_agent()`。
- `BackendClient.get_enabled_mcp_servers()` 返回 family 启用的 MCP server 列表 — **当前无对应 PUT/POST 配置端点**。

#### Backend CRUD 路由（待 MCP 化）
- Assets: `/api/v1/assets`，service `apps/backend/app/services/asset.py`
- Wishes (adult): `/api/v1/wishes`，service `wish.py`
- Child Wishes: `/api/v1/child/wishes`，service `child_wishes.py`
- Liabilities: `/api/v1/liabilities` 含 `PUT /{id}/payment`，service `liability.py`
- Chores（宝贝任务）: `/api/v1/family/chore-templates` + `/api/v1/chores`，service `chores.py`

#### 已知 Pain
- MCP 工具表硬编码、5 个只读、无管理 UI。
- `MCPSession` 与 `_transport` 在 SSE 长连接里寿命 > FastAPI 请求作用域 → 不能 `Depends(get_db)`，必须 per-call `with SessionLocal() as db:`。
- 之前 DeerFlow 的"任何故障 → silent disabled"踩过坑。
- `_get_owner_user(family_id, db)` 在 `mcp_session.py:16-31` 静默选 owner — 是 confused-deputy 漏洞。

### Past Learnings (docs/solutions/)
1. **mcp-chat-adapter-architecture-2026-05-21**：`__slots__` 冻结 family_id；SSE 路径 `if x_family_id != path_family_id: 403`；family_id 必过 `^[A-Za-z0-9_\-]{1,64}$`；工具异常 sanitize；GET/sse + POST/messages 必须共享同一 `_transport` 单例；`family_adapter_cache` 必须 hash mcp_servers 进 key。
2. **deerflow-adapter-stream-security-2026-05-16**：`hmac.compare_digest` 比 token；启动期 hostname allowlist 防 SSRF；新 router 复制现有 auth pattern。
3. **deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12**：`except Exception → feature_disabled = None` 是 anti-pattern；MCP 启用判断失败必须打日志、不得静默禁用。
4. **snowflake-id-json-string-serialization-2026-04-27**：MCP tool 返回值经 LLM 时需走 `SnowflakeBase` BigInt → str；用 `model.model_dump(mode="json")`。
5. **cache-key-granularity-matches-data-scope-2026-04-27**：MCP CRUD 基本不应加 cache；如加，key 必含 `family_id` + 用户级偏好。
6. **backend-module-extraction-workflow-2026-05-14**：`apps/` 消费 `packages/`，反向禁止；SSE/job 必须自己 `SessionLocal()`。
7. **three-state-circuit-breaker-with-cascade-retry-2026-05-20**：错误分类 401/403=permanent_auth（不重试），429/5xx=transient（可级联）；fire-and-forget 副作用不阻塞响应路径。
8. **fastapi-pydantic-validation-error-localization-2026-04-16**：MCP tool 输入校验错误必须走 `_VALIDATION_CODE_MAP` 中文 locale。
9. **redis-fail-fast-strategy**：开关 = on 但服务不可达时必须显式失败，禁止静默回退。
10. **gamified-child-system-architecture-2026-04-17**：Schema 在 `backend/app/schemas/`，每领域一文件；MCP tool schema 走同目录避免漂移。

### External Context
- **fastapi-mcp** (tadata-org)：ASGI-mounted 零路由修改，但无 multi-tenant / tool filter / 启停。
- **FastMCP** (jlowin/PrefectHQ)：mount-INTO ASGI；**已知 bug #1233**：ContextVar 跨请求泄漏。
- **Spring AI MCP**：`addTool / removeTool / notifyToolsListChanged` 是目前最完整的运行期工具切换实现。
- **MCP spec issue #278 + Claude Code #7328**：MCP 协议无原生 per-user/role tool 可见性 — 开放协议缺口。
- **OWASP Agentic Top 10 (2025-12)**：Confused Deputy 列入。Palo Alto Unit 42：5 个 MCP server 时单一受损达 **78.3%** 攻击成功率。
- **Capability-based security (Semgrep 2026)**：task-scoped attenuated tokens 取代 session-token-as-ambient-authority。
- **Truto multi-tenant MCP**：HMAC-scoped server URL + method/tag tool filtering + credential opacity。
- **PostgreSQL RLS / Salesforce virtual private DB**：连接期 `SET tenant_id` 与 MCP "session 期 bind family_id" 同构。

## Topic Axes
- A1. 租户身份冻结路径 — family_id 5 层链路保证不可被 LLM 篡改
- A2. 工具暴露面与粒度 — 哪些 CRUD 暴露、读写分离、粒度
- A3. 启停控制平面 — 开关层级、热更新、fail-fast vs silent
- A4. 服务层调用方式 — HTTP 回环 vs ASGI mount vs 直调 packages.domain
- A5. 写操作风险与审计 — 写前确认、幂等、audit log、prompt-injection 防御

## Ranked Ideas

### 1. Frozen Tenant Pouch + Closure Factory
**Description**: MCP session bootstrap 构造不可变 pouch `(family_id, caller_user_id, role, session_uuid)` HMAC 签名，注入 `MCPSession.__slots__`；工具注册时通过 closure 捕获 pouch — 工具 JSON Schema 不包含 `family_id` 字段。LLM 无法在 args 里 emit family_id（线协议层不存在）。Runtime AST 检查兜底：任何 handler 读 `arguments.get("family_id")` 启动失败。
**Axis**: A1
**Basis**: `direct:` `mcp_session.py:42` 已有 `__slots__ = ("_family_id","_server")`；`mcp_session.py:117` 仅"SECURITY: ignore family_id" 注释。`external:` ARINC 653 partition manifests + Truto HMAC-scoped URLs。
**Rationale**: 把 family_id 篡改从"运行期 reject"升级为"协议层不可表达"；每个未来 write tool 自动继承免疫，复合收益巨大。
**Downsides**: HMAC 密钥轮换流程；启动 AST 检查 +~50ms。
**Confidence**: 92%
**Complexity**: Low
**Status**: Unexplored

### 2. Caller-Bound Principal + Per-Member Tool Set
**Description**: 扩展 `MCPSession.__slots__` 为 `(family_id, caller_user_id, caller_role, server)`。删除 `_get_owner_user(family_id, db)` 静默选 owner 的逻辑——service 调用以**真实发起者**为 principal。`list_tools()` 按 `caller_role` 返回不同工具集（child → `complete_chore`/`view_my_wishes`；parent → `approve_chore`/`create_wish`；owner → destructive ops）。
**Axis**: A1 + A3
**Basis**: `direct:` `mcp_session.py:16-31` 显示 `_get_owner_user` 是真实存在的 confused-deputy 漏洞——child chat 经 agent 触发会被拔升为 owner-privileged。`external:` MCP spec issue #278（无原生 per-user tool visibility）+ OWASP Agentic Top 10 (2025-12) Confused Deputy。
**Rationale**: 这是已存在的 critical 漏洞，不是预防性设计；每加一个 write tool 都在放大它。同时优雅地绕过 MCP 协议缺口。
**Downsides**: 修改 SSE 握手提取 `caller_user_id`；前端跨 member 切换时需重建会话。
**Confidence**: 95%
**Complexity**: Low-Medium
**Status**: Unexplored

### 3. Tenancy-Proof Middleware on All `*_id` Arguments
**Description**: 装饰器 `@tenancy_proof` 在每个 MCP 写工具运行前扫描 args 中所有 `*_id` 键，逐个去 DB 查 `family_id`，任一不等于 `self._family_id` 立即 raise + audit。失败 = `permanent_auth`（不重试）。覆盖 `asset_id`/`liability_id`/`wish_id`/`child_id`/`chore_id`/`payment_id` 全部跨租户引用。
**Axis**: A1
**Basis**: `direct:` 当前依赖 `query.filter(Model.family_id == user.family_id)` 一个 join 兜底——一旦未来某 service 漏写过滤即失守。`reasoned:` 写工具扩展到 20+ 时 per-tool 人审 tenancy 不可持续；中间件让它结构化、可测试、可被 ruff 检查。
**Rationale**: S1 防 family_id 篡改；S3 防"用合法 family_id 但引用别家 entity_id"——两者关闭不同攻击向量，互补不重复。
**Downsides**: 每写多 1-N 次 SELECT；可 `@tenancy_proof(ids=("asset_id",))` 显式声明降本。
**Confidence**: 88%
**Complexity**: Low
**Status**: Unexplored

### 4. Intent-Level Verb Tools (Pharmacy Formulary)
**Description**: 不暴露 generic CRUD `update_asset(asset_id, **fields)`。改成窄 verb：`correct_asset_amount(asset_id, new_amount, reason)`、`rename_asset(asset_id, new_name)`、`archive_asset(asset_id)`、`record_liability_payment(liability_id, amount, date)`、`approve_chore_completion(chore_id)`、`reject_chore(chore_id, reason)`。每个 verb 输入域窄、专属 audit、专属 confirmation 策略。危险组合（"改金额同时改 family_id"）作为 tool 不存在，无法被调用。
**Axis**: A2
**Basis**: `external:` 医院 pharmacy formulary 通过移除危险组合（而非加警告）消除处方错配；Unit 42：5 个 MCP server 时单一受损达 78.3% tool-chaining 攻击成功率——窄 surface 是最有效缓解。`reasoned:` LLM 在 multi-field consistency 上差，在选 single-purpose tool 上好。
**Rationale**: Audit surface 从 "every field of every CRUD" 收敛到有限 verb；每个 verb 自带语义化 prompt template、确认策略、审计 schema；LLM 工具选择准确率显著上升。
**Downsides**: Verb 数量 ~25-30 vs 4 generic CRUD——需 capability manifest 集中管理避免 schema 漂移；新需求需新增 verb。
**Confidence**: 85%
**Complexity**: Medium
**Status**: Unexplored

### 5. Three-Lane Toggle — Green / Yellow / Red
**Description**: 替换 boolean 启用为三态，存于 `family_ai_config.mcp_lane`：
- **Green**: 读 + 写工具全部 register
- **Yellow**: 仅读工具 register；写工具走 `tools/list` 但调用返回 `{"error":"yellow_lane","retryable":false}`（家长年终对账时拉到 yellow）
- **Red**: 零工具 register；agent 收到明确 "MCP unavailable"（绝不静默回退）

通过 Redis pub/sub + `tools/list_changed` 通知热更新；MCP 配置 = on 但不可达时 fail-fast。
**Axis**: A3
**Basis**: `direct:` `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md` 明确教训"silent disabled 是 anti-pattern"；`docs/solutions/best-practices/redis-fail-fast-strategy.md` 同等强度。`external:` Toyota andon cord；Spring AI `addTool/removeTool/notifyToolsListChanged`。
**Rationale**: 直接对接约束 ① "MCP 内置管理启用状态可控"；yellow lane 是杀手特性——敏感期保留 read-only AI 比 all-or-nothing 实用；fail-fast 防 DeerFlow 那次踩坑复刻。
**Downsides**: 三态比布尔多一个产品决策；前端需要 lane 状态 indicator + family settings UI。
**Confidence**: 90%
**Complexity**: Low-Medium
**Status**: Unexplored

### 6. Two-Phase Write Confirmation — SWIFT-Style Settlement
**Description**: 写工具永不直接 mutate。Phase 1 返回 `{pending_op_id, diff_preview, expires_at}`（60s TTL，family-scoped，single-use）。前端在 chat 流中插入 confirm card："数鸣想新增资产'工商银行存款'¥50000，[确认][取消]"。Phase 2 只接 `confirm_write(pending_op_id)`，无可编辑 payload — LLM 无法在 preview 与 apply 之间篡改字段。Pending ops 存 Redis 队列，可批量审批。
**Axis**: A5
**Basis**: `external:` SWIFT MT103 inter-bank settlement 解耦消息生成与最终 commit；OWASP Agentic Top 10 列 confirmation-before-execute 为 confused-deputy 推荐缓解；Unit 42 78.3% tool-chaining 在没有 auto-commit 时失效。`reasoned:` 防御在模型完全 compromise 时仍成立——第二次调用 zero degrees of freedom。
**Rationale**: 单一最有效的 prompt-injection 写防御；同时给 audit + 自然 undo + 批量审查产品功能。家庭财务 blast radius 高。
**Downsides**: 每写多 1 往返 + 1 用户操作；可对低风险（"加 50 元杂货"）开 per-family auto-confirm 阈值。
**Confidence**: 93%
**Complexity**: Medium
**Status**: Unexplored

### 7. Idempotency Key + Domain-Event Audit Tap
**Description**: 每个写工具必带 `idempotency_key`（UUID 由 orchestrator 生成、不由 LLM）。Backend 缓存 `(family_id, idempotency_key, result_hash)` 24h，重试返回缓存。每个 mutation fire-and-forget emit 结构化事件到现有 `packages/domain/audit` channel：`{family_id, mcp_session_id, tool_name, llm_message_id, request_hash, before, after, ts}`。Grafana panel filter `source=mcp` 即得 LLM action 全可观测性。
**Axis**: A5
**Basis**: `direct:` `services/audit_logger.py` 已存在；`packages/domain/{audit,exchange_rate,snapshot,notification}` 已抽出，audit 是稳定 channel。最近 commit `fa21fafe (persist session metadata)` 表明 `llm_message_id` 已贯穿 stream。`reasoned:` DeerFlow + LangGraph 都会在 transient 失败时重试 tool 调用，无 idempotency = 重复写。
**Rationale**: 复用 audit 通道是力倍增——任何未来读 audit 的运维工具自动获得 MCP 可见性。Idempotency 是写工具上线前的 foundation。
**Downsides**: Idempotency 缓存对单家庭体量极小；audit 事件 schema 从一开始需版本化。
**Confidence**: 91%
**Complexity**: Low
**Status**: Unexplored

## 三方面验收映射（用户指定）

| 验收维度 | 主承担 idea | 辅助机制 |
|---|---|---|
| **架构设计** | #1 (closure pattern), #5 (lane state machine), #7 (audit reuse) | 复用 `MCPSession.__slots__` / `family_adapter_cache` / `packages.domain.audit`，最小侵入 |
| **功能体验** | #4 (verb 语义清晰), #5 (yellow lane 灵活运营), #6 (确认卡 UX) | 家长可控可信、敏感期可降级、单点确认 |
| **租户隔离** | #1 (协议层不可表达 family_id 篡改) + #2 (caller-bound 修 confused deputy) + #3 (`*_id` 中间件) | 三层独立防御，闭合不同攻击向量 |

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Attenuated Capability Token (替换 ambient X-Agent-Token JWT 化) | too expensive for single-family self-hosted scale；#1+#2+#3 三层已构成完整租户隔离防御 |
| 2 | Postgres RLS Defense-in-Depth | too expensive — 需在每个 tenant 表加 policy、改 migrations、改 fixtures、与 SQLAlchemy ORM 协调；当前规模下 service-layer filter + #3 middleware 充分；可作为 cloud-multitenant 阶段升级 |
| 3 | Capability Manifest as SSOT (独立 idea) | 合并入 #4 (Verb Tools) 与 #5 (Toggle) 的实现描述——manifest 是支撑机制而非独立洞见 |
| 4 | Per-Turn Intent-Ranked Dynamic Tool Exposure | too expensive relative to value——单家庭工具数量不会大到必须裁剪；#2 (per-member registry) 已覆盖 role-based 过滤 |
| 5 | ASGI In-Process Mount via ASGITransport | not grounded in current deployment — agent 与 backend 是独立 docker container（docker-compose），无法在 agent 进程内 mount backend ASGI app；现有 SSE+HTTP channel 已 work |
| 6 | Domain Package Extraction for Write Logic | not grounded — MCPSession 在 `apps/backend` 内部，import `apps.backend.services.*` 合法；agent 不直接 import backend，无 extraction 必要；future scheduler_worker 复用是 hypothetical |
| 7 | Anomaly-Triggered Re-Consent (Pit Boss) | premature for current scale——单家庭写次数不足以训练 z-score baseline；#6 (Two-Phase Confirm) 已在 commit 路径加 human gate；叠加 anomaly detection 是 over-engineering |
| 8 | Append-Only Event Log (every read is a write) | duplicates a stronger idea (#7 已把 writes 写入 audit channel)；reads 频率高时显著负担 |
| 9 | Read/Write Split — Two MCP Servers/Sessions | 价值被 #5 (Three-Lane Toggle) + #4 (Verb Tools) 同时覆盖：yellow lane 已实现 read-only 隔离，verb 设计已让 write 工具语义独立 |
| 10 | Pydantic→MCP Schema Bridge | 高 leverage 但非约束-critical——作为 #4 实现的强烈推荐机制保留在描述里，但不独立列为 survivor |
| 11 | Slots-Freeze Lint Probe（独立 idea） | 合并入 #1 描述作为兜底机制 |
| 12 | HMAC-Scoped MCP URL Per Family | 部分价值合并入 #1（pouch HMAC 签名）；URL-issuance 层面变化与"无侵入"约束有摩擦 |
| 13 | Single-Family Static Bake | 性质上是 deployment-mode 的 feature flag，可作为 #1 的部署优化项；不是 ideation 级别的洞见 |
| 14 | Family Adapter Cache as Sole Tenant Boundary | 与 #1 (closure factory) 重叠；cache 本身已是 leverage 但不构成隔离机制 |
| - | axis: A4 (服务层调用方式) | deliberate gap — 现有 SSE+HTTP channel + MCPSession 内部直 import services 已达成"无侵入"目标；A4 候选都没有 grounded 在当前部署架构 |
