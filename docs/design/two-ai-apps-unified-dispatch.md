# 双 AI 应用统一调度重构设计文档

**日期**: 2026-07-17（2026-07-17 按 live code 二次校正 dispatch/skill/SOUL 前提）
**状态**: 设计待评审（4 个决策点已确认；各阶段量化验收已补；评审勘误已并入阶段 0/2/4/5；**dispatch 前提已按最新代码校正——见 §1.2/§3.1/§3.5/阶段0/阶段4 校正块**；**2026-07-18 ce-doc-review Round 2 后修订：app 数从 2 扩为 3，见 §1.1 修订块**）
**目标**: 项目保留 AI 应用（数鸣 / AI 资产报告 / 导入解析），统一调度走 `stream_run`，废弃所有不使用的调度路径；按 MECE 原则重整 skill。

> **2026-07-18 修订（ce-doc-review Round 2 Apply 决断）**：原"仅保留两个 AI 应用"扩为**三个**——新增 `import-parse` 作为第 3 个 `stream_run` agent（U8）。origin 原 §8 fork (a)"import_parse 迁 `app="numina`""**修订为按调用形态分流**：suggest 改轻量 LLM 单次调用、import_parse 重构为独立第 3 个 stream_run agent（详见 implementation plan `docs/plans/2026-07-17-002-...` 的 Resolved-10 + U8）。理由：import_parse 是独立的 AI 应用（文件→资产/信用卡解析），与 numina/asset-report 并列；当前走 `orchestrator.dispatch` 无 skill fallback + `output_mapper._from_dict` 通用 schema 与持仓快照不匹配——半坏链路，需专属 agent + SKILL.md + MCP 写入工具。此修订经用户 2026-07-18 确认（Apply 决断）。

---

## 1. 核心定位（用户定义 + 已确认决策）

### 1.1 AI 应用（2026-07-18 修订：2 → 3）
- **数鸣（numina）智能体**: 家庭租户的通用分析智能体，资产顾问能力。业务能力可插拔（用户可自定义 skill），按 MECE 原则管理。
- **AI 资产报告（asset-report）**: 非严格智能体，是系统流程中的固定流程。**三步流水线**（决策2+3，KTD-7 修订见下）:
  1. **标准 DeerFlow 研究报告生成**: LLM 调 family-data MCP 取数据 → markdown 评分报告 → `write_file` **落文件保存供审计**。
  2. markdown → JSON（indicators schema）：同一 agent run 内 LLM `read_file` 读回 markdown + 输出 JSON（KTD-7 修订，不再单独调家庭 provider）。
  3. json-repair + schema 校验 → 落 `ai_reports` 表。
- **导入解析（import-parse）**（2026-07-18 新增，第 3 个 `stream_run` agent，U8 落地）: 文件→资产/负债/信用卡结构化解析的独立 AI 应用。多模态读图（扫描件 PDF）+ MCP `import_*_batch` 批量写入 DB。归类 = 系统内置固定流程（进 `RESERVED_NAMES`，不进 `BUILTIN_CAPABILITIES`）。详见 implementation plan U8 + Resolved-10。

  > **KTD-7/KTD-8 修订（2026-07-17 二次勘察 + 选型确认）**：三步在**一个 `stream_run` agent run 内**完成（不再 backend 跨 HTTP 编排、不再步骤2 单独调家庭 provider），prompt 落点 = 新建 `skills/builtin/public/asset-report/SKILL.md`（合并删 3 report skill 后的 prompt），归类 = 系统内置固定流程（进 `RESERVED_NAMES`，不进 `BUILTIN_CAPABILITIES`）。详见 §3.4。

### 1.2 四个障碍的统一解法
| 障碍 | 解法 |
|---|---|
| 1. `Orchestrator` 类缺 `stream_dispatch` | **校正**：`Orchestrator` 类（`agent/services/orchestrator.py`，routers 导入的 `orchestrator` 实例）**只有 `dispatch` + `_error_response`，从来没有 `stream_dispatch`**。`stream_dispatch` 仅存在于另一个对象 `ChatAdapter`（`deerflow_adapter/adapter.py:165`）。6 个 router（report/disposal/allocation/spending_leak/liability/time_machine）的流式 `/events` 端点调 `orchestrator.stream_dispatch(...)` → 运行即 `AttributeError`（自 a97eb08c 起已死）。统一用 `runs_stream.stream_run`（v2 改正式名）；报告也走此路径 |
| 2. 报告走 orchestrator skill 路径 | 仅保留 2 个 AI 应用；无关触发式功能按 §2 MECE 分类处理 |
| 3. worker 硬编码 chat/chat-search | worker 按 `app` 分派；报告步骤2 ~~直接调家庭 provider~~（KTD-7 修订：同 agent run 内 read_file+输出 JSON）|
| 4. 3 个输出契约 | 报告 = 三步流水线（markdown→json→repair），非 3 个 skill |

> ⚠️ **dispatch 删除风险校正（P0，2026-07-17 live code 核验 + KTD-9 修订）**：原"删 `dispatch` 会破坏 8 个在线 router"的表述**前提反了**。live `dispatch(...)` caller 共 9 处（report.py:28 / disposal.py:33 / allocation.py:45 / spending_leak.py:34 / import_parse.py:32 / liability.py:33 / suggest.py:40 / time_machine.py:46 / alerts.py:33），在类上存在、是活的。而 6 个 router 的 `stream_dispatch(...)` 调用本就已死（AttributeError）。KTD-9 后真实工作：report（阶段4）+ 5 trigger skill + time_machine（阶段4.5）的 7 个 caller **随 router 删除消失**（非迁移），仅 `import_parse`/`suggest` 2 caller 迁移（阶段5），再删 `Orchestrator.dispatch`。

---

## 2. Skill MECE 分类（决策1：先分类后重构）

### 2.1 分类原则
- **合并进数鸣 SOUL**: 属于 agent 内置灵魂/通用分析框架的（非用户可移除的能力底座）。
- **保留为 skill（可移除）**: 真实外扩技能，用户可移除以精简。评估合并/拆分。
- **删除**: 报告流水线内联后不再需要的 skill。

### 2.2 全部 16 个 skill 的分类

#### A. 报告相关 → 删除（流水线内联）
| skill | 处理 | 去向 |
|---|---|---|
| `report` | 删 | 步骤1 的 markdown 生成 prompt → 内联到新建 `asset-report` skill 目录的 SKILL.md |
| `report_generate` | 删 | 同上（markdown 模板并入 `asset-report` SKILL.md，write_file 由步骤1 完成） |
| `report_structured` | 删 | 步骤2 的 JSON schema → 内联为 `asset-report` SKILL.md 步骤2 prompt 指示 |

#### B. 通用分析框架 → 合并进数鸣 SOUL（不可移除的能力底座）
| skill | 处理 | 理由 |
|---|---|---|
| `family-asset-checkup` | 合并进 SOUL | 资产体检的 scorecards/risk_flags/recommendations 框架是数鸣的通用分析方法论，非专项能力 |
| `family-liability-review` | 合并进 SOUL | 负债分析的同一框架，与 checkup 同构 |
| `fixed-asset-followup` | 合并进 SOUL | 固定资产跟踪的同一框架 |
| `family-finance-insight-planner` | 合并进 SOUL | 深度研究的规划步骤模板，是数鸣的通用推理框架（plan_mode） |

> **依据**: 这 4 个 family-* skill 共享同一 JSON schema（`summary`/`scorecards`/`risk_flags`/`recommendations`/`rule_based_findings`/`ai_inferences`/`disclaimers`），是同一分析框架的不同切口，属于数鸣的"如何分析家庭财务"方法论底座，应作为 agent 灵魂而非可移除技能。
>
> ⚠️ **注册状态校正（2026-07-17 live code 核验）**：这 4 个 family-* skill **已注册在 `apps/backend/app/bootstrap/skills.py`**（`_BUILTIN_SKILLS` 列表，`input_mode: "trigger"` + 固定 Snowflake ID + `display_order`，`family_id=0` 系统模板）。**非**"未注册"。合并进 SOUL 须同步删 `bootstrap/skills.py` 4 个注册块 + `system_ids.py` 4 个 `SKILL_*_ID` 常量 + Alembic 数据迁移清理 `skill_registry`/`family_skills` 表中引用这 4 个 `skill_id` 的行（详见阶段 2 勘误）。

#### C. 真实外扩技能 → **删除**（KTD-9，能力回归数鸣 SOUL）
| skill | 现状 schema | 处理 | 理由 |
|---|---|---|---|
| `alerts` | `alert_type`(aging/high_maintenance/idle_cost) + severity + suggestion | **删除**（全栈清理） | 老化预警分析回归 SOUL 推理；遗留页面/DB/parser/writer 清理 |
| `allocation` | drift/target_pct/current_pct（配置偏离） | **删除**（全栈清理） | 配置偏离分析回归 SOUL；⚠️ `ai_allocation_targets` 用户配置数据 fork 见 KTD-9 (2) |
| `disposal` | resale_range/suggested_channel（处置） | **删除**（全栈清理） | 闲置处置建议回归 SOUL 推理 |
| `liability` | priority_debt/recommended_strategy（还款策略） | **删除**（全栈清理） | 负债优化策略回归 SOUL 推理 |
| `spending_leak` | leak_type/estimated_annual_waste（消费漏洞） | **删除**（全栈清理） | 隐性浪费识别回归 SOUL 推理 |

> **KTD-9 修订（2026-07-17 已确认）**：原"C 类保留为可开关 skill"**被推翻**——用户判定这 5 个"之前做成包含页面的应用是个错误，重构没清理干净"，当前 AI 应用就 2 个，其能力"完全是做成了 skill"应回归数鸣 SOUL 推理。5 个各有独立前端页面 + DB 表 + 结构化契约（`ai_result_parser.py` schema 块 + `ai_result_writer.py` typed writer），删除即全栈清理（页面/DB/parser/writer/路由/注册/i18n）。能力回归：数鸣 SOUL（`chat/SKILL.md`，已并 family-* 框架）补充 3 核心分析方向引导（资产负债分析/优化现金流/挖掘投资机会）。页面降级：原可 dismiss 持久结构化列表消失，用户经 /ai/chat 对话获同类分析（自由文本 + JSON）。
>
> ⚠️ **`ai_allocation_targets` 用户数据 fork（KTD-9 (2)）**：该表存用户手工配置的目标配比（非 LLM 输出），删 allocation 即丢用户配置。待决断：(a) 随删除（默认，彻底精简）；(b) 保留表 + 简化配置入口供 SOUL 读取。

#### D. 对话模式 + 系统内置固定流程 → 系统内置（保留，不进用户可开关目录）
| skill | 处理 | 理由 |
|---|---|---|
| `chat` | 保留为系统内置（已在 `RESERVED_NAMES`） | 数鸣的纯对话模式 |
| `chat-search` | 保留为系统内置（worker 按 `websearch_enabled` 自动选择） | 数鸣的联网搜索对话模式 |
| `asset-report`（**新建**） | 新建为系统内置固定流程（加入 `RESERVED_NAMES`，KTD-8） | AI 资产报告三步流水线的单一 SKILL.md prompt（合并删 3 个 report skill 后的 prompt）；系统固定流程，用户不可开关 |

> **校正（2026-07-17 live code 核验）**：`RESERVED_NAMES = ["chat", "time_machine"]`（`apps/backend/app/routers/ai_skills.py:52`）——`chat-search` **不在** `RESERVED_NAMES` 也**不在** `BUILTIN_CAPABILITIES`，它是一个普通 builtin skill 目录（`skills/builtin/public/chat-search/`，含 `allowed-tools: [web_search, web_fetch]`）。这两个对话 skill 不进用户可开关目录，由 worker 按 `websearch_enabled` 自动选择（`worker.py:230` `capability = "chat-search" if (call_websearch_enabled and has_search_capability) else "chat"`）。
>
> **KTD-8 校正（2026-07-17 已确认）**：新建的 `asset-report` 归为**系统内置固定流程**（选 (a)），**不进** `BUILTIN_CAPABILITIES`，**不进** `INTERNAL_ONLY_SKILLS`。落点 = 加入 `RESERVED_NAMES` + 建独立 skill 目录 `skills/builtin/public/asset-report/SKILL.md`。
>
> **KTD-9 校正（2026-07-17 已确认）**：`time_machine` 非 AI skill（纯计算计算器应用：`ai_time_machine.py` + `projection/whatif/purchasing_power` 服务无 LLM），与 skill 系统"毫不相干"——**从 `RESERVED_NAMES` 移除**，删死 agent router（`agent/routers/time_machine.py` 调不存在的 `stream_dispatch`），保留纯计算 backend router + `AITimeMachinePage.vue` + `capability_registry.py` UI 卡片入口不动。故 `RESERVED_NAMES` 终值 = `["chat", "asset-report"]`（加 asset-report、移除 time_machine）。

#### E. 内部 skill → 保留隔离
| skill | 处理 |
|---|---|
| `skill-creator` | 保留（`INTERNAL_ONLY_SKILLS`） |
| `skill-installer` | 保留（`INTERNAL_ONLY_SKILLS`） |

### 2.3 MECE 评估结论
- **合并/拆分评估（KTD-9 修订）**: 5 个外扩 skill（C 类）**删除**（非"不建议合并"）——其分析能力回归数鸣 SOUL 推理，遗留前端页面/DB/parser/writer 全栈清理。4 个 family-* skill（B 类）合并进 SOUL。
- **净效果**: 16 → 5 个 skill 目录（删 3 报告 + 合并 4 family-* 进 SOUL + **删 5 trigger skill**（KTD-9）+ 新建 1 `asset-report`；time_machine 无 skill 目录、解耦出系统）。最终 5 目录: asset-report / chat / chat-search / skill-creator / skill-installer。`BUILTIN_CAPABILITIES` = `[]`（report + 5 trigger skill 全删，asset-report 不进）；`RESERVED_NAMES` = `["chat","asset-report"]`（加 asset-report、移除 time_machine，KTD-8 + KTD-9）。

---

## 3. 目标架构

### 3.1 统一调度路径（仅一条）
```
所有 AI 应用 → backend → agent /api/threads/{id}/runs/stream
            → runs_stream.stream_run（v2 改正式名）→ worker.run_agent
            → 按 record.metadata["app"] 分派: numina | asset-report
```
废弃: `Orchestrator.dispatch`（删前须先清零 live caller：9 处中 7 处随 report/5 trigger skill/time_machine router 删除消失，2 处 `import_parse`/`suggest` 迁移，KTD-9）+ 6 个已死的 `orchestrator.stream_dispatch(...)` 调用（本就 AttributeError，随 router 删除）。`stream_agent_dispatch`（`agent_dispatch.py:198`）非死函数，其调用方迁移完成后另行清理。

> ⚠️ **校正**：原"废弃 `stream_agent_dispatch`（死函数）+ `orchestrator.dispatch/stream_dispatch`"的表述不准。live code 核验：(1) `stream_agent_dispatch`（`agent_dispatch.py:198`）**非死**，被 `test_agent_run_service.py` 大量引用且 `worker.py:129` 注释引用其逻辑；(2) `Orchestrator` 类**无 `stream_dispatch`**（6 个 router 的该调用已死）；(3) `Orchestrator.dispatch` 是活的，8 个 router 在用。

### 3.2 worker 重构
```python
async def run_agent(bridge, run_manager, record, family_id, user_id, thread_id,
                    graph_input, config, ...):
    app = record.metadata.get("app")  # "numina" | "asset-report"
    if app == "numina":
        await _run_numina_agent(...)            # 现有 chat/chat-search + Path C 工具过滤
    elif app == "asset-report":
        await _run_asset_report_pipeline(...)   # 三步流水线
```

### 3.3 数鸣智能体（numina）
- **SOUL.md 现状校正（2026-07-17 live code 核验）**: 仓库**不存在 `bootstrap/agents.py` 文件**，原引用 `bootstrap/agents.py:10-65` 为失效路径。当前数鸣的对话行为来自 `skills/builtin/public/chat/SKILL.md` + `chat-search/SKILL.md`（worker 按 `websearch_enabled` 选择）。存在一个 `AgentTempCache`（`services/agent_temp_cache.py`）会往临时目录写 `SOUL.md`（从 `soul_md` 字符串），但**当前无任何调用方**传入 `soul_md`——该 SOUL.md 机制本身是死代码。**待定**: 合并 4 个 family-* 框架进"数鸣 SOUL"时，需先决定 SOUL.md 的真实落点（是启用 `AgentTempCache` 路径，还是内联进 SKILL.md，或新建 agents 配置）——这是实现期须澄清的设计点，非现成文件可改。
- **SOUL.md 扩充目标**: 在上述落点确定后，并入 4 个 family-* skill 的通用分析框架（scorecards/risk_flags/recommendations 方法论 + 深度研究规划步骤）。
- **外扩 skill（KTD-9 修订）**: 5 个 C 类 skill **删除**（非保留）——能力回归数鸣 SOUL 推理，遗留页面/DB/parser/writer 全栈清理。`BUILTIN_CAPABILITIES` 终值 = `[]`（report + 5 trigger skill 全删）。
- **调度**: 走统一 `stream_run`，`app="numina"`，保留 Path C 工具过滤（active_skill_context）。

### 3.4 AI 资产报告三步流水线（决策2+3，KTD-7 修订：单 agent run）
> **架构（KTD-7 修订，2026-07-17 二次勘察确认）**：报告三步在**一个 `stream_run` agent run 内**完成，不再 backend 跨 HTTP 编排。worker `app="asset-report"` 分派 → 单次 `adapter.typed_stream_dispatch(skill_name="asset-report", ...)`，prompt（`skills/builtin/public/asset-report/SKILL.md`）引导 LLM 依次调 `write_file`（步骤1 落 markdown）→ `read_file` + 输出 JSON（步骤2）→ worker 收尾 json-repair 落库（步骤3）。步骤2 的 JSON 经 LangGraph `custom` 事件 `report.step2_json` 透传前端。backend `proxy_report_events` 两阶段编排废弃。

```python
async def _run_asset_report_pipeline(...):
    # 单 agent run，三步全在 prompt 引导下由 LLM 用工具完成
    async for sse_type, data in adapter.typed_stream_dispatch(
        skill_name="asset-report", thread=..., input=..., record=record, ...
    ):
        # 步骤1: LLM 调 family-data MCP 取数据 → 生成 markdown 评分报告 → write_file 落
        #   tenant reports 目录 / report_{timestamp}.md（审计用，worker.py 工具结果可见）
        # 步骤2: LLM 调 read_file 读回 markdown + 输出 indicators JSON 文本
        #   → worker 收到后经 LangGraph custom 事件 report.step2_json 透传前端
        # 步骤3: worker 收尾 json-repair + schema 校验 → write_report_results 落 ai_reports 表
        ...  # 复用 worker.py:235 的 (sse_type, data) 消费循环
```
```

**步骤1 prompt 落点（KTD-8 已确认）**: 原 `bootstrap/agents.py:70-143` 为失效路径（仓库无此文件）。当前不存在独立 `asset-report` agent 配置——`agent/routers/report.py` 直接调 `orchestrator.dispatch(capability="report"/"report_generate"/"report_structured")`，由对应 skill 的 SKILL.md 驱动。**KTD-8 落点 = 新建 `skills/builtin/public/asset-report/SKILL.md`**，合并删 3 个 report skill 后的 prompt（步骤1 markdown 生成 + `write_file` 落盘 + 步骤2 JSON 输出指示），`allowed-tools` 含 family-data MCP + `write_file`/`read_file`。归类 = 系统内置固定流程（加入 `RESERVED_NAMES`，不进 `BUILTIN_CAPABILITIES`）。

**步骤2 简化（KTD-7 修订）**: 不再删 `report_structured` skill 后用 worker 内直接家庭 provider LLM 单次调用。改为**同一 agent run 内** LLM `read_file` 读回步骤1 markdown + 按 SKILL.md 内联 indicators schema 输出 JSON，经 LangGraph `custom` 事件 `report.step2_json` 透传前端；worker 收尾 json-repair 落库（步骤3）。无需家庭 provider 二次 LLM 调用。

---

## 3.5 AI 资产报告触发入口（现状勘误 + 找回）

> 用户反馈"原有两个触发入口（手动 + 定时）在改动中丢失"。经全量勘察（前端/后端/agent/scheduler + git 全历史），**事实与记忆有出入，需先澄清**。

### 触发入口 1: 手动生成 —— 非"丢失"，而是 agent 层断裂

| 层 | 现状 | 证据 |
|---|---|---|
| 前端入口（2 个） | ✅ 都在、都连着 | `AIHubPage.vue:113/56`（"生成首份报告"+刷新）、`AIReportPage.vue:55/252`（立即生成/重新生成），都 POST `/ai/report/generate/events` |
| 前端路由 | ✅ 注册 | `router/index.ts:275` |
| 后端 router | ✅ 注册+连着 | `backend/main.py:424`，`ai_report.py:64` 派发 `capability="report"` |
| 后端→agent 代理 | ✅ 存在 | `_ai_events_helper.py:329/483` |
| **agent router** | ❌ **调用不存在的方法** | `agent/routers/report.py:49/74/108` 调 `orchestrator.stream_dispatch`，但 `Orchestrator` 类**从来没有** `stream_dispatch`（该方法在另一对象 `ChatAdapter`=`deerflow_adapter/adapter.py:165` 上，routers 导入的 `orchestrator` 实例并非 `ChatAdapter`）→ 运行即 `AttributeError`（自 a97eb08c 起已死）。注：`report.py:28` 的非流 `orchestrator.dispatch(capability="report")` 是**活的**（`Orchestrator.dispatch` 存在），仅流式 `/events` 端点断裂 |

**断点**: `orchestrator.stream_dispatch` 在 `Orchestrator` 类上不存在（非"被删"，是从未在该类上）。**找回方式**: 由阶段 3 将报告迁到统一 `stream_run`（`app="asset-report"`），阶段 4 删 `report.py` + 迁移/删除 `Orchestrator.dispatch` 的 live caller。前端/后端层无需改动。

### 触发策略: 8 小时缓存 + 单家庭单任务并发控制

**并发控制（已满足，无需新建）**:
- `trigger_generate_events`（`ai_report.py:77`）已调 `AITaskService.get_running_task(family_id, "report")`——有 running 报告任务则**接续**（不 409、不重复创建），是全 6 个 AI 路由共用的模式。
- `ai_report.py:96` 调 `get_any_running_task(family_id)`——家庭任意能力有 running 任务时，报告任务进 `queued` 排队（返回 202 + queue_position），前一个完成自动提升。
- **结论: "一个家庭并行只能有一个任务"已由现有 AITaskService 机制满足**，阶段 3 迁统一 `stream_run` 时保留这套检查即可。

**8 小时缓存（需新增，语义已定: 命中则提示 + 强制刷新）**:
- 现状: `AIReport` 模型（`models/ai_report.py`）只有 `generated_at`，无 `expires_at`/`cache_ttl`；`trigger_generate_events` 当前**无条件生成**。
- **缓存语义（决策 4, 2026-07-17 已定）**: 点击触发时，若最新 `AIReport` 的 `generated_at` 在 8h 内 → **不生成**，后端返回缓存命中信号（含 `generated_at`、报告已存在等）+ 不启动 NDJSON 流；前端 `AIReportPage`/`AIHubPage` 显示"报告仍新鲜"提示 + **"强制重新生成"按钮**。用户点强制刷新 → 前端带 `force=true`（或独立 query/header）调 `/generate/events` → 后端**绕过缓存**走现有生成流程。未命中（无报告或超 8h）→ 正常生成。
- **实现要点**:
  - 后端 `trigger_generate_events`（`ai_report.py`）入口先查最新 `AIReport`（已有 `GET ""` 的 latest 查询可复用），8h 内且无 `force` → 返回 `{"status": "cached", "generated_at": ..., "report": ...}`（非 `StreamingResponse`，普通 JSON，200）；带 `force` 或超 8h → 现有流程。
  - **不新增 DB 列**: 8h 阈值用 `generated_at` + `timedelta(hours=8)` 运行时计算即可，无需 `expires_at` 列、无需 Alembic migration（保持 surgical）。
  - **并发控制与缓存的关系**: 缓存检查在并发检查**之前**——缓存命中直接返回，不触达 `get_running_task`；缓存未命中/强制刷新才走并发控制（接续/排队）。强制刷新仍受单家庭单任务约束（已有 running 报告任务时仍接续而非新建，避免破坏并发不变量）。
  - **强制刷新参数透传**: `POST /generate/events?force=true`（query param）或请求头。`AIHubPage.vue`/`AIReportPage.vue` 的"生成/重新生成"按钮默认不带 force（首次无报告时也不会命中缓存）；新增"强制重新生成"按钮（仅缓存命中提示态显示）带 `force=true`。`useAITask.startStream` 透传 force 到 `startAIEventStream` 的 fetch URL。
  - **前端提示态**: 缓存命中时页面不进入执行流，而是显示提示卡片（i18n 文案如"报告仍新鲜（X 小时前生成）"+ 强制刷新按钮）；现有评分环 + indicators 卡片照常展示缓存报告内容。
  - **i18n**: 新增 `aiReport.cacheFresh`/`aiReport.forceRegenerate` 等键到 `zh-CN.ts`/`en-US.ts` 的 `aiReport` 块。

### 触发入口 2: 定时刷新 —— ⚠️ git 全历史确认从未实现过（待决策）

**勘察结论（不预设间隔，全量审计）**:
- `scheduler_worker` 现有 7 个 job（exchange_rate/file_sync/audit_log_purge/revoked_token_cleanup/device_session_cleanup/reminder_daily/snapshot_daily），**无一生成 AI 报告**。
- `agent/app/scheduler.py` 仅有两个**注释掉的** stub（月度 `day=1`、周度告警），从未启用，函数从未定义。
- git 全历史 `-S "add_job"` 审计：**从未有任何 `add_job` 引用 report/报告/health/refresh**。
- `generate_monthly_reports` / `monthly_health_report` 仅以注释 stub 出现（`scheduler.py:48/96`）。
- `AIReport` 模型无 schedule/interval/next_run 列；无报告调度表。
- `generate_health_report`（`health_report.py:127`）**零调用方**（死代码）。
- 唯一相关定时任务 `snapshot_daily`（每天 00:05，commit `9cb79e96`）生成的是**资产快照**（喂给报告的数据完整度评分），**非 AI 报告本身**，且今天仍在跑。

**结论**: 不存在"8 小时/任意间隔的定时刷新丢失"——它从未实现过。记忆可能混淆了 `exchange_rate`（`hour="8,10,12,..."` 每 2h）或 `snapshot_daily`（每天），但二者都不是 AI 报告刷新。

> **决策（2026-07-17 已定）: 暂不做定时刷新。** 经亲自核验 git 全历史确认定时刷新从未实现过后，用户决定暂不新建该功能。本次范围仅修手动入口（入口 1）+ 页面三步竖线轴重构。若未来需要定时刷新，在 agent scheduler 注册 job → 统一 `stream_run(app="asset-report")` 即可，单列阶段。

### 报告生成页面 UI 重构（三步竖线轴）

**现状**: 页面 `AIReportPage.vue:6-19` 用 `TaskConsole.vue`（通用执行展示，由 `useAITask.ts` 驱动）展示原始 agent 执行（thinking/工具调用/plan-steps），**非报告生成阶段**。完成后从 DB 加载结构化报告（评分环 + indicators/narrative/legacy 卡片）。

**目标布局（决策: 三步竖线轴）**:
```
┌─ PageHeader: 家庭资产体检 ─────────────┐
│                                          │
│  ● 步骤1: 报告生成（可点开/收起）          │
│  │   展开内容: AI 对应页面的交互完整内容    │
│  │   （即 TaskConsole 的 thinking/工具/    │
│  │    plan-steps 等执行流）                │
│  │                                        │
│  ● 步骤2: 模型调用 JSON（可点开/收起）     │
│  │   展开内容: 步骤2 LLM 直调生成的 JSON   │
│  │   （格式化展示，对应三步流水线的 raw_json│
│  │    即 report_structured 的 indicators） │
│  │                                        │
│  ○ 步骤3: 最终处理状态（不可点开）         │
│      仅显示状态: 成功/失败 + 落库结果       │
│                                          │
│  [完成后: 现有评分环 + indicators 卡片]    │
└──────────────────────────────────────────┘
```

**实现要点**:
- **竖线轴组件**: 复用 Vant `van-steps direction="vertical"`（全仓库仅 `DeveloperPromoPage.vue:39` 用过一次），或从 `TaskConsole.vue:51-65` 的 `console-steps` 模式提取新组件 `ReportStepTimeline.vue`。步骤1/2 可点开收起（`<van-collapse>` 或自定义），步骤3 禁用点开。
- **步骤1 内容**: 复用现有 `TaskConsole` 的执行流展示（thinking/toolSteps/planSteps）作为步骤1 的展开体——本质是把当前整页的 TaskConsole 收进步骤1 折叠面板。
- **步骤2 内容**（KTD-7 修订）: 报告前端改用 `useThreadChat` 同款 LangGraph SDK 消费 `stream_run`（不再 `useAITask` NDJSON）。步骤2 的 JSON 由同一 agent run 内 LLM `read_file` + 输出产生，经 LangGraph `custom` 事件 `report.step2_json` 透传，前端 `handleEvent` 捕获后填入步骤2 面板。
- **步骤3 内容**: 复用现有 `aiTask.status.*`（completed/failed/timeout）+ 步骤3 落库结果（`ai_reports` 写入状态）。
- **i18n**: 新增步骤标签键（`aiReport.step1/step2/step3` 等）到 `zh-CN.ts` `aiReport` 块（lines 2461-2498）+ `en-US.ts`，走 `t('key')`，不硬编码中文。
- **完成后视图**: 保留现有评分环 + indicators 卡片（`AIReportPage.vue:69-256`）作为步骤3 之下的结果区，不变。

**归属阶段**: 归入阶段 3（报告流水线），因其依赖步骤2 SSE 事件透传。

---

## 4. 实施步骤（分阶段，每阶段独立验证）

### 阶段 0: 死代码清理 + v2 命名
- [ ] ~~删 `agent_dispatch.py` 的 `stream_agent_dispatch` + `EffectiveConfigBuilder` 死代码~~ **校正**：二者均**非死代码**——`stream_agent_dispatch`（`agent_dispatch.py:198`）被 `test_agent_run_service.py` 引用且 `worker.py:129` 注释引用其逻辑；`EffectiveConfigBuilder`（`packages/core/effective_config.py:30`）被 `agent_dispatch.py:409` + `main.py:85` 调用并有 `test_effective_config.py` 单测。**本阶段不删二者**，仅做下条重命名。
- [x] `runs_stream.py:stream_run_v2` → `stream_run`（函数重命名，路由路径不变）。
- **量化验收**:
  - 残留引用数 = 0：`git grep -n "stream_run_v2"` 在改后无命中。（`stream_agent_dispatch`/`EffectiveConfigBuilder` 本阶段不删，见校正。）
  - 路由路径不变量：`/api/threads/{id}/runs/stream` 的 HTTP 状态码在重命名前后均为 200（无 307/404 回归），用 1 条端到端请求断言。
  - 测试全绿：`uv run pytest apps/agent/tests/ apps/backend/tests/` 失败数 = 0，且用例数不下降（重命名前后用例数差 = 0）。

> ⚠️ **阶段 0 勘误（评审 + 2026-07-17 live code 二次校正）**：`stream_agent_dispatch`（`agent_dispatch.py:198`）**非死函数**（有测试 + `worker.py:129` 注释引用）。`EffectiveConfigBuilder`（`packages/core/effective_config.py:30`）**也非死代码**——被 `agent_dispatch.py:409`（`config_builder = EffectiveConfigBuilder(pm)`）与 `main.py:85` 调用，且有 `test_effective_config.py` 单测。二者**均不在本阶段删除**，推迟到各自调用方迁移完成后（见阶段 4 前置）。本阶段仅做 `stream_run_v2`→`stream_run` 重命名。

### 阶段 1: worker 多应用分派
- [ ] `worker.py`: `run_family_agent` → `run_agent`，按 `record.metadata["app"]` 分派。
- [ ] 提取现有 chat 逻辑为 `_run_numina_agent`（保留 Path C 工具过滤）。
- [ ] `start_run`/`stream_run` 透传 `app` 到 `record.metadata`。
- **量化验收**:
  - app 字段透传覆盖率 = 100%：所有进入 `run_agent` 的 record 断言 `record.metadata.get("app")` 非空（缺省回退 `"numina"`），用 ≥2 条用例（numina / asset-report 各一）断言分派分支命中。
  - chat 不回归：`/ai/chat` 端到端 1 轮对话，断言响应非空、SSE 流至少产出 1 个 `token.stream` 事件、结束时 `phase=done`；与重构前同一输入的响应长度差 ≤ 10%（防行为漂移）。
  - 工具过滤不变：`active_skill_context` 过滤后可用工具集合与重构前一致（同 skill 下的 `allowed_tools` 差集 = ∅）。
  - 测试全绿：失败数 = 0。

### 阶段 2: 数鸣 SOUL 扩充 + family-* skill 合并
- [ ] 数鸣 SOUL.md 并入 4 个 family-* 的通用分析框架（scorecards/risk_flags/recommendations 方法论 + 深度研究规划步骤）。**校正**：`bootstrap/agents.py` 不存在（见 §3.3 校正），SOUL.md 落点待实现期确定（启用 `AgentTempCache` / 内联 SKILL.md / 新建 agents 配置三选一）。
- [ ] 删 4 个 family-* skill 目录（`apps/agent/skills/builtin/public/family-asset-checkup` 等）。
- [ ] `apps/backend/app/bootstrap/skills.py` 删 4 个 `_BUILTIN_SKILLS` 注册块（family-asset-checkup / family-finance-insight-planner / family-liability-review / fixed-asset-followup）。
- [ ] `apps/backend/app/constants/system_ids.py` 删 `SKILL_FAMILY_ASSET_CHECKUP_ID` / `SKILL_FAMILY_FINANCE_INSIGHT_PLANNER_ID` / `SKILL_FAMILY_LIABILITY_REVIEW_ID` / `SKILL_FIXED_ASSET_FOLLOWUP_ID` 4 个常量；`ai_skills.py` 清理相关引用（若有）。
- **量化验收**:
  - 删除残留 = 0：`git grep -n "SKILL_FAMILY_ASSET_CHECKUP_ID\|SKILL_FAMILY_LIABILITY_REVIEW_ID\|SKILL_FIXED_ASSET_FOLLOWUP_ID\|SKILL_FAMILY_FINANCE_INSIGHT_PLANNER_ID"` 命中数 = 0；4 个 skill 目录 `ls` 不存在。
  - DB 一致性：`skill_registry`（`family_id=0` 系统模板）+ `family_skills`（家庭启用）表中 `skill_id ∈ {family-asset-checkup, family-liability-review, fixed-asset-followup, family-finance-insight-planner}` 的行数在迁移后 = 0（需 Alembic 数据迁移清理，见阶段 2 风险）。
  - 对话行为不漂移：以"家庭资产体检"类输入跑 ≥3 轮 numina 对话，断言响应含 `scorecards`/`risk_flags`/`recommendations` 三类结构化键的出现率 = 100%（方法论已进 SOUL）；响应平均长度与合并前差 ≤ 20%。
  - 测试全绿：失败数 = 0。

> ⚠️ **阶段 2 勘误（评审 + 2026-07-17 live code 路径校正）**：4 个 family-* skill **已在 `apps/backend/app/bootstrap/skills.py` 注册为 trigger 模式**（`_BUILTIN_SKILLS` 列表，`input_mode: "trigger"` + 固定 Snowflake ID + `display_order`，`family_id=0` 系统模板），非文档原述"未注册"。合并进 SOUL 须同步：(1) 删 `bootstrap/skills.py` 4 个 `_BUILTIN_SKILLS` 注册块；(2) 删 `system_ids.py` 中 4 个 `SKILL_*_ID` 常量（非 `ai_skills.py`）；(3) Alembic 数据迁移清理 `skill_registry` + `family_skills` 表中引用这 4 个 `skill_id` 的行。否则留下孤儿 DB 行 + 悬挂 capability 引用。

### 阶段 3: AI 资产报告流水线 + 页面三步竖线轴 + 8h 缓存
- [ ] 新建 `asset-report` skill 目录（`skills/builtin/public/asset-report/SKILL.md`），合并 `report`/`report_generate`/`report_structured` 三 SKILL.md 为单一 prompt（步骤1 markdown 生成 + `write_file` 落盘 + 步骤2 JSON 输出指示），`allowed-tools` 含 family-data MCP + `write_file`/`read_file`。归类 = 系统内置固定流程（KTD-8）：加入 `RESERVED_NAMES`，不进 `BUILTIN_CAPABILITIES`。再删 3 个 report skill 目录。
- [ ] `worker.py` 新增 `_run_asset_report_pipeline`（三步，决策2+3）。
- [ ] backend `ai_report.py`: `proxy_report_events` 改走统一 `stream_run`（`app="asset-report"`），不再调 orchestrator（**此步找回触发入口 1**）。
- [ ] **保留**现有并发控制（`get_running_task` + `get_any_running_task` 排队），阶段 3 迁统一 `stream_run` 后仍生效。
- [ ] **新增 8h 缓存（语义 b）**: `trigger_generate_events` 入口查最新 `AIReport`，8h 内且无 `force` → 返回 `{"status":"cached",...}` JSON（不启动流）；`?force=true` 或超 8h → 现有流程。缓存检查在并发检查之前；强制刷新仍受单家庭单任务约束。**无需 Alembic migration**（用 `generated_at`+`timedelta(hours=8)` 运行时计算）。
- [ ] 前端 `useAITask.startStream` 透传 `force` 到 fetch URL；`AIHubPage`/`AIReportPage` 新增缓存命中提示态 + "强制重新生成"按钮（仅提示态显示，带 `force=true`）。
- [ ] 步骤2 在同一 agent run 内由 LLM `read_file` + 输出 JSON（不再单独调家庭 provider），新增 LangGraph `custom` 事件 `report.step2_json` 透传步骤2 的 JSON 给前端（KTD-7 修订）。
- [ ] 前端 `AIReportPage.vue`: 用 `ReportStepTimeline.vue`（Vant `van-steps direction="vertical"` 或提取自 `TaskConsole console-steps`）替换 `TaskConsole` 整页展示——步骤1 可点开（执行流，复用 TaskConsole 内容）、步骤2 可点开（格式化 JSON，捕获新 SSE 事件）、步骤3 不可点开（状态）。
- [ ] 新增 i18n 键（`zh-CN.ts` + `en-US.ts` 的 `aiReport` 块），含缓存命中提示（`cacheFresh`）+ 强制刷新（`forceRegenerate`）文案。
- **量化验收（按功能点逐条）**:

  **F1. 三步流水线端到端**
  - 端到端成功率 ≥ 95%（≥20 次生成取样，成功 = `ai_reports` 表新增 1 行 `status=completed`）。
  - 步骤产出完整性 = 100%：每次成功生成断言三件产物齐全——(a) markdown 文件落盘且文件大小 > 0 字节；(b) 步骤2 `raw_json` 经 `json_repair` 后为合法 JSON dict；(c) `ai_reports.report_json` 非空且 `overall_score` ∈ [0,100]、`data_completeness_score` ∈ [0.0,1.0]。
  - JSON schema 合规率 = 100%：`report_json` 必须含 indicators schema 全部必填键（`summary`/`scorecards`/`risk_flags`/`recommendations`），缺一键即判失败。

  **F2. markdown 审计落盘**
  - 落盘率 = 100%：成功生成时 `markdown_file_path` 非空且文件实际存在；相对路径在 tenant reports 目录下（路径遍历校验：`..` 出现次数 = 0）。
  - 文件可读回：落盘后 `read_file` 能取回内容，且内容含评分表关键标记（如 `## 评分` 或 `overall_score`）。

  **F3. 8h 缓存命中**
  - 命中判定：最新 `AIReport.generated_at` 在 8h 内 + 无 `force` → 返回 `status="cached"` JSON（非 `StreamingResponse`），Content-Type 为 `application/json`，且**不启动 NDJSON 流**（流事件数 = 0）。
  - 命中响应延迟：P95 ≤ 500ms（单次 DB latest 查询 + 序列化，无 LLM 调用）。
  - 缓存检查先于并发检查：命中路径不触达 `get_running_task`/`get_any_running_task`（用 mock 断言两者调用次数 = 0）。

  **F4. 强制刷新绕过缓存**
  - `?force=true` 时即使 `generated_at` 在 8h 内也走生成流程（返回 `StreamingResponse`，非 cached JSON）。
  - 强制刷新仍受并发约束：已有 running 报告任务时，force 请求接续而非新建（`ai_tasks` 表同 family+report 的 running 行数 ≤ 1，即重复 force 请求不产生重复任务）。

  **F5. 单家庭单任务并发不变量**
  - 并发上限 = 1：同 family 并发触发 2 次报告生成，`ai_tasks` 表中该 family 的 `status=running` 行数恒 = 1；第 2 次要么接续（返回同 task_id）要么排队（`status=queued` + 202 + `queue_position`）。
  - 跨能力排队：同 family 有 running 非报告任务时，报告任务进 `queued`（HTTP 202），不并发执行。
  - 接续正确性：接续 running 任务时不重复创建（`create_task` 调用次数增量 = 0）。

  **F6. 无 AI provider 降级**
  - 家庭无配置 provider 时，步骤2 不抛未捕获异常；返回结构化结果（`status` 标记降级 + 步骤1 markdown 仍落盘供查看），前端步骤2 面板显示"未配置 AI 供应商"提示而非空白卡死。

  **F7. 三步竖线轴交互**
  - 步骤数 = 3，步骤1/2 可展开收起（`aria-expanded` 切换），步骤3 禁用展开（点击无展开动作，`aria-disabled` 或等价）。
  - 生成中三步均可见：pending（灰）/ active / done 三态齐全，步骤1 active 时有流式进度指示（非纯空白）。
  - 步骤2 JSON 面板有界：`max-height ≤ 60vh` + `overflow-y: auto`（JSON 任意大时不撑破竖线轴布局）；含复制按钮。
  - 步骤展开/收起触控目标 ≥ 44×44px，键盘可操作（Tab 可聚焦 + Enter/Space 触发）。
  - 生成中点击步骤1 展开，可见 TaskConsole 执行流内容（thinking/toolSteps/planSteps 至少 1 类有内容时非空）。

  **F8. SSE 事件 `report.step2_json`**
  - 步骤2 完成时前端恰好收到 1 个 `report.step2_json` 事件，payload 为合法 JSON 字符串（`JSON.parse` 成功）；步骤2 未完成时该事件数 = 0。

  **F9. i18n 完整性**
  - 新增键在 `zh-CN.ts` 与 `en-US.ts` 的 `aiReport` 块下均存在（差集 = ∅）；页面无硬编码中文（`grep -nP "[\x{4e00}-\x{9fff}]" AIReportPage.vue ReportStepTimeline.vue` 在 template/逻辑区命中数 = 0，注释除外）。

  **F10. 测试全绿**：`uv run pytest apps/agent/tests/ apps/backend/tests/` 失败数 = 0，且为 F1-F8 新增 ≥8 条可断言用例（每条量化阈值至少 1 条断言）。

### 阶段 4: 删报告 skill + orchestrator skill 路径
- [ ] 删 `apps/agent/skills/builtin/public/report`、`report_generate`、`report_structured` 三个 skill 目录（其 prompt 已在阶段3 合并进新建的 `asset-report` skill 目录）。
- [ ] `apps/backend/app/bootstrap/skills.py` 删 `report` 注册块（`SKILL_REPORT_ID`）。
- [ ] `apps/backend/app/constants/system_ids.py` 删 `SKILL_REPORT_ID` 常量；`ai_skills.py:BUILTIN_CAPABILITIES` 删 `"report"`（interim 5，5 trigger skill 在阶段4.5 再删→最终 `[]`）；`ai_skills.py:RESERVED_NAMES` 加 `"asset-report"`、移除 `"time_machine"`（`["chat","time_machine"]`→`["chat","asset-report"]`，KTD-8 + KTD-9）。
- [ ] 删 `agent/routers/report.py`（阶段3 已不用）。
- [ ] 删 `Orchestrator.dispatch`（**仅** `stream_dispatch` 在 `Orchestrator` 类上不存在，6 个 router 的该调用本已死，无需删；真正要删的是 live 的 `Orchestrator.dispatch`，前提是其 8 个 caller 全部迁移）。
- [ ] 删 `ai_result_parser.py` 中 report 专用的旧 schema 分支（保留 indicators schema + json-repair 给步骤3）。
- **量化验收**:
  - report skill 残留 = 0：`git grep -n "report_generate\|report_structured\|SKILL_REPORT_ID"` 命中数 = 0（`report` 单词命中需人工甄别，排除业务语义）；3 个 skill 目录 `ls` 不存在。
  - `BUILTIN_CAPABILITIES` 基数 = 5（interim：`alerts, allocation, disposal, liability, spending_leak`，`"report"` 不在其中；5 trigger skill 在阶段4.5 删除→最终 `[]`）。
  - `ai_result_parser.py` report 旧 schema 分支删除后，indicators schema + json-repair 路径仍被阶段 3 步骤3 调用且单测通过（回归用例 ≥1 条）。
  - 无遗漏调用：`git grep -n 'capability="report"'` 在 report 相关调用点命中数 = 0。
  - **dispatch 删除前置门槛（2026-07-17 live code 校正 + KTD-9 修订，硬性）**：`Orchestrator` 类**只有 `dispatch`，无 `stream_dispatch`**。live `dispatch(...)` caller 共 9 处（report.py:28 / disposal.py:33 / allocation.py:45 / spending_leak.py:34 / import_parse.py:32 / liability.py:33 / suggest.py:40 / time_machine.py:46 / alerts.py:33）。KTD-9 后：report（阶段4）+ 5 trigger skill + time_machine（阶段4.5）的 caller **随 router 删除而消失**（非迁移），仅剩 `import_parse`/`suggest` 2 处需迁移到 `stream_run`。删 `Orchestrator.dispatch` 的前提是 `git grep -n "orchestrator\.dispatch\("` = 0。已死的 `stream_dispatch` 调用随各 router 删除自然消失。
  - 测试全绿：失败数 = 0。

> ⚠️ **阶段 4 前置约束（2026-07-17 live code 校正 + KTD-9 修订，P0）**：原"删 dispatch 会破坏 8 个在线 router"经核验**前提反了**——`Orchestrator` 从无 `stream_dispatch`，6 个 router 流式端点早已死。KTD-9 后，5 trigger skill + time_machine 的 live `dispatch` caller **随 skill 删除/router 删除而消失**（非迁移），仅 `import_parse`/`suggest` 2 处迁移。故：阶段4 删 report 专用调用点 → 阶段4.5 删 5 trigger skill + time_machine 解耦（caller 随之消失）→ 阶段5 迁 `import_parse`/`suggest` 2 caller → 删 `Orchestrator.dispatch`。

### 阶段 4.5: 删 5 外扩 trigger skill 全栈 + time_machine 解耦（KTD-9）
> 详见 plan `U7`。5 trigger skill（alerts/allocation/disposal/liability/spending_leak）全栈删除（agent router + backend router + 前端页面 + API client + DB 表 + Alembic downgrade + parser schema 块 + writer 函数 + 注册/常量 + i18n + 路由），能力回归数鸣 SOUL（补充 3 核心分析方向引导）。time_machine 解耦：删死 agent router + 移出 RESERVED_NAMES，保留纯计算应用。⚠️ `ai_allocation_targets` 用户数据 fork（KTD-9 (2)）待决断，默认 (a) 随 allocation 删除。

### 阶段 5: 迁 import_parse/suggest + 删 Orchestrator.dispatch（KTD-9 修订后）
> 阶段4（删 report）+ 阶段4.5（删 5 trigger skill + time_machine 解耦）后，live `dispatch` caller 仅剩 `import_parse.py:32` + `suggest.py:40`（二者无 skill 目录，非 16 skill 之一，是 agent router 直调 `dispatch(capability=...)` 的边缘 case）。
- [ ] **fork**：决断 import_parse/suggest 去向——(a) 迁 `stream_run` `app="numina"`（默认）；(b) 若无 live 前端调用则删 router。先 grep 前端是否调用 `/import/parse` 与 `/suggest/asset`。
- [ ] 按决断迁移或删除这 2 个 `dispatch` caller。
- [ ] `git grep -n "orchestrator\.dispatch\("` = 0 后，删 `Orchestrator.dispatch` 方法（`orchestrator.py:210`）+ `_error_response`（若仅 dispatch 用）。
- **量化验收**:
  - 迁移/删除后 `git grep -n "orchestrator\.dispatch\("` = 0（此时方可删 `Orchestrator.dispatch`）；`git grep -n "orchestrator\.stream_dispatch\("` = 0（6 死调用全消）。
  - `import_parse`/`suggest` 端点迁移后 HTTP 200（若保留）或前端无调用确认（若删除）。
  - 测试全绿：失败数 = 0。

---

## 5. 已确认决策（无需再问）
1. **skill 分类后重构（KTD-9 修订）**: B 类（4 family-*）合并进数鸣 SOUL；C 类（5 trigger skill）**删除**——能力回归数鸣 SOUL 推理，遗留页面/DB/parser/writer 全栈清理（非"保留为可移除 skill"）；A 类（3 报告）删除内联；新建 `asset-report` 系统内置固定流程（KTD-8）；`time_machine` 解耦出 skill 系统（KTD-9）。终值 5 个 skill 目录。
2. **报告步骤1 markdown 落文件**（审计用），步骤1 = LLM 调 family-data MCP + `write_file` 落 markdown。
3. **报告步骤2（KTD-7 修订）**: 同一 agent run 内 LLM `read_file` 读回 markdown + 输出 JSON（不再单独调家庭 provider），经 LangGraph `custom` 事件 `report.step2_json` 透传。
4. **8h 缓存语义（2026-07-17 已定）**: 报告触发时若最新 `AIReport.generated_at` 在 8h 内且无 `force` → 命中缓存，返回 `{"status":"cached",...}` JSON（非流），不触达并发检查；`?force=true` 或超 8h → 正常生成。不新增 DB 列（运行时 `generated_at`+`timedelta(hours=8)` 计算）。

## 6. 风险与回滚
- **阶段 1 worker 重构**: 改 /ai/chat 核心路径。缓解: 提取 `_run_numina_agent` 保持逻辑不变 + 充分测试。
- **阶段 2 SOUL 扩充**: 合并 family-* 框架可能改变数鸣输出风格。缓解: 保留原 skill 内容到 SOUL 时仅取方法论框架，不改变现有对话行为。
- **阶段 3 报告流水线**: 三步串联。缓解: 每步独立 try/except + 审计日志；步骤3 失败时保留步骤1 markdown 供排查。
- **回滚**: 每阶段独立 commit，可单独 revert。阶段 0-1 不删功能。

## 7. 验证策略

每阶段量化验收项见 §4 各阶段"**量化验收**"小节（按功能点逐条可断言）。本节为跨阶段总览。

- **测试基线**: 每阶段 `uv run pytest apps/agent/tests/ apps/backend/tests/` 失败数 = 0，且用例数不低于阶段开始前。
- **量化验收总览表**（功能正确性取向，阈值均可写进 pytest 断言）:

| 阶段 | 功能点 | 量化阈值 |
|---|---|---|
| 0 | v2 重命名 | `stream_run_v2` 残留 = 0；路由 HTTP 200 不变；用例数差 = 0（`EffectiveConfigBuilder`/`stream_agent_dispatch` 非死代码，本阶段不删） |
| 1 | worker 多应用分派 | app 字段透传覆盖率 100%；chat 响应长度差 ≤10%；工具过滤差集 = ∅ |
| 2 | SOUL 扩充 + family-* 合并 | `SKILL_*_ID` 残留 = 0；`family_skills` 孤儿行 = 0；结构化键出现率 100%；响应长度差 ≤20% |
| 3 | F1 三步流水线 | 端到端成功率 ≥95%；产物完整性 100%；schema 合规率 100% |
| 3 | F2 markdown 落盘 | 落盘率 100%；路径 `..` = 0；可读回含评分标记 |
| 3 | F3 8h 缓存命中 | 命中返回 JSON 非流，流事件数 = 0；P95 ≤500ms；不触达并发检查（调用次数 = 0） |
| 3 | F4 强制刷新绕过 | `force=true` 必走生成流；force 下重复请求 running 行数 ≤1 |
| 3 | F5 单家庭单任务并发 | 同 family running 行数恒 = 1；跨能力进 queued/202；接续不重复创建 |
| 3 | F6 无 provider 降级 | 不抛未捕获异常；步骤1 markdown 仍落盘；前端有明确提示 |
| 3 | F7 三步竖线轴 | 步骤数 = 3；1/2 可展开、3 禁用；JSON 面板 ≤60vh；触控 ≥44×44px |
| 3 | F8 SSE `report.step2_json` | 步骤2 完成时恰好 1 事件、payload 合法 JSON；未完成时 = 0 |
| 3 | F9 i18n 完整性 | zh/en 键差集 = ∅；页面硬编码中文 = 0（注释除外） |
| 4 | 删 report skill | report 残留 = 0；`BUILTIN_CAPABILITIES` 基数 = 5（interim）；`RESERVED_NAMES` = `["chat","asset-report"]` |
| 4.5 | 删 5 trigger skill + time_machine 解耦（KTD-9） | 5 skill 全栈残留 = 0；`BUILTIN_CAPABILITIES` = `[]`；6 DB 表 downgrade；`useAITask` 残留 = 0；能力回归对话通过 |
| 5 | 迁 import_parse/suggest + 删 Orchestrator.dispatch | `orchestrator\.dispatch\(` = 0；`orchestrator\.stream_dispatch\(` = 0；端点 200 不回归 |

- **手动端到端**: 阶段 1 `/ai/chat` 1 轮对话、阶段 3 报告生成全流程（含缓存命中/强制刷新/并发触发三场景）。
- **回归 grep 门槛**: 阶段 4/5 删除类操作前，相关 `git grep` 命中数必须 = 0 方可合并。

## 8. 不在本次范围
- `available_skills` 传入 DeerFlowClient（Path C 遗留，独立推进）。
- chat/chat-search 进一步系统化（`chat` 在 `RESERVED_NAMES`；`chat-search` 为普通 builtin skill，worker 按 `websearch_enabled` 选择，够用）。
- ~~阶段 5 的 5 个外扩 skill 调度迁移（可选后续）~~ → **KTD-9 改为删除**：5 trigger skill 全栈删除（非迁移），能力回归数鸣 SOUL；其 live `dispatch` caller 随 router 删除消失。阶段5 `import_parse`/`suggest` 2 caller **按调用形态分流**（2026-07-18 Resolved-10 修订，推翻原 fork (a) 统一迁 stream_run）：suggest 改轻量 LLM 单次调用（`_create_lightweight_llm`）、import_parse 重构为第 3 个 stream_run agent（U8，新增 MCP 批量写入 + 多模态），再删 `Orchestrator.dispatch`（见阶段4/4.5/5/6 前置约束）。
- **定时刷新 AI 报告**（触发入口 2）: git 全历史确认从未实现过，**用户已决定暂不做**（见 §3.5）。若未来需要，在 agent scheduler 注册 job → 统一 `stream_run(app="asset-report")`，单列阶段。
