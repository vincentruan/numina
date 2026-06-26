# AI Chat Streaming 端到端验证报告

> 验证日期: 2026-06-23
> 验证目标: Backend → Agent SSE 代理链的功能完整性、四种思考模式、MCP/Skill/WebSearch 集成

---

## 1. 测试环境

| 项目 | 值 |
|------|-----|
| Backend URL | `http://localhost:8000/api/v1/ai/chat/stream` |
| Agent URL | `http://localhost:8001/api/threads/{id}/runs/stream` |
| 认证方式 | JWT Bearer token (Backend) → X-Agent-Token (Agent) |
| 测试用户 | demouser (family_id=1824578943130650) |
| AI 模型 | qwen3.7-plus (openai_compatible) |

## 2. 租户 AI 配置确认

| 配置项 | 状态 | 详情 |
|--------|------|------|
| AI 供应商 | ✅ 已配置 | qwen3.7-plus, 1 个 active provider |
| 智能体 (数鸣) | ✅ 已启用 | id=100000000000005, skills=["*"] (全部技能) |
| 智能体 (资产报告) | ✅ 已启用 | id=100000000000006, skills=["report"] |
| 内置 Skills | ✅ 6 个 | report, alerts, allocation, disposal, liability, spending_leak |
| WebSearch | ✅ 已启用 | DuckDuckGo, circuit_state=closed |
| MCP 服务器 | ❌ 0 个 | 租户下未配置 MCP 服务器 |

### 2.1 SSE Event 类型映射

| SSE Event | 数据来源 | 说明 |
|-----------|---------|------|
| `session.start` | Backend `ai_chat.py` proxy 生成 | 包含 session_id + task_id |
| `values` | DeerFlow `typed_stream_dispatch` → runs.py 透传 | LangGraph 状态快照 (messages/artifacts) |
| `messages` | DeerFlow `typed_stream_dispatch` → runs.py 透传 | AI 文本逐 token 流 (`type: "ai"`, `content`) |
| `custom` | runs.py 生成 | tool_call、suggestions 等元事件 |
| `end` | runs.py 生成 | 流结束 sentinel |

## 3. 测试结果总表

### 3.1 数鸣模式 (agent_id=100000000000005)

| 测试 # | 模式 | 参数组合 | SSE 流 | AI 回答 | event: end | 状态 |
|--------|------|---------|--------|---------|------------|------|
| 1 | **闪速** (flash) | deep_think=false, plan_mode=false, subagent=false | ✅ messages ×11, values ×6 | ✅ 自我介绍 | ✅ | ✅ |
| 2 | **思考** (think) | deep_think=true, plan_mode=false, subagent=false | ✅ messages ×20, values ×7, custom ×4 | ✅ 资产健康分析 | ✅ | ✅ |
| 3 | **Pro** (deep research) | deep_think=true, plan_mode=true, subagent=false | ✅ messages ×13, values ×7, custom ×3 | ✅ 资产配置分析 | ✅ | ✅ |
| 4 | **Ultra** (super research) | deep_think=true, plan_mode=true, subagent=true | ✅ messages ×32, values ×7, custom ×2 | ✅ 全面财务分析 | ✅ | ✅ |

### 3.2 开放问答 (通过数鸣智能体, agent_id=100000000000005)

| 测试 # | 模式 | SSE 流 | AI 回答 | event: end | 状态 |
|--------|------|--------|---------|------------|------|
| 5 | **闪速** | ✅ messages, values | ✅ 天气回答(简短) | ✅ | ✅ |
| 6 | **思考** | ✅ messages ×136, values ×6 | ✅ ML 详解(完整长文) | ✅ | ✅ |
| 7 | **Pro** | ✅ messages ×207, values ×3 | ⚠️ Flask/FastAPI对比(被截断) | ❌ 超时截断 | ⚠️ |
| 8 | **Ultra** | ✅ messages ×171, values ×3 | ⚠️ 资产配置建议(被截断) | ❌ 超时截断 | ⚠️ |

### 3.3 开放问答 (无 agent_id, 旧路径)

| 测试 # | 模式 | SSE 流 | 状态 |
|--------|------|--------|------|
| 9-12 | 全部 | ❌ 仅 session.start + custom: 404 | ❌ |

## 4. 发现的问题

### P0 — 阻塞性问题

#### 问题 1: 无 agent_id 的开放问答路径不可用

**现象:** 当 `agent_id=null` 时，Backend proxy 路由到 `/chat/ask/stream`，但该端点已在 Agent 端移除。

**影响:** 前端无法在不指定智能体的情况下发送普通问答请求。所有请求必须携带 `agent_id`。

**建议修复:**
- 方案 A: 在 Backend proxy 层，当 `agent_id=null` 时自动使用默认智能体 (如数鸣) 的 ID 代替
- 方案 B: 前端调用时始终携带 `agent_id`，若用户未选择则传递默认值

#### 问题 2: Pro/Ultra 模式长回答被截断

**现象:** Pro 和 Ultra 模式的 15 秒超时导致长回答被截断，`event: end` 未收到。

**影响:** 复杂财务分析问题可能在回答未完成时被截断。

**建议修复:**
- Backend proxy `AgentClient` 的超时时间 (当前 130s) 理论上足够，但 curl 测试的超时 (15s) 较短
- 需要确认前端流式读取的超时策略是否匹配

### P1 — 需关注的差异点

#### 问题 3: Backend proxy vs 直接 Agent SSE 格式差异

| 对比项 | 直接 Agent runs.py | Backend Proxy |
|--------|-------------------|---------------|
| `session.start` | ❌ 无 | ✅ 额外添加 |
| `messages` data | `{"type":"ai","content":"..."}` | 完全一致 |
| `values` data | 状态快照 | 完全一致 |
| `custom` | tool_call 等 | 完全一致 |
| `end` | sentinel | 完全一致 |
| SKILL 名 | `chat` | `100000000000005` (agent_id) |

**结论:** 核心 SSE 协议完全兼容。`session.start` 是预期行为（前端需要 session_id 初始化）。SKILL 名差异不影响前端消费。

#### 问题 4: SKILL 名使用 agent_id

**现象:** 数鸣模式下，DeerFlow 收到的 SKILL 名为 `100000000000005` (智能体的数字 ID)，而非语义化的 `numina` 或 `chat`。

**影响:** 如果 DeerFlow 的 skill routing 依赖 SKILL 名称匹配，可能存在问题。当前测试未发现问题，但需关注。

### P2 — 配置相关

#### 问题 5: 无 MCP 服务器配置

**现象:** 测试租户没有配置 MCP 服务器。虽然 WebSearch 已启用，但 MCP 资产数据查询能力未验证。

**影响:** 无法验证 MCP 集成链路的端到端功能。

**建议:** 配置至少一个 MCP 服务器后重新验证。

## 5. SSE 报文存档

所有测试的原始 SSE 报文已保存:

| 文件 | 对应测试 | 大小 |
|------|---------|------|
| `/tmp/sselog_numina_mode1_flash.txt` | 数鸣-闪速 | 7.3 KB |
| `/tmp/sselog_numina_mode2_think.txt` | 数鸣-思考 | 15.7 KB |
| `/tmp/sselog_numina_mode3_pro.txt` | 数鸣-Pro | 14.1 KB |
| `/tmp/sselog_numina_mode4_ultra.txt` | 数鸣-Ultra | 17.3 KB |
| `/tmp/sselog_open_via_numina_flash.txt` | 开放-闪速(通过数鸣) | 6.8 KB |
| `/tmp/sselog_open_via_numina_think.txt` | 开放-思考(通过数鸣) | 28.8 KB |
| `/tmp/sselog_open_via_numina_pro.txt` | 开放-Pro(通过数鸣) | 27.1 KB |
| `/tmp/sselog_open_via_numina_ultra.txt` | 开放-Ultra(通过数鸣) | 22.6 KB |
| `/tmp/sselog_open_mode1_flash.txt` | 开放-闪速(无agent_id) | 160 B |
| `/tmp/sselog_open_mode2_think.txt` | 开放-思考(无agent_id) | 160 B |
| `/tmp/sselog_open_mode3_pro.txt` | 开放-Pro(无agent_id) | 160 B |
| `/tmp/sselog_open_mode4_ultra.txt` | 开放-Ultra(无agent_id) | 160 B |

## 6. 结论

- **数鸣模式 4 种思考模式均正常运作**，SSE 格式与 DeerFlow 协议完全兼容
- **开放问答必须通过 agent_id 路由**，旧的无 agent_id 路径已废弃
- **Pro/Ultra 模式在长回答场景需要关注超时策略**
- **MCP 集成需要配置服务器后才能验证**
