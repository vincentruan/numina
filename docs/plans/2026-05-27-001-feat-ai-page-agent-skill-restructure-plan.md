---
date: 2026-05-27
type: feat
origin: docs/brainstorms/2026-05-26-ai-page-agent-skill-restructure-requirements.md
status: active
deepened: null
---

# feat: /ai 页面智能体与技能职责重构

## Summary

把 `/ai` 重构为以智能体为入口的统一页面：两个系统智能体（AI问答 + 数鸣，含品牌花体字 logo）、资产时光机作为独立应用卡、自定义智能体并列展示。后端通过 alembic migration 删除六个 builtin 业务智能体行（资产体检、配置漂移、闲置清仓、资金泄漏、负债优化、老化预警），它们继续作为 skill 存在。Skill 管理移除"固定技能"概念，仅管理六个业务 skill + 自定义 skill。新增 `agent_dispatch.py` sentinel + per-agent skill 解析层，统一 agentId 路由，让 AI问答（仅 chat）与数鸣（全能）的能力边界在运行时强制执行。

---

## Problem Frame

参见 origin: `docs/brainstorms/2026-05-26-ai-page-agent-skill-restructure-requirements.md` 的 Problem Frame 部分。简述：

- 系统智能体当前不可见（AIHubPage 只渲染 builtin + custom，过滤掉 system）
- chat / time_machine 错误归类为"fixed skills"，与真正的业务 skill 混淆
- 六个 builtin 业务智能体身份重复（既是 agent 行又是 skill 文件）
- 缺少品牌化主入口（Numina 视觉资产未应用到智能体卡片）

---

## Origin Document Reference

源自 `docs/brainstorms/2026-05-26-ai-page-agent-skill-restructure-requirements.md`（17 个 requirements R1-R17，11 个 acceptance examples AE1-AE11，4 个 key flows F1-F4，6 个 actors A1-A6）。所有 R-ID / AE-ID / F-ID 引用均指向该文档。

12 个 Resolve Before Planning 项已在本计划的 Key Technical Decisions 中解决或落地为具体 implementation unit。

---

## Requirements Trace

| Requirement | 涉及 Implementation Units | 备注 |
|---|---|---|
| R1 (/ai 网格三区) | U8, U9 | AgentGrid 重写 + AIHubPage 重渲染 |
| R2 (AgentGrid prop API) | U8, U9 | 移除 builtin prop，增 system，时光机卡独立渲染 |
| R3 (NuminaLogo) | U7, U9 | 提取为可复用组件，作用域 ID |
| R4 (agentId 统一路由) | U10, U11, U12 | handleAgentConsult + startChat + AIChatPage agentId 消费 |
| R5 (系统智能体定义) | U2, U4 | migration + dispatch 层；**KD2 覆盖 origin R5 fixture mandate** — soul_md 直接 inline 写入 migration |
| R6 (sentinel 解析) | U4 | agent_dispatch 新解析层 |
| R7 (skill 调用文本+CTA) | U12 | AIChatPage 助手消息 + CTA 按钮 |
| R8 (BUILTIN_CAPABILITIES 调整) | U3 | ai_skills.py 常量更新 + RESERVED_NAMES |
| R9 (FIXED_CAPABILITIES 删除) | U3, U14 | 后端 3 处清理 + 前端区移除 |
| R10 (skill 路径全面清理) | U3, U12, U14 | capabilityMeta + selectedCapability default |
| R11 (migration 删 6 个 builtin agent) | U2 | alembic up + down |
| R12 (引用清理) | U3, U10, U14, U15 | capability_catalog + handleAgentConsult + SkillsManagePage + AgentsManagePage |
| F3 (skill 管理流程, origin 覆盖 R5+R6+R8+R9+R12) | U1, U3, U14 | 后端 catalog 清理 + 前端 skill 管理页；新会话覆盖 R5/R6 sentinel 解析 |
| R13 (时光机卡保留) | U9 | 渲染独立 app 卡片 |
| R14 (时光机 MCP 工具) | — | 已降级为 follow-on，不在本计划 |
| R15 (custom agent skill 装载) | U4 | 由统一 dispatch 解析层覆盖 |
| R16 (数鸣 read-only edit view) | U6, U13 | 后端 can_edit + 前端 AgentFormPage 只读模式 |
| R17 (AgentListResponse.builtin 兼容性) | U2 (verification) | 字段保留为空数组 |

---

## High-Level Technical Design

### Skill resolution flow（新增层）

`agent_dispatch.py` 在调用 `EffectiveConfigBuilder.build()` 之前插入 skill 解析层：

```
agentId 路由进入
    │
    ▼
get_agent_config(agent_id) → agent.skills 字段
    │
    ▼
SkillResolver.resolve(agent.skills, family_id):
    │
    ├── skills == ["chat"] → return []  (纯 LLM 模式，AI问答)
    ├── skills == ["*"] → query family_skill_config
    │       → return all enabled (数鸣 sentinel)
    ├── skills == [...] → intersect with family enabled (custom agent)
    └── skills == None / [] → return []  (兜底)
    │
    ▼
EffectiveConfigBuilder.build(enabled_skills=resolved_skills, ...)
    │
    ▼
DeerFlow stream
```

**Directional guidance, not implementation specification.** 实际函数命名、错误处理、缓存策略由 implementer 决定。该 sketch 仅说明 skill 解析层的输入输出契约与分支逻辑。

### Agent grid 三区结构（前端）

```
AIHubPage.vue
  ├── Header (greeting, score, stats, report card)
  │
  ├── AgentGrid.vue
  │     ├── section 1: agents.systemAgents
  │     │     ├── AgentCard (AI问答, emoji 🤖)
  │     │     └── AgentCard (数鸣, NuminaLogo SVG)
  │     ├── section 2: agents.apps  (硬编码常量，不通过 AgentGrid prop)
  │     │     └── AppCard (资产时光机, ⏰)
  │     └── section 3: agents.customAgents
  │           ├── AgentCard (custom 1..N)
  │           └── AgentCard--create (placeholder, owner only)
  │
  └── Bottom chat input (recipient chip → agent picker)
```

`AgentGrid.vue` 的 props 改为 `systemAgents: Agent[]` + `customAgents: Agent[]`；时光机 app 卡片由 `AIHubPage.vue` 直接渲染，不进入 `AgentGrid` 的 typed `Agent[]` 数据流。

---

## Key Technical Decisions

### KD1. Sentinel + per-agent skill 解析内联在 agent_dispatch.py（不新建 service 文件）

**Decision:** 在 `agent_dispatch.py` 内**内联**一个 8-12 行的 module-level helper `_resolve_skills(agent_skills, family_enabled_skills)`，在调用 `EffectiveConfigBuilder.build()` 之前解析 agent.skills 字段。**不**新建 `skill_resolver.py` 独立 service 文件。

**Rationale:**
- `agent_dispatch.py` 是新的 agentId 网关路径（与 R4 一致）
- `chat_adapter.py` 是遗留的 `routers/chat.py` 路径，硬编码 `capability='chat'`，不读 agent.skills
- 内联实现保证 R5（AI问答 仅 chat）、R6（数鸣 sentinel）、R15（custom 手动选 skill）三个要求在运行时被强制执行
- **简单性优先（per scope-guardian + CLAUDE.md）：** 单一调用点 + 8-12 行 pure-function 逻辑不需要独立 service 抽象；`agent/CLAUDE.md` 同时禁止类似 SkillLoader 类抽象
- 解决了 brainstorm RBP 的两个 deferred items

**关于 chat_adapter.py 的处置:** 本计划不迁移 chat_adapter — 它作为遗留路径继续服务于 `routers/chat.py`（如有外部调用方仍在使用）。所有新流量通过 R4 的 agentId 路由进入 `agent_dispatch.py`。chat_adapter 的最终删除作为 follow-on 工作。Phase C 增加 grep 验证 gate 确认前端无 `/chat/ask` 残留调用（per 验证策略）。

### KD2. soul_md 直接 inline 写入 migration（覆盖 R5 的 fixture mandate）

**Decision:** 新 migration 直接 inline 数鸣的 soul_md 字符串，与现有 `a53453cf574b_unified_agent_model.py` 的模式保持一致。**不**创建 `server/packages/db/seeds/system_agents.py` fixture 模块。

**Rationale:**
- 用户决定（call-out 1：accept inline）
- 现有 migration 已建立 inline 模式，新 migration 跟随保持一致性
- soul_md 长度可控（每个 agent 约 60-80 行 markdown）
- down() 路径通过 `INSERT INTO ai_agents (...) VALUES (...)` 重建六个 builtin agent 行；soul_md 同样 inline，可承受
- 该决定与 origin R5 的 fixture 要求冲突；本计划 explicit 覆盖该约束

### KD3. Migration up/down 两条路径

**Decision:** 新 migration `xxxxx_demote_builtin_agents_seed_numina.py` 实施：

- **up():**
  1. INSERT 数鸣 (`agent_name='numina'`, fixed ID `100000000000005`, `agent_type='system'`, `skills='["*"]'`)
  2. DELETE FROM ai_agents WHERE id IN (100000000000001, 100000000000002) AND family_id=0 AND agent_type='builtin'  — 这是 `asset-health-advisor` 与 `finance-optimizer`，由 `x2581y64zqr9` 插入
  
- **down():**
  1. DELETE FROM ai_agents WHERE id=100000000000005 AND agent_name='numina'
  2. INSERT 六个 builtin agent 行（inline soul_md，与原 migration 一致）

**与 a53453cf574b 的交互:** 现有 migration 的 down() 是 `DELETE WHERE agent_type='system'` — 当 alembic rollback 链先经过本 migration 的 down() 时，数鸣已被删除；继续 rollback 到 a53453cf574b 的 down() 时，仅 ai-assistant + time-machine 被删除，无双删除问题。

### KD4. Dashboard 浮动按钮 — 不在本计划范围

**Decision:** 当前 codebase 中 `DashboardPage.vue` 没有 floating chat button。R4 的 "必须更新跳转 URL" 实际上是 spec 错误（不存在的对象无法更新）。本计划不创建该按钮，将其列入 Scope Boundaries → Deferred to Follow-Up Work。

**Rationale:** 用户决定（call-out 2: drop）。R4 的 agentId 统一路由仍然适用于 `/ai` 主入口的 startChat() 和 handleAgentConsult；dashboard 浮动按钮作为单独的入口需求由后续迭代决定是否新建。

### KD5. AIChatPage chat filter tab — 保留为兼容性

**Decision:** `AIChatPage.vue` 的 `capabilityMeta.chat` 键**保留**（不删除），但 `selectedCapability` 默认值从 `'chat'` 改为 `'all'`。`time_machine` 键也保留，作为历史会话过滤标签。

**Rationale:**
- 移除 `chat` 键会隐藏既有用户的历史会话（历史 `ai_chat_messages.capability='chat'` 数据存在）
- 默认 tab 改为 `'all'` 满足 R10 的"chat 不再是 skill 概念"语义意图，同时不破坏历史显示
- 这与 R10 的清理意图存在权衡；选择保留是为了避免静默回归

### KD6. RESERVED_NAMES 独立常量

**Decision:** 在 `ai_skills.py` 中新增 `RESERVED_NAMES = ["chat", "time_machine"]` 常量，与 `BUILTIN_CAPABILITIES` 解耦。`CustomSkillCreate.validate_skill_id` 同时检查 `BUILTIN_CAPABILITIES` 和 `RESERVED_NAMES`。

**Rationale:** R8 移除 chat/time_machine 后，原 validator 不再阻止 owner 创建同名 custom skill。独立常量保持命名空间不被复用。

### KD7. 数鸣 read-only edit view — AgentFormPage 复用

**Decision:** `AgentFormPage.vue` 检测 `agent.agent_type === 'system'`，进入只读分支：所有 field disabled，skills 显示为 family 已启用 skill 列表（含锁形图标），保存按钮从 DOM 移除，顶部 banner 解释。后端 `_to_response` 设置 system agent 的 `can_edit=true`（owner 可访问只读视图）。

**Rationale:** 避免新建独立路由；复用现有 AgentFormPage（即 AgentEdit 路由对应的组件）的视觉与导航。后端 `update_agent` 已有 `agent_type='system'` 守卫（403），UI 层提供更友好的 read-only 体验。

### KD8. 分阶段交付（4 个 PR）

**Decision:** 按 Phase A → B → C → D 顺序交付，每个 phase 一个 PR，独立可 review、可 ship。

| Phase | 范围 | PR | 阻塞下一阶段 |
|---|---|---|---|
| A | 后端基础（migration、ai_skills 清理、dispatch 解析层、capability_catalog） | PR-1 | 是 |
| B | 前端基础（NuminaLogo、AgentGrid、AIHubPage、agentId 路由） | PR-2 | 是 |
| C | 前端聊天与 skill 管理（AIChatPage、AgentFormPage、SkillsManagePage、AgentsManagePage） | PR-3 | 否（可与 D 并行） |
| D | 测试 + i18n 抛光 | PR-4 | 否 |

**Phase A→B 部署 gate（hard requirement，非建议）：**
- Phase A merge 前，Phase B PR 必须已开启（可 Draft 状态）且 CI 全绿
- Phase A 不得单独 deploy 到 production；Phase A 与 Phase B 必须同一 release window 合入
- 如出现 Phase A 已 merge 但 Phase B 阻塞超过 24 小时，触发 rollback：执行 `alembic downgrade -1` 回到 Phase A 之前
- **替代缓解（如 Phase B 周期过长）：** Phase A 的 migration up() 改为 soft-delete（添加 `is_enabled=false` 而非 `DELETE`），保留 builtin 行直到 Phase B merge 后单独的清理 migration 执行真正删除。soft-delete 路径见 Risks & Mitigation 表

**Rationale:** 用户决定（call-out 3：phased）。每个 phase 独立 review 范围聚合，降低 reviewer 认知负担；后端先行让前端能依赖稳定的 API contract。Phase A→B 硬性 gate 是防止 production 出现"系统智能体不可见 + builtin 卡片消失"的中间态。

---

## Scope Boundaries

### Deferred for later

- **资产时光机 MCP 工具暴露** — 推迟到 follow-on 迭代（R14 已明确）
- **聊天内嵌入 chart widget 渲染** — 推迟到 follow-on（R7 / Scope Boundaries 已明确）
- **Dashboard 浮动 AI 入口按钮** — 当前不存在；本计划不创建。如需后续添加，单独立项
- **chat_adapter.py 路径迁移到 agent_dispatch** — 本计划保留 chat_adapter 作为遗留路径

### Outside this product's identity

- 儿童前端 (`frontend/apps/child`) — 本次仅改造 main app
- 自定义智能体的创建/编辑 UI 流程不重新设计
- `ai_chat_messages` 表结构不变
- 多智能体并行对话（一个 session 同时与多 agent 对话）

### Deferred to Follow-Up Work

- AgentListResponse.builtin 字段最终移除（本计划保留为空数组兼容；clean-up iteration 决定）
- DeerFlow harness 是否原生支持 per-conversation skill 子集激活（本计划假定 EffectiveConfigBuilder 接收的 enabled_skills 即为最终激活集合）
- 已有 `ai_chat_messages.capability='chat'` 历史数据的清理或重新归类

---

## Phased Delivery

### Phase A: Backend Foundation (PR-1)
**单元:** U1 (含原 U6 内容), U2, U3, U4, U5
**目标:** migration 落地，skill catalog 清理，dispatch 解析层就绪，capability_catalog 与 ai_agents API 对齐
**Verification gate:** `uv run pytest tests/` 全绿；`uv run alembic upgrade head` 在测试 DB 成功；`uv run alembic downgrade -1` + `uv run alembic upgrade head` 双向迁移成功

### Phase B: Frontend Foundation (PR-2)
**单元:** U7, U8, U9, U10, U11
**Depends on:** Phase A merged
**注意：U7→U8→U9→U10→U11 为严格顺序链；Phase B 内各 unit 不可并行实现** — U8 依赖 U7、U9 依赖 U8、U10 依赖 U9、U11 依赖 U10
**目标:** NuminaLogo 组件、AgentGrid 三区、AIHubPage 重渲染、agentId 统一路由
**Verification gate:** `npm run typecheck` 通过；`npm run test:run` 全绿；浏览器手动验证 `/ai` 渲染正确

### Phase C: Frontend Chat & Skill Mgmt (PR-3)
**单元:** U12, U13, U14, U15
**Depends on:** Phase B merged (transitive: Phase A 已 merge — U12 直接依赖 U4 SkillResolver)
**目标:** AIChatPage 消费 agentId、AgentFormPage 数鸣只读视图、SkillsManagePage 移除"固定技能"区、AgentsManagePage 内置区清理
**Verification gate:**
- typecheck + test:run 全绿
- 手动验证 owner 编辑数鸣进入只读模式
- **legacy chat path 验证（封堵遗留路径运行时缺口）：** `grep -rn "chat/ask\\|/chat/ask/stream" frontend/apps/main/src/` 在 AIHubPage、AIChatPage 重构后**无任何匹配**（确认所有前端入口已迁移到 `agentId` 路由 + agent_dispatch 路径）。如 grep 仍有匹配，说明 SkillResolver 边界未完整封闭，必须在本 phase 清理或显式 follow-on 立项

### Phase D: Tests & Polish (PR-4)
**单元:** U16, U17
**Depends on:** Phase B merged（可与 Phase C 并行开始；全部 AE test 需等 Phase C 合并后方可全绿）
**目标:** AE1-AE11 集成测试覆盖，新 i18n 字符串补齐
**Verification gate:** 所有 AE 对应的 test 通过；i18n 检查无 missing key

---

## Implementation Units

### U1. ai_skills.py — RESERVED_NAMES + BUILTIN_CAPABILITIES 调整

**Goal:** 后端 skill catalog 常量按 R8 / R9 重构；新增 RESERVED_NAMES 常量保护 chat / time_machine 命名。

**Requirements:** R8, R9, R10 (KD6)

**Dependencies:** 无（最先落地，后续 unit 复用）

**Files:**
- `server/apps/backend/app/routers/ai_skills.py` (modify)
- `server/apps/backend/tests/test_ai_skills.py` (modify; create if absent)

**Approach:**
- `BUILTIN_CAPABILITIES = ["report", "alerts", "allocation", "disposal", "liability", "spending_leak"]` (移除 chat 和 time_machine)
- 删除 `FIXED_CAPABILITIES` 常量
- 删除 `toggle_skill_endpoint` 中 `if skill_id in FIXED_CAPABILITIES: raise ...` 守卫
- 删除 `list_skills_grouped` 中 `fixed = [SkillDefinitionResponse(id="chat",...), SkillDefinitionResponse(id="time_machine",...)]` 硬编码块；返回 schema 的 `fixed` 字段保留为空数组（前端依赖该字段存在但为空）
- **`reorder_skills_endpoint` 第 4 处引用清理（line ~369）**：删除 `and skill_id not in FIXED_CAPABILITIES` 子条件。chat/time_machine 已不在 BUILTIN_CAPABILITIES，外层 `if skill_id in BUILTIN_CAPABILITIES` 已自然过滤
- 新增 `RESERVED_NAMES = ["chat", "time_machine"]`
- `CustomSkillCreate.validate_skill_id` 追加：`if v in RESERVED_NAMES: raise ValueError("skill_id 与保留命名冲突")`
- ai_skills.py 顶部新增 module docstring 说明 `RESERVED_NAMES` 与 `chat` 内部保留能力规则（合并自原 U6 任务）

**Patterns to follow:** 现有 `validate_skill_id` 的 ValueError 抛出模式

**Test scenarios:**
- 禁用 BUILTIN_CAPABILITIES 中的某个 skill（如 `report`）成功
- toggle skill 接口对 `chat` 返回 404 / 不存在（不再是 capability）
- create custom skill with `skill_id='chat'` 被 RESERVED_NAMES 拒绝（400 + 中文错误消息）
- create custom skill with `skill_id='report'` 被 BUILTIN_CAPABILITIES 拒绝
- `GET /ai/skills` flat 列表不包含 chat 或 time_machine
- `GET /ai/skills/grouped` 返回的 `fixed` 字段为空数组 `[]`

**Verification:** `uv run pytest tests/test_ai_skills.py -v` 全绿；`grep -rn "FIXED_CAPABILITIES\|chat.*BUILTIN_CAPABILITIES" server/apps/backend/app/` 无残留引用

---

### U2. Alembic migration — 删除 6 个 builtin agent + 插入数鸣

**Goal:** 后端数据层完成 ai_agents 表的智能体重构。

**Requirements:** R5, R11, R17 (KD2, KD3)

**Dependencies:** U1（避免数据 migration 与 catalog 调整混在同一 PR 文件冲突）

**Files:**
- `server/apps/backend/alembic/versions/<rev_id>_demote_builtin_agents_seed_numina.py` (create)
- `server/apps/backend/tests/test_migrations.py` (modify; 验证 up/down 双向)

**Approach:**
- 新 migration `revision='<rev_id>'`，`down_revision='a53453cf574b'`（或最新 head）
- **实际 builtin agent 行（已通过 codebase 验证）：仅 2 个**，由 `x2581y64zqr9_unify_ai_tables_and_add_agents.py` 在 ID `100000000000001` 与 `100000000000002` 处插入：
  - `asset-health-advisor` (id `100000000000001`)
  - `finance-optimizer` (id `100000000000002`)
- **up():**
  1. `op.execute("INSERT INTO ai_agents (id, family_id, agent_name, display_name, description, icon, color, soul_md, skills, agent_type, display_order) VALUES (100000000000005, 0, 'numina', '数鸣', '...', '✨', '#8b5cf6', '<inline soul_md>', '[\"*\"]', 'system', 11)")`
  2. `op.execute("DELETE FROM ai_agents WHERE id IN (100000000000001, 100000000000002) AND family_id=0 AND agent_type='builtin'")`
- **down():**
  1. `op.execute("DELETE FROM ai_agents WHERE id=100000000000005 AND family_id=0 AND agent_name='numina'")`
  2. 重新 INSERT `asset-health-advisor` (id 100000000000001) 与 `finance-optimizer` (id 100000000000002)，inline soul_md 引用 `x2581y64zqr9` 中原始内容

**Execution note:** Start by reading existing migration `a53453cf574b_unified_agent_model.py` to confirm column names, ID conventions, and soul_md formatting; mirror that style.

**Patterns to follow:** `server/apps/backend/alembic/versions/a53453cf574b_unified_agent_model.py` 的 `op.execute("INSERT...")` 模式

**Test scenarios:**
- alembic upgrade head 成功；ai_agents 表中 numina 行存在，agent_type='system'，skills='["*"]'
- alembic upgrade head 后**两个** builtin agent 行已被删除（`SELECT COUNT(*) FROM ai_agents WHERE agent_type='builtin'` 返回 0）
- alembic downgrade -1 成功；numina 行已删除，`asset-health-advisor` + `finance-optimizer` 已恢复且 soul_md 内容完整
- `GET /ai/agents`（family scope）返回 system 数组含 ai-assistant + numina（2 项），builtin 数组为空 `[]`

**Verification:** `uv run alembic upgrade head` 成功；`uv run alembic downgrade -1 && uv run alembic upgrade head` 往返成功；测试套件全绿

---

### U3. capability_catalog.py — 移除 chat 和 time_machine entries

**Goal:** UI metadata 与 R8 的 BUILTIN_CAPABILITIES 调整保持一致。

**Requirements:** R10, R12

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/services/capability_catalog.py` (modify)
- `server/apps/backend/tests/test_capability_catalog.py` (modify; create if absent)

**Approach:** 从 `_CAPABILITY_OVERRIDES` dict 删除 `"chat"` 和 `"time_machine"` 两个键。`apply_capability_overrides` 函数无需改动（已是泛型 dict merge）。

**Patterns to follow:** 文件本身的简单 dict 模式

**Test scenarios:**
- `apply_capability_overrides({"id": "report"})` 仍然返回正确的 ui metadata
- `apply_capability_overrides({"id": "chat"})` 返回未经 override 的原始 dict（不再有 _CAPABILITY_OVERRIDES 注入）

**Verification:** `uv run pytest tests/test_capability_catalog.py -v` 全绿；`grep -n "chat\|time_machine" server/apps/backend/app/services/capability_catalog.py` 仅剩注释（如有）

---

### U4. agent_dispatch.py — Skill resolver 内联层

**Goal:** 实现 R5（AI问答仅 chat）、R6（数鸣 sentinel）、R15（custom agent 手动选 skill）的运行时强制。**单一消费者，内联实现，不引入独立 service 文件。**

**Requirements:** R5, R6, R15 (KD1, RBP item resolved)

**Dependencies:** U1, U2

**Files:**
- `server/apps/agent/services/agent_dispatch.py` (modify) — 内联解析逻辑，**不**新建独立文件
- `server/apps/agent/tests/test_agent_dispatch.py` (modify; 增 sentinel/per-agent skill 单元用例 + 真实 harness 集成测试)

**Approach:**
- 在 `agent_dispatch.py` 中 `client.get_enabled_skills()` 调用与 `EffectiveConfigBuilder.build()` 调用之间，插入 4 分支解析逻辑（约 8-12 行）：
  - `if agent_skills == ["chat"]:` 返回 `[]`（reserved 内部能力，不进入 skill catalog）
  - `if agent_skills and "*" in agent_skills:` 返回 `family_enabled_skills`（数鸣 sentinel 全集）
  - `if agent_skills:` 返回 `[s for s in family_enabled_skills if s["skill_id"] in set(agent_skills)]`（custom agent 交集）
  - `else:` 返回 `[]`
- 实现作为 module-level helper `_resolve_skills(agent_skills, family_enabled_skills) -> list` 放在 agent_dispatch.py 文件顶部；保持 pure function，不依赖外部 state
- agent_dispatch 主流程：`fetched_skills = await client.get_enabled_skills(); skill_entries = _resolve_skills(agent_config.get("skills"), fetched_skills)`，结果作为 `enabled_skills` 参数传入 EffectiveConfigBuilder
- **理由（per scope-guardian 反馈）：** 单一调用点 + 8-12 行逻辑不构成 "service" 抽象；CLAUDE.md 简单性优先原则反对为单一使用者引入新文件。`agent/CLAUDE.md` 也禁止 SkillLoader 类抽象。如未来出现第二个消费者（如 chat_adapter 迁移），再提取为独立模块

**Execution note:** Implement test-first — write failing tests for each branch in `_resolve_skills` before adding the helper.

**Patterns to follow:** `server/apps/agent/services/agent_dispatch.py` 现有的 module-level helper function 模式（pure function or stateless）

**Test scenarios:**
- AI问答 (`skills=["chat"]`) → `_resolve_skills` 返回 `[]`
- 数鸣 (`skills=["*"]`) + family 启用 3 个 skill → `_resolve_skills` 返回 3 项
- 数鸣 + family 启用 0 skill → `_resolve_skills` 返回 `[]`（覆盖 AE9）
- custom agent (`skills=["report", "allocation"]`) + family 启用 4 个 skill 含 report 与 allocation → `_resolve_skills` 返回 2 项（交集）
- custom agent (`skills=["report"]`) + family 未启用 report → `_resolve_skills` 返回 `[]`
- agent.skills 为 `None` → `_resolve_skills` 返回 `[]`
- agent_dispatch 调用 EffectiveConfigBuilder.build() 时 `enabled_skills` 参数等于 `_resolve_skills` 返回值（单元测试，mock EffectiveConfigBuilder）
- **harness-level integration test (真实 DeerFlow 或薄层 mock)：** AI问答 dispatch 后，DeerFlow 收到的 `available_skills` 配置为空 list（覆盖 AE2 — 验证 harness 真实遵守 skill 列表，而非仅验证传参）
- **harness-level integration test：** 数鸣 dispatch 后，DeerFlow 收到的 `available_skills` 等于 family 全部启用 skill（覆盖 AE3）
- 如 harness 不直接暴露 `available_skills`，可通过 LLM 调用历史 stub 验证：注入特定 skill 名作为 trigger phrase，确认对应/未对应 skill 被激活/未激活

**Verification:** `uv run pytest server/apps/agent/tests/test_agent_dispatch.py -v` 全绿；`grep -n "_resolve_skills" server/apps/agent/services/agent_dispatch.py` 确认调用链穿过 helper

---

### U5. ai_agents.py routers — system agent can_edit 调整

**Goal:** 后端 `_to_response` 设置 system agent 的 `can_edit=true`（owner 可访问只读视图）。

**Requirements:** R16

**Dependencies:** U2

**Files:**
- `server/apps/backend/app/routers/ai_agents.py` (modify)
- `server/apps/backend/tests/test_ai_agents.py` (modify)

**Approach:**
- `_to_response(agent, current_user)` 中 `can_edit` 计算逻辑调整为：
  - `agent_type == 'system' and current_user.role == 'owner'` → `can_edit=True`（用于 read-only 视图导航）
  - `agent_type == 'builtin'` → `can_edit=False`（保持现有行为）
  - `agent_type == 'custom' and current_user.role == 'owner'` → `can_edit=True`
- `update_agent` 端点的 `if agent.agent_type == 'system': raise AppError(403)` 守卫**保留**（前端不调用 PUT，但守卫提供 defense-in-depth）

**Patterns to follow:** `_to_response` 函数现有的 can_edit / can_delete 计算模式

**Test scenarios:**
- `GET /ai/agents` as owner → numina (`agent_type='system'`) 返回 `can_edit=true`
- `GET /ai/agents` as adult (non-owner) → numina 返回 `can_edit=false`
- `PUT /ai/agents/{numina_id}` as owner → 仍然 403（守卫不变）

**Verification:** `uv run pytest tests/test_ai_agents.py -v` 全绿

---

### U6. [已合并到 U1] — 原"chat reserved capability 处理"

**已合并到 U1.** 原 U6 的工作（chat 保留能力的服务端语义、ai_skills.py module docstring 注明 RESERVED_NAMES）实质上是 U1 的延续，且修改同一文件 `ai_skills.py`。为避免 Phase A 内部 PR merge 冲突与 ghost-unit 现象，原 U6 内容已并入 U1 的 Approach 与 Test scenarios。U-ID `U6` 保留以维持 ID 稳定性，不再单独行动。后续引用 `U6` 视为 U1 的一部分。

---

### U7. NuminaLogo Vue 组件提取

**Goal:** 从 `LoginPage.vue` 提取 cursive Numina SVG 为可复用组件，使用 `useId()` 作用域 SVG 内部 IDs。

**Requirements:** R3 (KD from doc-review)

**Dependencies:** Phase A merged（独立 unit，可与 Phase A 并行编写但需在 Phase B PR 中合入）

**Files:**
- `frontend/apps/main/src/components/common/NuminaLogo.vue` (create) — 放在 main app 内，避免新建 frontend/packages/ui 包的 scaffolding 开销；child app 复用作为 follow-on 决策
- `frontend/apps/main/src/pages/LoginPage.vue` (modify; 替换 inline SVG 为 `<NuminaLogo />`)
- `frontend/apps/main/src/components/common/__tests__/NuminaLogo.test.ts` (create)

**Approach:**
- 复制 `LoginPage.vue` 的 SVG 块到 NuminaLogo.vue
- 使用 `import { useId } from 'vue'` 生成 `const uid = useId()`，在所有 `<defs>` 内的 id 属性上加前缀 `${uid}-flourishGrad` 等
- 同步更新所有 `url(#xxx)` 与 `filter="url(#xxx)"` 引用为 `url(#${uid}-xxx)`
- props 接受 `width`、`color` 等可选自定义参数（保留 LoginPage 现有 220px 默认尺寸，AIHubPage 使用 max-width: 80px 见 U9）
- LoginPage.vue 删除 inline SVG，使用 `<NuminaLogo class="numina-logo" />`

**Patterns to follow:** `frontend/packages/` 现有 Vue 组件包结构（参考 numina 现有 packages，如 auth, ui）

**Test scenarios:**
- 单实例渲染：DOM 中存在 4 个 unique id（flourishGrad、textGrad、logoGlow、logoSoftglow）带 useId 前缀
- 多实例渲染：同一 page 渲染 2 次，DOM 中存在 8 个 unique id（两两不冲突）
- 多实例渲染：第二个实例的 stroke 渐变正确显示（无视觉退化为黑色 — 表示 `url(#xxx)` 引用解析到正确的 def）
- LoginPage.vue 渲染：仍显示 cursive Numina logo（视觉无退化）

**Verification:** `npm run test:run NuminaLogo` 全绿；`npm run typecheck` 通过；浏览器手动验证 LoginPage 与 AIHubPage 多实例渲染正常

---

### U8. AgentGrid.vue — 三区结构 prop API

**Goal:** AgentGrid 支持 system/custom 两个 prop（移除 builtin），time-machine app 卡片不通过 grid 渲染。

**Requirements:** R1, R2

**Dependencies:** U7

**Files:**
- `frontend/apps/main/src/components/agent/AgentGrid.vue` (modify)
- `frontend/apps/main/src/components/agent/AgentCard.vue` (modify; numina 使用 NuminaLogo)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify; 新增 `agents.systemAgents`、`agents.apps` keys)
- `frontend/apps/main/src/components/agent/__tests__/AgentGrid.test.ts` (modify)
- `frontend/apps/main/src/components/agent/__tests__/AgentCard.test.ts` (modify)

**Approach:**
- AgentGrid props: `systemAgents: Agent[]`, `customAgents: Agent[]`, `showCreate?: boolean`（移除 `builtinAgents`）
- 添加新 `<div class="agent-section">` 区块用于 system agents，i18n key `agents.systemAgents`
- AgentCard 增加分支：当 `agent.agent_name === 'numina'` 时，icon 槽位渲染 `<NuminaLogo :width="80" />`，其他 agent 渲染 emoji
- **Icon 槽尺寸约束：** `.agent-card__icon` 设置固定 `height: 56px` 与 `display: flex; align-items: center; justify-content: center`，同时容纳 32px emoji 与 80×24px NuminaLogo SVG。卡片整体高度不变（2 列网格行高一致）
- **Dark-mode NuminaLogo 可见性：** `.agent-card__icon .numina-logo` 在 `[data-theme='dark']` 下增加 `filter: brightness(1.4)` 或检查 SVG 内 gradient stop 颜色在深色背景的对比度；如需要，传 `color` prop 覆盖默认渐变色
- **同一份 props 适用于 R1 三区结构：** custom section title 始终渲染（不加 v-if）；当 `customAgents.length === 0 && !showCreate` 时，复用现有 `van-empty` 提示文案（per AE11）；当 `showCreate=true` 时显示"创建智能体"占位卡
- **AgentGrid prop rename 与 AIHubPage 调用点同 PR 原子合入（per U9）：** U8 单独应用会导致 typecheck 失败，必须与 U9 在同一 commit / PR 中合并
- 不在 AgentGrid 中渲染 time-machine app 卡片（由 AIHubPage 直接渲染，见 U9）

**Patterns to follow:** AgentGrid.vue 现有 `<div v-if="builtinAgents.length" class="agent-section">` 结构

**Test scenarios:**
- AgentGrid 接收 `systemAgents` 渲染 system 区
- AgentGrid 不接受 `builtinAgents` prop（typecheck 错误如传入）
- AgentCard with `agent_name='numina'` 渲染 NuminaLogo（DOM 含 `<svg class="numina-logo">`）
- AgentCard with `agent_name='ai-assistant'` 渲染 `agent.icon` emoji（DOM 不含 svg）
- 空 customAgents 数组不渲染 customAgents 区块标题（v-if 守卫保留）
- showCreate=true 时显示"创建智能体"占位卡

**Verification:** `npm run test:run AgentGrid AgentCard` 全绿；`npm run typecheck` 通过

---

### U9. AIHubPage.vue — 三区渲染重构

**Goal:** AIHubPage 按 R1 顺序渲染：系统智能体区、应用区（资产时光机硬编码）、自定义智能体区。

**Requirements:** R1, R2, R3, R13

**Dependencies:** U8

**Files:**
- `frontend/apps/main/src/pages/AIHubPage.vue` (modify)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify; 新增应用区相关 key 与时光机 app 卡片描述)
- `frontend/apps/main/src/pages/__tests__/AIHubPage.test.ts` (modify)

**Approach:**
- 移除 `builtinAgents` 引用，改为传 `agentStore.systemAgents.filter(a => a.is_enabled)` 给 AgentGrid
- 在 AgentGrid 与 customAgents 区之间硬编码渲染时光机 app 卡片（独立 `<div class="agent-section">`，包含 emoji ⏰，i18n title `aiHub.timeMachineCardTitle` 与描述）
- 该 app 卡片点击跳转 `/ai/time-machine`（保留现有路由）
- AgentGrid 的 `:custom-agents` 仍然传 `agentStore.customAgents.filter(a => a.is_enabled)`

**Patterns to follow:** AIHubPage.vue 现有 `<div class="feature-section">` 渲染 grid 的方式

**Test scenarios:**
- Owner 视图：渲染顺序为 [AI问答, 数鸣, 时光机 app, custom agents..., 创建占位]（覆盖 AE1）
- 非 owner 视图：不渲染创建占位卡（覆盖 AE11）
- 资产体检 / 配置漂移等旧 builtin agent 卡片不出现
- 数鸣 卡片渲染 NuminaLogo（覆盖 AE5）

**Verification:** `npm run test:run AIHubPage` 全绿；浏览器手动验证 `/ai` 渲染正确

---

### U10. AIHubPage handleAgentConsult — agentId 统一路由

**Goal:** 移除按 agent_name 和 skills 的 special-case 路由；所有智能体一律 `/ai/chat?agentId=<id>`。

**Requirements:** R4, R12

**Dependencies:** U9

**Files:**
- `frontend/apps/main/src/pages/AIHubPage.vue` (modify; handleAgentConsult)
- `frontend/apps/main/src/pages/__tests__/AIHubPage.test.ts` (modify)

**Approach:**
- handleAgentConsult 简化为：`router.push({ name: 'AIChat', query: { agentId: agent.id } })`
- 删除 `agent_name === 'ai-assistant'` 分支（特例移除）
- 删除 `agent.skills?.includes('report')` 等所有 skill-based 路由分支（六个 builtin agent 已被 migration 删除，分支即死代码）
- `agent_name === 'time-machine'` 分支删除（time-machine 现在是独立 app 卡片，不通过 handleAgentConsult，由 U9 的 app 卡片直接处理 router.push）

**Patterns to follow:** R4 的统一 agentId 路由

**Test scenarios:**
- handleAgentConsult(numina_agent) → push `/ai/chat?agentId=<numina_id>`
- handleAgentConsult(ai-assistant_agent) → push `/ai/chat?agentId=<ai-assistant_id>`（无 special-case）
- handleAgentConsult(custom_agent) → push `/ai/chat?agentId=<custom_id>`
- 删除的死代码分支不再存在（`grep "skills?.includes"` 在 AIHubPage.vue 无匹配）

**Verification:** `npm run test:run AIHubPage` 全绿；diff 确认 special-case 分支删除

---

### U11. startChat() 注入 numina agentId

**Goal:** 底部输入框默认绑定数鸣作为收件人；recipient chip UI；agentId 在路由 query 中携带。

**Requirements:** R4

**Dependencies:** U10

**Files:**
- `frontend/apps/main/src/pages/AIHubPage.vue` (modify; startChat + recipient chip)
- `frontend/apps/main/src/components/common/AIChatInput.vue` (modify; 增 recipient chip slot 或 prop)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify; 新增 `aiHub.sendTo` 等 key)
- `frontend/apps/main/src/pages/__tests__/AIHubPage.test.ts` (modify)

**Approach:**
- AIHubPage 计算属性：`const numinaAgent = computed(() => agentStore.systemAgents.find(a => a.agent_name === 'numina'))`
- 底部输入框上方渲染 chip：`发送给：<icon> 数鸣 ▾`，点击弹出 Vant action sheet 列出所有已启用 system + custom 智能体
- **chip 加载与空态：**
  - `agentStore.loadAgents()` 未完成时（store 数据为空），chip 渲染骨架占位：宽度固定（~120px）、显示 van-skeleton 一行
  - `numinaAgent.value` 解析为 `undefined`（migration 未应用或加载失败），chip 显示通用 fallback `发送给：智能体 ▾`，并 disable 提交按钮
  - action sheet 列表为空时，显示中央空态文案 `aiHub.noEnabledAgents`（"暂无可用智能体"）+ "前往智能体管理" 跳转入口
- **action sheet 中 numina 条目的 icon 渲染：** 使用 `<NuminaLogo :width="24" />`（每个实例由 useId 作用域 ID，per U7），其他 agent 用其 emoji；保持列表行高一致
- ref `selectedRecipient` 默认为 numina；用户切换后更新 ref
- `startChat(q)` 改为：`router.push({ path: '/ai/chat', query: { q, agentId: selectedRecipient.value.id, newSession: '1', deepThink, webSearch } })`

**Patterns to follow:** Vant action sheet 现有用法（参考其他页面如 AssetFormPage）

**Test scenarios:**
- 页面加载时 chip 显示"发送给：数鸣"
- 点击 chip 弹出 sheet 列表含 AI问答 + 数鸣 + 已启用 custom agents
- 切换到 AI问答 后，chip 显示"发送给：AI问答"
- startChat 携带正确的 agentId 跳转
- 默认（未切换）情况下 startChat 携带 numina_id

**Verification:** `npm run test:run AIHubPage` 全绿

---

### U12. AIChatPage.vue — agentId 消费 + capabilityMeta 调整

**Goal:** AIChatPage 读取 agentId 加载 agent soul/skill；移除 chat default capability filter；保留 chat 历史 tab 兼容性。

**Requirements:** R4, R7, R10 (KD5)

**Dependencies:** U11, U4

**Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue` (modify)
- `frontend/apps/main/src/api/agent.ts` (verify; 应已提供 `getAgent(id)` 接口)
- `frontend/apps/main/src/pages/__tests__/AIChatPage.test.ts` (modify)

**Approach:**
- mounted hook 读取 `route.query.agentId`，调用 `getAgent(agentId)` 加载 agent 信息（display_name, icon, soul，supported skills）
- agent 缺失（无 agentId / 加载失败）→ fallback 到 numina（按 agent_name 查 store）
- **Chat header 布局（375px 视口）：** 头部行从左到右为 `[back] [history] [agent-icon + display_name] [edit?] [new]`。agent identity 占据中间灵活宽度（min-width 0 + text-overflow ellipsis），其他 5 个图标按钮固定宽度。数鸣使用 `<NuminaLogo :width="24" />`（24px 紧凑版）取代 emoji；其他智能体使用 emoji + display_name
- **Loading / fallback render：** `getAgent()` 进行中时 header 中部显示骨架占位（一行 80px 宽 van-skeleton）。若加载失败，先 fallback 到 numina display 再异步重试一次
- **Session 标题：** 原 `displayedTitle` 动画字符串作为 agent identity 下方的副标题（更小字号，灰色），不再占主标题位置
- `selectedCapability` 默认值改为 `'all'`（替换 `'chat'`）
- `capabilityMeta` 中 `chat` 与 `time_machine` 键**保留**（用于历史会话过滤），但 UI 上 chat tab 不再作为新会话默认入口
- **Skill 调用结果的 CTA 按钮规范：**
  - 元素类型：`<van-button size="small" plain type="primary">` 或语义化 `<a class="skill-cta">` （二选一，team 风格优先选 van-button 与 AIChatPage 现有按钮一致）
  - 位置：**助手消息流式文本气泡 下方** 作为独立 block，间距 8px；不在 inline
  - 时机：仅当本轮 `phase === 'done'` 后渲染（避免流式中途渲染半成品按钮）
  - tap target：最小 44×44px（移动端可达性）
  - 多 skill 调用同一回复：CTA 按钮纵向 stack，垂直间距 8px，按 skill 调用顺序排列
  - 文案：`查看 <skill_display_name> 详情`，点击 router.push 对应 `/ai/<skill>` 页面

**Patterns to follow:** AIChatPage 现有 `useAgentEventStream` SSE 处理；`AiFinalAnswer.vue` 助手消息渲染

**Test scenarios:**
- `/ai/chat?agentId=<numina_id>` 加载 → header 显示数鸣（NuminaLogo + 名称）
- `/ai/chat?agentId=<ai-assistant_id>` 加载 → header 显示 AI问答 + 🤖 icon
- `/ai/chat`（无 agentId）→ fallback 到数鸣
- 数鸣对话调用 allocation skill → 助手消息文本流式输出 + 末尾出现"查看 配置漂移 详情"CTA 按钮（覆盖 AE6）
- 点击 CTA 按钮跳转 `/ai/allocation`
- `selectedCapability` 默认值 'all'，历史 chat session 在切换到"全部"或"chat" tab 时仍可见
- AI问答 在 family 未启用任何 skill 时不报错（覆盖 AE2 + AE9）

**Verification:** `npm run test:run AIChatPage` 全绿；浏览器手动验证 4 个 agent 类型的进入路径

---

### U13. AgentFormPage.vue — 数鸣只读模式

**Goal:** owner 进入数鸣 edit 路由时进入 read-only 视图；所有 field disabled，保存按钮 DOM 移除，banner 显示。

**Requirements:** R16 (KD7)

**Dependencies:** U5

**Files:**
- `frontend/apps/main/src/pages/AgentFormPage.vue` (modify)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify; 新增 `agents.form.systemAgentBanner` 等 key)
- `frontend/apps/main/src/pages/__tests__/AgentFormPage.test.ts` (modify; create if absent)

**Approach:**
- 增加 `const isSystemAgent = computed(() => formData.value?.agent_type === 'system')`
- 模板顶部条件渲染 banner：`<van-notice-bar v-if="isSystemAgent">{{ t('agents.form.systemAgentBanner') }}</van-notice-bar>`，banner 紧贴 nav-bar 下方，在 scroll container **之外** （固定可见）
- 所有 `<van-field>`、`<van-cell>` 增加 `:disabled="isSystemAgent"`
- skills 区域：当 isSystemAgent=true 且 skills 包含 `"*"`，渲染为已解析的 family 启用 skill 列表（每项前 lock icon `<van-icon name="lock" />`），不显示字面 `["*"]`
  - **Skills 加载态：** `getSkillsGrouped()` 加载中时 skills 区域显示 `<van-skeleton :row="3" />`
  - **Skills 空态：** family 启用 0 skill 时显示 van-empty 配合文案 `agents.form.noEnabledSkills`（"暂未启用任何技能，可前往技能管理开启"）+ 跳转 CTA
  - **Lock icon 来源：** 统一使用 Vant `<van-icon name="lock" />`，无 inline SVG
- 保存按钮使用 `<template v-if="!isSystemAgent">` 包裹（DOM 移除而非 disabled）
- `handleSubmit` 增加防御：`if (isSystemAgent.value) return` 提前返回
- **isBuiltin vs isSystemAgent 调和（per feasibility 反馈）：** isSystemAgent 检查放在 handleSubmit 的最前面（早 early-return），优先于现有 isBuiltin 分支。原 isBuiltin 分支保留以兼容（实际生效仅当 agent_type='builtin' 行恢复 — 当前为空，但保留防 down() 后场景）

**Patterns to follow:** AgentFormPage 现有 `isBuiltin` ref 的分支模式（不直接复用，因为 isBuiltin 与 isSystemAgent 语义不同）

**Test scenarios:**
- owner 进入 `/settings/ai/agents/<numina_id>/edit` → form 全部 disabled，banner 渲染，保存按钮 DOM 不存在（覆盖 AE10）
- 显示的 skill 列表为 family 当前启用的 skill（带 lock icon），不显示字面 `["*"]`
- 用户点击返回按钮不发起 PUT/PATCH（manual mock + assertNoApiCall）
- owner 进入 custom agent edit → 仍然全部可编辑，保存按钮存在
- adult 用户访问 numina edit 路由 → 现有路由 guard 阻止（如有），或 view-only 渲染

**Verification:** `npm run test:run AgentFormPage` 全绿；浏览器手动验证 owner 进入数鸣 edit 视图

---

### U14. SkillsManagePage.vue — 移除"固定技能"区 + builtinIds 同步

**Goal:** 前端 skill 管理页与 R8/R9/R10 后端清理保持一致。

**Requirements:** R8, R9, R10, R12

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/pages/SkillsManagePage.vue` (modify)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify; 删除 `skills.fixedSkills` key)
- `frontend/apps/main/src/pages/__tests__/SkillsManagePage.test.ts` (modify)

**Approach:**
- 完整删除 `<van-cell-group :title="t('skills.fixedSkills')">...</van-cell-group>` 元素及其循环 `v-for="skill in groupedSkills?.fixed ?? []"` 块
- 更新硬编码 `builtinIds` 数组：`['alerts', 'allocation', 'disposal', 'liability', 'report', 'spending_leak']`（移除 `chat` 与 `time_machine`）
- 自定义 skill 创建时的 id 校验：`if (builtinIds.includes(skillId))` + 新增 `if (['chat', 'time_machine'].includes(skillId))` 阻止保留命名（与后端 RESERVED_NAMES 对齐）
- i18n: 从 zh-CN.ts 删除 `skills.fixedSkills` key

**Patterns to follow:** SkillsManagePage 现有的 builtin/custom van-cell-group 渲染

**Test scenarios:**
- 渲染时顶部"固定技能"区不出现（DOM 不含对应标题）（覆盖 AE4）
- 列表只展示六个业务 skill 开关 + 自定义 skill
- 创建自定义 skill 时 id='chat' → 表单错误"与保留命名冲突"（前端 + 后端双重校验）
- 创建自定义 skill 时 id='report' → 表单错误"与内置技能冲突"

**Verification:** `npm run test:run SkillsManagePage` 全绿；`grep -n "fixedSkills" frontend/apps/main/src/` 无匹配

---

### U15. AgentsManagePage.vue — 移除"内置智能体"区

**Goal:** migration 删除六个 builtin agent 后，AgentsManagePage 的 builtinAgents van-cell-group 整体移除。

**Requirements:** R12

**Dependencies:** U2

**Files:**
- `frontend/apps/main/src/pages/AgentsManagePage.vue` (modify)
- `frontend/apps/main/src/pages/__tests__/AgentsManagePage.test.ts` (modify)

**Approach:**
- 删除 `<van-cell-group inset :title="t('ai.builtinAgents')">...</van-cell-group>` 元素及其 `v-for="agent in agentStore.builtinAgents"` 循环
- 保留 system agents 区与 custom agents 区
- i18n key `ai.builtinAgents` 与 `ai.builtinAgentHint` 删除（如未在他处使用）

**Patterns to follow:** AgentsManagePage 现有 system/custom van-cell-group 模板

**Test scenarios:**
- 渲染时 `ai.builtinAgents` title 不出现
- system 区渲染 ai-assistant + numina（2 项）
- custom 区渲染 family 自定义 agents

**Verification:** `npm run test:run AgentsManagePage` 全绿；`grep -n "builtinAgents" frontend/apps/main/src/pages/AgentsManagePage.vue` 无匹配（前端 store 仍保留 ref，但页面引用应清理）

---

### U16. 集成测试 — AE1-AE11 覆盖

**Goal:** 端到端 / 集成测试覆盖所有 acceptance examples，建立未来回归基线。

**Requirements:** AE1-AE11（除 AE8，已 follow-on）

**Dependencies:** U1-U15 全部完成（含 U1 后端常量调整，AE4 验证依赖此）

**Files:**
- `frontend/apps/main/src/pages/__tests__/integration/agent-restructure.test.ts` (create)
- `server/apps/agent/tests/integration/test_skill_dispatch.py` (create or extend)
- `server/apps/backend/tests/integration/test_agent_lifecycle.py` (create or extend)

**Approach:**
- 将 11 个 AE 写为命名的 integration test cases，每个 test case 引用对应 AE 编号
- 部分 AE 需要 mock LLM 响应（数鸣 dispatch 测试用 stub LLM）
- AE7 验证 `GET /ai/agents` 返回结构（builtin: []）

**Patterns to follow:** 现有 `tests/integration/` 结构与 mock LLM 模式（参考 `tests/test_ai_chat.py` 等）

**Test scenarios:**
- AE1：owner 访问 `/ai`，渲染顺序正确
- AE2：family 启用 report+allocation，问"闲置资产"，不调用 disposal skill
- AE3：family 启用第 5 个 skill 后，新对话立即可调用（无需重启）
- AE4：SkillsManagePage 渲染，无固定技能区
- AE5：数鸣卡片渲染 NuminaLogo（不是 emoji）
- AE6：allocation skill 调用结果含文本+CTA（非 chart）
- AE7：`GET /ai/agents` 返回结构正确
- AE8：[已移除 — 资产时光机 MCP 工具暴露推迟到 follow-on 迭代，不在本计划测试范围]
- AE9：family 无启用 skill 时数鸣不报错
- AE10：owner 进入数鸣 edit 进入只读视图
- AE11：非 owner 自定义智能体空态行为

**Test expectation:** all AE-tagged tests pass

**Verification:** `npm run test:run integration/agent-restructure` 与 `uv run pytest tests/integration/ -v` 全绿

---

### U17. i18n 完整性补齐

**Goal:** 新增的所有 i18n key 在 zh-CN.ts 中完整定义；运行 i18n 检查无 missing key。

**Requirements:** Cross-cutting (项目 i18n 规范)

**Dependencies:** U7-U15 完成

**Files:**
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify)
- `frontend/apps/main/src/i18n/__tests__/i18n-completeness.test.ts` (modify; create if absent)

**Approach:**
- 全文 grep `t('...')`、`$t('...')` 收集所有 key 引用
- 与 zh-CN.ts 比对，列出缺失 key
- 补齐所有缺失 key，包括但不限于：
  - `agents.systemAgents`、`agents.apps`、`agents.appsHint`
  - `agents.form.systemAgentBanner`、`agents.form.systemAgentSkillLock`
  - `aiHub.sendTo`、`aiHub.timeMachineCardTitle`、`aiHub.timeMachineCardDesc`
  - `aiHub.changeRecipient`
  - 新 CTA 按钮文案
- 删除已废弃 key：`skills.fixedSkills`、`ai.builtinAgents`、`ai.builtinAgentHint`（如不再被引用）

**Patterns to follow:** 现有 `frontend/apps/main/src/i18n/locales/zh-CN.ts` 的命名空间结构

**Test scenarios:**
- 自动化 i18n completeness 测试：扫描所有 .vue / .ts 中的 `t('...')` 引用，比对 zh-CN.ts，无 missing key
- 所有 toast 字符串含 emoji 前缀（per CLAUDE.md emoji convention）
- 所有 hardcoded 中文字符串不出现在 .vue / .ts logic 中（per CLAUDE.md i18n required rule）

**Verification:** `npm run test:run i18n-completeness` 全绿；手动 grep `'一-龥` 在 .vue 模板中只命中 i18n key 定义

---

## System-Wide Impact

| 组件 | 影响范围 |
|---|---|
| ai_agents 表 | -6 行（builtin），+1 行（numina），保留 ai-assistant + time-machine（system） |
| ai_skills 后端 API | `BUILTIN_CAPABILITIES` 缩减为 6 项；`FIXED_CAPABILITIES` 删除；新增 RESERVED_NAMES |
| agent_dispatch | 新增 SkillResolver 层，所有 agent 的 dispatch 路径都经过 |
| chat_adapter | 不变（遗留路径，作为 follow-on 工作迁移） |
| capability_catalog | 删除 `chat` / `time_machine` 两条 entry |
| AIHubPage `/ai` | 主入口视觉与交互重构（系统/应用/自定义三区） |
| AIChatPage | 新增 agentId 消费逻辑，capability filter 默认值变更 |
| AgentFormPage | 新增 system agent read-only 模式 |
| SkillsManagePage | 移除"固定技能"区 |
| AgentsManagePage | 移除"内置智能体"区 |
| LoginPage | NuminaLogo 提取为独立组件（视觉无变化） |
| `/ai/report`、`/ai/allocation` 等 | 不变（保留为 skill 调用结果的详情页） |

**前端 store**: `agentStore.builtinAgents` ref 保留为空数组（不删，避免破坏类型契约）；`agentStore.systemAgents` 与 `agentStore.customAgents` 是主要数据源。

**`AgentListResponse.builtin`** schema 字段保留为 `[]`（per R17/KD），不破坏 API 兼容性。

---

## Risks & Mitigation

| 风险 | 影响 | Mitigation |
|---|---|---|
| Migration up() 后六个 builtin agent_name 与文档假设不一致 | up() 不删除任何行 | U2 实施前 ce-work 阶段先 SELECT 现有 ai_agents WHERE agent_type='builtin' 确认实际 agent_name |
| SkillResolver 与 EffectiveConfigBuilder 的契约错误 | dispatch 时 skills 集合错误 | U4 完整 unit + integration test；test_skill_dispatch end-to-end 覆盖 4 种 agent 形态 |
| NuminaLogo SVG 引用 useId() 但 Vue 版本不兼容 | 编译失败 | 已验证 Vue 3.5.30 支持 useId（feasibility 已确认） |
| AgentFormPage read-only 模式遗漏某个 field 的 disabled | owner 仍能修改 | U13 增加自动化 DOM 测试断言所有 form field 的 disabled 属性 |
| migration down 路径恢复 6 个 builtin agent 时 soul_md 丢失 | 回滚后 agent 缺失 description | U2 验证 down → up 双向；soul_md 完整 inline |
| AIChatPage 历史 chat session 在 selectedCapability='all' 默认下显示混乱 | 用户找不到旧会话 | U12 测试覆盖；保留 chat 与 time_machine tab 作为可选过滤 |
| Phase B 合入前用户访问 `/ai` 仍渲染六个旧 builtin 卡片但点击死链 | 用户体验回归 | Phase A migration 落地后**立即**触发 Phase B；建议 Phase A 与 Phase B 在同一 release 窗口内合入 production |

---

## Verification Strategy

### Unit-level
- 每个 implementation unit 的 test scenarios 全部通过
- `npm run typecheck` 无错误
- `uv run pytest tests/ -v` 全绿

### Integration-level
- AE1-AE11 集成测试（U16）全部通过
- alembic up + down + up 双向迁移成功（U2）

### Manual smoke (per phase)
- **Phase A**：postgres 中验证 ai_agents 表行数变化；`GET /ai/agents` API 返回正确结构；`POST /ai/agents/{id}/toggle` 对 system agent 仍 403
- **Phase B**：浏览器访问 `/ai`，确认三区渲染；数鸣卡片显示 NuminaLogo；点击各智能体卡片正确跳转 chat 页带 agentId
- **Phase C**：浏览器访问 `/settings/ai/agents/<numina_id>/edit`，确认只读视图；访问 `/settings/ai/skills`，确认无固定技能区；`/ai/chat?agentId=<numina_id>` 流式输出
- **Phase D**：所有 AE 集成测试通过

### Quality gates per phase
- Phase A merge 前：backend pytest + alembic round-trip
- Phase B merge 前：frontend typecheck + test:run + 手动 smoke
- Phase C merge 前：同 Phase B
- Phase D merge 前：所有 AE test 全绿

---

## Outstanding Questions

### Resolve During Implementation

- **[Affects U2]** ✅ 已通过 codebase 验证：实际 builtin 行为 `asset-health-advisor` (id 100000000000001) + `finance-optimizer` (id 100000000000002)，共 2 个，非原计划假设的 6 个。U2 已更新为正确列表
- **[Affects U4]** SkillResolver 是否做缓存（per-session 或 LRU）— ce-work 阶段根据现有 EffectiveConfigBuilder 的调用频率决定；初版可不缓存
- **[Affects U7]** ✅ 已通过 codebase 验证：`frontend/packages/` 下不存在 `ui` 包；NuminaLogo 已重定位至 `frontend/apps/main/src/components/common/`，避免引入新 workspace package 的 scaffolding 开销
- **[Affects U13]** AgentFormPage 当前 isBuiltin 分支与 isSystemAgent 调和已在 U13 Approach 中解决（isSystemAgent 早 early-return 优先于 isBuiltin 分支）；isBuiltin 分支保留以兼容理论上的 down() 后回滚场景

### Deferred Beyond This Plan

- DeerFlow harness 是否原生支持 per-conversation skill 子集 — 假定 SkillResolver 输出即为最终激活集合；如未来需要 harness 层过滤再单独处理
- chat_adapter.py 路径迁移到 agent_dispatch — follow-on 工作
- 资产时光机 MCP 工具暴露 — follow-on 工作
- 聊天内嵌入 chart widget 渲染 — follow-on 工作
- `AgentListResponse.builtin` 字段最终移除 — clean-up iteration
- 已有 `ai_chat_messages.capability='chat'` 历史数据的清理或重新归类 — clean-up iteration

---

**Plan ready.**
