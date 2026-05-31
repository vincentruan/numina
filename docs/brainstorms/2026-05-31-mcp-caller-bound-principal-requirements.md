---
date: 2026-05-31
topic: mcp-caller-bound-principal-and-per-member-tool-set
parent_ideation: docs/ideation/2026-05-31-agent-internal-mcp-crud-ideation.md (idea #2)
status: draft — assumptions explicit, awaiting confirmation before /ce-plan
constraints_from_parent:
  - MCP 内置管理启用状态可控
  - 现有 FastAPI 无侵入修改
  - 租户严格隔离
acceptance_axes_from_parent: [架构设计, 功能体验, 租户隔离]
---

# Requirements: Caller-Bound Principal + Per-Member Tool Set

> 来源：`docs/ideation/2026-05-31-agent-internal-mcp-crud-ideation.md` 的 Ranked Idea #2。本文档把它从一句话洞见落到可被 `/ce-plan` 直接消费的 deliverable 边界。

## 1. Problem Frame

### 1.1 Today's behavior（已 verified against code）

- `server/apps/backend/app/services/mcp_session.py:16-31` 的 `_get_owner_user(family_id, db)` 在 MCP 工具调用时**静默选取 family 的 owner** 作为 service 层 principal。
- 调用链：child / parent / owner 任意成员发起 chat → `agent_dispatch.stream_agent_dispatch(family_id, user_id, ...)` → backend SSE handshake (`mcp_internal.py:63`) → `MCPSession(family_id=family_id)` → 工具调用 → `_get_owner_user` 返回 owner → service 拿 owner 身份执行查询。
- `MCPSession.__slots__ = ("_family_id", "_server")`：family_id 是冻结的，**caller 身份完全丢失**。
- `mcp_session.py:117` 的 `# SECURITY: ignore family_id in arguments` 注释只防住一半 — family_id 不可篡改，但 caller 已经被静默拔到 owner。

### 1.2 The two distinct attack/error vectors

| 向量 | 当前防御 | 现状 |
|---|---|---|
| LLM 在 tool args 里 emit `family_id` 篡改租户 | `_family_id` slot freeze + service 层 `query.filter(family_id=...)` | 已闭合 |
| LLM 触发 child / parent 不该有的能力（destructive ops、跨成员数据） | **无** — service 拿到的永远是 owner | **开放漏洞** |

第二行就是 #2 要关闭的洞 — confused-deputy in agentic terms。

### 1.3 Why this is observable, not theoretical

- 子端（`frontend/apps/child`）已经存在并独立 deploy。当 child 端将来接入 agent chat（adult agent 路径或 child agent 路径），任何 MCP 工具调用都会被 `_get_owner_user` 提权到 owner 视角 — 这不是「LLM 越权」的假设，是路径上的确定行为。
- 现有 5 个**只读** tool 让爆面有限（child 看 family overview 不会立即引发争议），但 ideation 的目标是把 backend CRUD 全面 MCP 化，写工具一旦上线，confused-deputy 就从「信息泄漏」升级为「未授权写入」。

### 1.4 What we're NOT solving here

- `family_id` 在 args 里被 LLM 篡改 — 这是 ideation #1 的目标，已被 `__slots__` 闭合。
- 跨 family 的 entity_id 引用（asset_id 属于别家）— 这是 ideation #3 `@tenancy_proof` 的目标。
- Generic CRUD vs intent-level verb tools — 这是 ideation #4 的目标。
- Write tool 的两阶段确认 — ideation #6。
- Audit reuse — ideation #7。

#2 只关闭一个洞：**caller 身份在 MCP session 里不应被丢失或静默替换**。

---

## 2. Goal

让 backend MCP 工具调用以**真实 caller 的身份**执行 service 层授权，且 caller 视角的工具集合在协议层（`tools/list`）就被正确裁剪 — 而不是依赖 service 层在每次调用时检查角色。

> 一句话：从「家里所有 AI 调用都以 owner 身份执行」改成「AI 替谁说话，就用谁的身份执行」。

---

## 3. Scope（明确的 deliverable 边界）

### 3.1 In scope

S1. **caller_user_id 端到端贯通**
- `agent_dispatch.stream_agent_dispatch` 已持有的 `user_id`，需要传到 backend SSE handshake header `X-Caller-User-Id`。
- `BackendClient.get_enabled_mcp_servers()` 调用路径不受影响（这是 family 级配置查询，与 caller 无关）。
- backend `mcp_internal.mcp_sse` 提取 header → `MCPSession(family_id=..., caller_user_id=...)`。

S2. **`MCPSession.__slots__` 扩展为 `("_family_id", "_caller_user_id", "_caller_role", "_server")`**
- caller_user_id 在构造时冻结（与 family_id 同模式）。
- caller_role 在构造时一次查询 `User.role` 缓存到 slot，避免 per-call 再查 DB。
- 不引入任何 ContextVar / module-level mutable state（DeerFlow harness #1233 的踩坑前车之鉴）。

S3. **`_get_owner_user` 删除，替换为 `_get_caller_user`**
- service 调用以**真实 caller 的 User 行**为 principal，而非 owner。
- caller 身份失败（不属于该 family / inactive / 已删除）→ 整个 SSE 握手返回 403，**绝不静默 fallback** 到 owner（与 deerflow-harness silent fallback 教训对齐）。

S4. **`list_tools()` 按 caller_role 静态裁剪**
- 引入 tool metadata 表：`{tool_name → {allowed_roles: set[Literal["owner","member","child"]], requires_write: bool}}`，集中管理避免漂移（参考 [[gamified-child-system-architecture]] 的 SSOT 教训）。
- `list_tools()` 只返回 `caller_role in allowed_roles` 的工具。
- `call_tool(name, ...)` 入口再校验一次 caller_role：协议裁剪是 hint，server 端二次校验是 enforcement（参考 backend 现有 `require_owner` / `require_adult` 模式）。
- 二次校验失败 → 返回 `{"error": "permission_denied"}` + audit log 记录 attempted_tool & caller_role。

S5. **审计字段补齐**
- `audit_logger.AuditEntry` 已有 `user_id` 字段；MCP 路径必须填，不能再用 `family_id` 当 stand-in。
- backend 侧 `mcp_session.py` 的 `logger.info("[mcp_session] family=%s tool=%s args=%s ok", ...)` 增加 `caller_user_id=` 与 `caller_role=`。
- `permission_denied` 事件 `level=WARNING`（区别于 success 的 INFO），且不计入 transient 错误重试。

### 3.2 Out of scope（以下决策由其他 idea / 后续 brainstorm 承担）

- **per-member 自定义 tool override UI**：「owner 在设置里手动开关 X 成员能看见哪些工具」是另一个产品决策。本 #2 只做基于 `User.role` 的**静态**裁剪表，**不引入 `family_member_tool_grants` 数据库表**。需要时再单独 brainstorm。
- **child role 在 #2 首期是否暴露 MCP**：见 §5 Assumption A3，默认走 policy_guard 上游拦截，不在本 deliverable。
- **destructive write tools**：本 #2 不新增任何写工具。允许 `requires_write=True` 在元数据表里保留，但首期注册的工具都是 `requires_write=False`（5 个现存只读工具）。写工具的 admission 由 ideation #4 + #6 共同决定。
- **与 ideation #1（HMAC pouch）合并实现**：#1 提议把 `(family_id, caller_user_id, role, session_uuid)` 整体 HMAC 签名以防协议层伪造。本 #2 描述按「server 端冻结」实现即可（agent ↔ backend 已有 `X-Agent-Token` 共享密钥 + nginx 私网，威胁模型不要求额外签名层）。HMAC pouch 作为后续 hardening 的可选叠加。

---

## 4. Acceptance Criteria

### 4.1 Architecture（架构设计）

- [ ] `MCPSession.__slots__` 包含且仅包含 `("_family_id", "_caller_user_id", "_caller_role", "_server")`。无任何工具注册路径会读 `arguments` 里的 `family_id` / `user_id` / `role`。
- [ ] `_get_owner_user` 在整个 `server/` 下被删除（grep 验证 — 当前命中 3 处：`apps/backend/app/services/mcp_session.py`、`tests/backend/unit/test_mcp_session.py`、`tests/backend/test_mcp_tenant_isolation.py`，全部需要清掉）。`_get_caller_user(family_id, caller_user_id, db)` 是唯一入口，且强校验 `user.family_id == self._family_id and user.is_active`。
- [ ] tool registry 集中在一个文件（建议 `apps/backend/app/services/mcp_tool_registry.py`），每个 tool 必须声明 `allowed_roles`，缺省即注册失败（启动时 fail-fast）。
- [ ] agent → backend SSE handshake 失败时（caller 不存在 / inactive / 跨 family）返回 403 + agent 侧 `audit_logger` 记录 `error_type=PermanentAuth`，**禁止**回退到 owner 身份。

### 4.2 Tenant isolation（租户隔离）

- [ ] 单元测试矩阵：`(caller_role ∈ {owner, member}) × (tool ∈ {get_family_overview, get_assets, get_liabilities, get_members, get_recent_alerts})` 全覆盖；每个 cell 显式声明 expected `allowed | denied`。
- [ ] 注入测试：构造一个属于 family A 的 caller_user_id，但 SSE handshake URL 是 `/internal/mcp/{family_B}/sse` → 必须 403。
- [ ] 注入测试：构造一个 `is_active=False` 的 user → 必须 403。
- [ ] 注入测试：LLM 在 tool args 里 emit `caller_user_id`、`role`、`as_owner=true` 等字段 → 工具行为完全等价于不传（slot 是唯一真值源）。
- [ ] 不再有任何 child caller 经 MCP 路径意外读到家庭财务明细的可能（首期通过 §5 A3 实现：child 不进 MCP）。

### 4.3 Functional / UX（功能体验）

- [ ] 现有 owner 用户的所有 chat 行为表现不变（5 个只读工具结果不变）。
- [ ] member 用户调 chat：能查 family overview / assets / liabilities / members / alerts（首期所有读工具对 owner+member 同等可见）。
- [ ] 每个 family member 单独建立一条 SSE，`family_adapter_cache` 命中率与单 owner 时相比，per-family 增加最多 N 个 entry（N = 该 family 的活跃成员数）。可观测：`get_cache_stats()` 输出。
- [ ] permission_denied 路径的 LLM 错误响应是结构化 `{"error":"permission_denied","retryable":false}`，让 LLM 知道「我不该再试」（与 redis-fail-fast / three-state circuit breaker 同语义）。

### 4.4 Non-regressions

- [ ] `MCPSession` 的 SSE 寿命 > 请求作用域的约束保持（每次 tool call 仍 `with SessionLocal() as db:`）。
- [ ] `redirect_slashes=False` + 路由前缀风格不变。
- [ ] `__slots__` 增加字段不引入 pickle / deepcopy 路径（既有代码也没用过）。
- [ ] `family_adapter_cache` key 是否需要新增 caller 维度由 §5 A1 决定 — 本验收要求是「是 or 否」的决策被显式记录，不留 ambiguous。

---

## 5. Assumptions（**未确认，请 review；任一改动会改变 §3/§4 形状**）

### A1. Caller 绑定层级 = SSE 握手期固定 ✱

- **What**：agent 在 SSE handshake 阶段通过 `X-Caller-User-Id` header 把 caller 传给 backend；`MCPSession` 在构造时冻结。一个 SSE 连接 = 一个 caller。同 family 的 owner 与 member 各自持有独立 SSE。
- **Why**：与 `__slots__` 冻结 family_id 的现有模式同构；`agent_dispatch.py:200` 入参已带 `user_id`，零结构性改动；caller 不进 MCP 协议层意味着 LLM 协议消息里压根不存在 `caller_user_id` 字段，符合 ideation #1 的「协议层不可表达 = 不可篡改」原则。
- **Cost**：`family_adapter_cache` 的 5-tuple key 需要变 6-tuple `(family_id, caller_user_id, config_id, subagent, plan, mcp_hash)`。100-cap 的 LRU 实际容量按 family × member 折算（典型 4 口之家 = 25 family）。
- **Alternative rejected**：「per-call 在 messages 通道带 caller」会把 caller 暴露在 LLM 可见线协议上，需要额外 HMAC 防伪造，不值得。

### A2. #2 scope 形状 = B（caller-as-principal + per-role tool set 静态裁剪）

- **What**：删除 `_get_owner_user` + `list_tools()` 按 role 裁剪 + `call_tool` 二次校验。**不**引入 owner 可手动 override 单个成员可见工具的 UI。
- **Why**：A 单独做（仅删 `_get_owner_user`）只关闭 confused-deputy，不能兑现 ideation #2 描述里的「优雅绕过 MCP spec issue #278（无 native per-user tool visibility）」产品价值；C（override UI）是独立产品决策，blast radius 大、需要前端 settings 页 + DB schema，与 #2 的「服务端隔离防御」性质不同，应单独 brainstorm。
- **Cost**：tool registry 元数据表是新增 SSOT，需要保持与 list_tools 实现同步（lint check 可加）。

### A3. child role 不在 #2 首期暴露 MCP

- **What**：child 用户即便登录到 chat 入口，也在 `policy_guard.check()` 上游被拦下（capability `agent` / `chat` 走 `admin_only_capabilities` 或类似机制）。MCP `list_tools()` 在 caller_role=="child" 时**直接 raise** 而非返回空表 — 这是 fail-fast 的具体落点。
- **Why**：(1) child 端有独立 frontend `frontend/apps/child`，与成人 chat 是不同入口，MCP 接入路径未启动；(2) child 经 MCP 看到家庭财务明细的隐私边界需要单独产品决策（脱敏概览 vs 完全不可见 vs 限定字段），不该被 silently 绑进本 #2；(3) 直接 raise 比返回空 tools 列表更安全 — 空列表会让 LLM 用纯先验回答，行为不可预测。
- **Cost**：未来 child 接入 MCP 是必须新开 brainstorm 的工作（child-side privacy 决策），不是「在表里加一行」就行。
- **Risk if wrong**：如果产品方向是「child 也要能问数鸣家庭概况」，本假设让 #2 的 deliverable 不能直接服务 child 端，需要补一个 child-side requirements doc。

### A4. 写工具不在 #2 首期上线

- **What**：tool registry 的 `requires_write` 字段保留作为元数据，但首期注册的所有工具 `requires_write=False`（5 个现有只读工具）。
- **Why**：写工具引入会立刻把 #2 的复杂度耦合到 ideation #4（verb tools）+ #6（two-phase confirm）+ #7（idempotency/audit）— 任何一个独立 brainstorm 没收敛，写工具就不该上。本 #2 只把「caller 身份正确」这件事做对。
- **Cost**：member 角色「能写但只对自己」的产品价值要等 #4/#6 完成才可兑现。

### A5. 不并入 ideation #1 的 HMAC pouch

- **What**：caller_user_id 走 SSE header 不签名，依赖 `X-Agent-Token` 共享密钥 + 私网部署的现有信任基础。
- **Why**：单家庭 self-hosted 部署模式下 agent ↔ backend 同 docker-compose 网络；HMAC pouch 是 cloud-multitenant 阶段的 hardening。本 #2 优先解决「正确性」，而非「在威胁模型外的额外签名层」。
- **Risk if wrong**：若部署形态变成 cloud-multitenant，需要回头给 SSE header 加签名（`X-Caller-User-Id` + nonce + timestamp HMAC，与现有 `X-Agent-Token` 同密钥）。结构变更小，可后续叠加。

---

## 6. Open Questions（写文档过程中浮现的，等 review 决策）

| # | Question | Why it matters | Default if not answered |
|---|----------|----------------|-------------------------|
| Q1 | `family_adapter_cache` key 是否需要新增 caller 维度？ | DeerFlow client 是否对 caller 敏感取决于 `mcp_servers` 配置是否含 caller — 本 #2 不改 mcp_servers 配置内容，所以**理论上不需要**。但 SSE 是 backend 侧建立的，`get_enabled_mcp_servers` 返回的是 family 级 server URL（`/internal/mcp/{family_id}/sse`），URL 本身不含 caller。**默认不改 cache key**。需 review 是否同意。 | 不改 cache key |
| Q2 | tool registry 应该在 backend 还是 packages？ | backend 当前 `apps/backend/app/services/mcp_session.py` 内联了 5 个 tool 定义。若要让 scheduler_worker 未来也跑 MCP，registry 应迁到 `packages/domain/`。但 ideation 文档显式说 #4 (domain extraction) is `not grounded — no extraction necessary`。**默认放 backend**。 | `apps/backend/app/services/mcp_tool_registry.py` |
| Q3 | `caller_role` 缓存到 slot 的有效期 = SSE 连接寿命。如果 owner 在连接期间被降级为 member，slot 仍是 owner — 是 bug 还是 feature？ | 真实场景：owner 把所有权 transfer 给另一个成员，此时旧 owner 的 active SSE 仍以 owner 身份执行。SSE 寿命默认很短（每问一次 chat 重建），影响窗口分钟级。**默认接受这个窗口**，理由是显式 caller 校验比 per-call DB 查询更经济，且 transfer 是低频操作。 | 接受窗口；前端在 transfer 后强制刷新 chat 入口 |
| Q4 | member 与 owner 在首期的工具集差异 = 0（都看到 5 个只读工具）。这种情况下 §3.1 S4 的 `list_tools()` 静态裁剪在第一个 PR 里没有可见效果，是否还要做？ | 做的理由：tool registry 是后续写工具的接收骨架，比「先内联、写工具上线时再抽」更省事；不做的理由：首期没差异，YAGNI。**默认做**，因为这是 §2 「绕过 MCP spec #278」产品价值的承载点。 | 做；首期 owner/member 在 registry 里 allowed_roles 都填 `{"owner","member"}` |

---

## 7. Test Strategy（acceptance 之外的 enforcement）

- **Unit**: `tests/unit/test_mcp_session_caller_binding.py` — `MCPSession.__slots__` 长度断言 / `_get_caller_user` cross-family 拒绝 / inactive 拒绝 / arguments 里 emit `caller_user_id` 被忽略。
- **Integration**: `tests/integration/test_mcp_caller_role_filtering.py` — 对每个 (caller_role, tool) cell 启动真实 SSE 连接，`tools/list` 比对、`tools/call` 比对。
- **Static**: ruff custom rule（或 mypy plugin / 启动期 AST 检查）— 任何注册到 server 的 handler 函数体读 `arguments.get("family_id" | "caller_user_id" | "role")` 启动失败。
- **Audit replay**: 取一条历史 audit log（child caller × 任意工具），验证经过本次改造后会被拒绝，且在 stage 环境的 audit 日志里没有等效条目。

---

## 8. Dependencies / Prerequisites

- 不依赖任何上游 ideation idea（#1/#3/#4/#5/#6/#7 都是叠加层，本 #2 独立可上）。
- 不依赖前端改动（SSE handshake header 由 agent 发，不经前端）。
- 依赖 backend 现有 `User.role` 字段稳定（已 verified `packages/db/models/user.py:30` `'owner', 'member', or 'child'`）。
- 依赖 agent 现有 `audit_logger.AuditEntry.user_id` 字段（已 verified `apps/agent/services/audit_logger.py:57`）。

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| `family_adapter_cache` 命中率显著下降 | Low | typical 4-member family 把 100 cap 折算成 25 family；可观测 `get_cache_stats`；必要时 cap 上调到 200 |
| caller_role 在 slot 过期窗口里产生不一致（Q3） | Low | 接受窗口；前端 transfer 后强制 refresh；如必要在 owner-only tool 二次校验时多查一次 DB |
| LLM 看到 permission_denied 后陷入循环重试 | Low-Medium | 返回 `retryable:false` + 短中文 reason；audit log 记录 retry 次数，超过阈值 break stream |
| 静态 tool registry 与实际 list_tools 漂移 | Low | 启动期校验：`all(tool in registry for tool in server.list_tools())` 否则 fail-fast |
| child 端将来接入 MCP 时本设计需要回退（A3 假设错误） | Medium | A3 文档化为 explicit assumption；child 接入时新开 brainstorm，本 #2 不预先建模 |

---

## 10. Handoff to /ce-plan

When ready, `/ce-plan` should treat this document as fixed. Specifically:

- 不要在 plan 阶段重新讨论「caller 在哪一层绑定」(A1)、「scope 形状」(A2/A4)、「child 是否进 MCP」(A3) — 这些是产品决策，应该先回到本文档调整 Assumptions 再 replan。
- Plan 阶段决定的是：tool_registry 的具体文件结构、迁移 PR 切分、单元测试位置、cache key 是否真的不动（Q1）等技术实现选项。
- Plan 阶段必须显式回答 §6 的 Q1/Q2/Q4。Q3 已在 Risks 里有 mitigation，可不再决策。
