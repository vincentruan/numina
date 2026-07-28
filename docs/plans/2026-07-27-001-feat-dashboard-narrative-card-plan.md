---
title: 仪表盘叙事卡片 - Plan
type: feat
date: 2026-07-27
topic: dashboard-narrative-card
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# 仪表盘叙事卡片 - Plan

## Goal Capsule

- **Objective:** 在仪表盘新增一张 AI 生成的月度财务叙事卡片，用 2-3 句自然语言解释"发生了什么、为什么重要"，把仪表盘从纯数字展示升级为「理解 → 行动」的信息流。
- **Product authority:** 仪表盘是用户打开 app 的第一个页面，叙事卡片在此提供上下文，帮助用户理解数字背后的故事，而不只是看到数字。
- **Execution profile:** 前端新增 DashboardNarrativeCard 组件 + 后端新增一个 LLM skill（通过 SkillRegistry）生成叙事文本，4h 缓存。
- **Stop conditions:** 叙事与教练卡职责重叠导致信息冗余；LLM 调用阻塞仪表盘渲染；叙事在无数据家庭显示空洞内容；叙事异步加载导致教练卡被推到首屏以下且用户无法感知其存在。
- **Open blockers:** 无。
- **Prerequisite:** 财务 Hub 重构 (`docs/plans/2026-07-22-001-feat-finance-hub-overview-redesign-plan.md`) 必须先完成——叙事卡片嵌入重构后的仪表盘布局。

---

## Product Contract

### Summary

新增 `DashboardNarrativeCard`：一张 LLM 驱动的叙事卡片，放在统计卡和教练卡之间，默认折叠只显示第一句摘要 + "展开"按钮，展开后显示完整 2-3 句叙事。数据来源复用现有 dashboard 端点，通过 SkillRegistry 注册的 LLM skill 生成，4h 缓存 + 数据变更主动失效。异步加载不阻塞其他卡片，骨架屏占位防跳动。AI 不可用时优雅降级为不显示。用户可关闭卡片（session 级别）。

### Problem Frame

仪表盘重构后已经有了完整的数字层（统计卡：净资产 ¥523,000、↑12%）和行动层（教练卡：建议提前还贷）。但两层之间缺少一个"理解层"——用户看到数字增长 12%，需要自己心算原因；看到教练建议还贷，不清楚当前负债率是否真的需要关注。

后端已有 `/dashboard/insights` 端点，返回 6 个结构化洞察板块（smart discoveries、goal progress、type distribution、duration distribution、retention rate、investment returns），但仪表盘从未消费这些数据。数据基础设施就绪，缺的是把它编织成一段可读的故事。

### Key Decisions

- **LLM-only for MVP.** 直接用 LLM skill 生成叙事，不先建规则层。理由：现有 SkillRegistry + AI provider 基础设施已就绪，LLM 叙事质量远高于模板填充；规则层可作为后续优化，在了解实际使用模式后再引入。
- **叙事卡放在统计卡与教练卡之间（Option C）。** 形成「数字 → 洞察 → 行动」三段式信息流。理由：叙事承接统计卡的数字提供解释，教练卡承接叙事提供建议，三者职责清晰不重叠。Governs R1, R2.
- **叙事 vs 教练卡职责分离。** 叙事只解释"发生了什么"（过去/现在），不推荐"该做什么"（未来行动）；教练卡只推荐行动，不复述叙事已解释的数据变化。Governs R6, R7.
- **复用现有数据端点，不新建聚合管道。** `/dashboard/overview` + `/dashboard/insights` 提供充足的 context 数据。理由：避免数据重复聚合，降低维护成本。Governs R3.
- **叙事异步加载不阻塞教练卡。** 叙事 LLM 调用可能耗时 1-3s，教练卡不等待叙事就绪即独立渲染。理由：引入卡片间加载依赖会增加复杂度和失败面；用户先看到行动建议后看到解释，虽非理想顺序但可接受。Governs R12.
- **用户编辑数据后主动失效叙事缓存。** 资产/负债/心愿的增删改操作触发叙事缓存失效，下次仪表盘加载时重新生成。理由：4h TTL 内用户编辑数据后叙事仍说"旧故事"，与统计卡数字不一致，破坏信任感。Governs R14.
- **叙事卡默认折叠，只显示第一句。** 折叠态 ≈ 40px，展开后显示完整叙事。理由：折叠态只占一行，不挤压教练卡首屏空间；用户主动展开才投入注意力，避免被动阅读；同时保留"展开详情"的信息深度。Governs R1, R13.

### Actors

- **A1. 家庭成员（任何角色）：** 打开仪表盘，阅读叙事卡片了解本月财务概况。叙事对所有家庭成员可见（只读）。
- **A2. LLM skill（`dashboard-narrative`）：** 接收结构化 context 数据，生成 2-3 句中文叙事文本。通过 SkillRegistry 注册，使用家庭已配置的 AI provider。

### Key Flows

- **F1. 仪表盘加载 — 叙事生成（cache miss）**
  - **Trigger:** 用户打开仪表盘，叙事缓存过期或不存在。
  - **Actors:** A1, A2
  - **Steps:**
    1. 前端渲染统计卡和其他卡片（不阻塞）。
    2. 前端在叙事卡位显示骨架屏（≈ 40px），同时异步请求叙事 API。
    3. 教练卡独立加载，不等待叙事。
    4. 后端从 `/dashboard/overview` + `/dashboard/insights` 聚合 context 数据。
    5. 后端检查数据阈值（Governs R5）——不满足则返回空。
    6. 后端调用 `dashboard-narrative` LLM skill，传入结构化 context。
    7. LLM 返回叙事文本，后端写入缓存（4h TTL）。
    8. 前端收到响应：有内容 → 骨架屏替换为叙事卡片；空响应 → 骨架屏消失，卡片不渲染。
  - **Outcome:** 叙事卡片（或空）出现在仪表盘中。教练卡可能先于叙事卡出现（可接受的加载顺序）。
  - **Covers R1, R2, R3, R4, R5, R8, R12, R16.**

- **F2. 仪表盘加载 — 叙事命中缓存（cache hit）**
  - **Trigger:** 用户打开仪表盘，叙事缓存有效。
  - **Actors:** A1
  - **Steps:**
    1. 前端异步请求叙事 API。
    2. 后端从缓存读取叙事文本，直接返回。
  - **Outcome:** 叙事卡片瞬间出现，无 LLM 调用延迟。
  - **Covers R4.**

- **F3. AI 不可用降级**
  - **Trigger:** LLM provider 不可用（熔断器开启、超时、配置缺失）。
  - **Actors:** A1
  - **Steps:**
    1. 前端请求叙事 API。
    2. 后端尝试调用 LLM skill 失败。
    3. 后端返回空响应（不报错）。
    4. 前端收到空响应，不渲染叙事卡片。
  - **Outcome:** 仪表盘正常显示其他卡片，叙事卡片静默消失。用户无感知。
  - **Covers R2.**

### Requirements

#### Narrative content

- R1. 叙事文本为 2-3 句中文自然语言，覆盖本月净资产变化方向与幅度、主要贡献因素（top asset category 或 income change）、负债变化概要。第一句必须独立成意（折叠态下单独可见即传达核心信息），总长度 ≤ 150 字。
- R2. 叙事卡片在仪表盘 DOM 顺序中位于 OverviewStatCard 之后、FinanceCoachCard 之前。当叙事为空（AI 不可用或数据不足）时，卡片不渲染，不影响其他卡片布局。
- R3. 叙事数据 source 为现有 `/dashboard/overview` 和 `/dashboard/insights` 端点的聚合数据，不引入新的数据聚合管道。

#### Data threshold

- R4. 叙事缓存 TTL 为 4 小时。缓存过期后下次请求触发重新生成。
- R5. 当家庭资产数 < 5 或历史数据 < 3 个月时，不生成叙事，卡片不渲染。阈值可配置。

#### Narrative vs Coach separation

- R6. 叙事 prompt 只包含"描述和解释"指令，不包含"建议"或"推荐"类指令。叙事文本不出现行动建议。Governs R6.
- R7. 教练卡可引用与叙事相同的数据指标，但只用于支撑行动建议，不复述叙事已解释的变化原因。

#### UX

- R8. 叙事卡片有视觉区分样式（区别于统计卡和教练卡），支持浅色/深色主题。
- R9. 叙事卡片顶部显示标签（如"本月洞察"），标识内容性质。
- R10. 移动端（≤ 428px）叙事卡片占满宽度，文本在单词/句子边界自然换行，不做单词级截断。卡片整体高度受 R13 约束。
- R11. 所有用户可见文本（标签、fallback 文案）通过 i18n key 引用，不硬编码中文。

#### Loading & async behavior

- R12. 叙事请求异步发出，不阻塞统计卡、教练卡等其他卡片的渲染。叙事加载中时，在叙事卡位显示骨架屏（高度 ≈ 40px，匹配折叠态），加载完成后替换为真实内容或隐藏（空响应时）。教练卡独立于叙事加载状态。
- R13. 叙事卡片默认折叠，折叠态只显示第一句 + 右侧"展开"按钮（高度 ≈ 40px）。点击展开显示完整叙事 + "收起"按钮，动画过渡。展开/折叠状态不持久化，每次进入仪表盘重置为折叠态。

#### Cache invalidation

- R14. 用户通过 app 内操作（新增/编辑/删除资产、负债、心愿）后，叙事缓存主动失效。下次仪表盘加载时触发重新生成。外部直接修改数据库不触发失效，依赖 4h TTL 兜底。

#### User control

- R15. 叙事卡片右上角提供关闭按钮（×），点击后卡片以动画收起，本次会话不再显示（sessionStorage 标记）。关闭不持久化——下次 app 冷启动后叙事卡重新出现。
- R16. `DashboardSkeleton` 骨架屏为叙事卡预留空间（一个短骨架条，高度匹配折叠态 ≈ 40px，位于统计卡和教练卡对应位置之间）。

### Acceptance Examples

- AE1. 典型活跃家庭（15 资产，3 负债，6 个月历史）
  - **Given:** 家庭有净资产 ¥523,000，环比 +12%，基金组合贡献最大增长，负债率 33%。
  - **When:** 用户打开仪表盘，叙事缓存过期。
  - **Then:** 叙事卡片以折叠态出现，显示第一句「你的净资产本月增长 12%，主要来自基金组合的稳健回报（+¥28,000）。」右侧有"展开"按钮。卡片位于统计卡下方、教练卡上方。折叠态高度 ≈ 40px，教练卡仍在首屏可见。

- AE1b. 展开叙事卡片
  - **Given:** AE1 的叙事卡处于折叠态。
  - **When:** 用户点击"展开"按钮。
  - **Then:** 卡片以动画展开，显示完整叙事：「你的净资产本月增长 12%，主要来自基金组合的稳健回报（+¥28,000）。同时，房贷正常还款使负债率降至 33%，处于健康区间。」"展开"变为"收起"按钮。再次点击收起回折叠态。

- AE2. 新注册家庭（2 资产，0 负债，1 个月历史）
  - **Given:** 家庭刚注册，资产数 2，历史数据 1 个月。
  - **When:** 用户打开仪表盘。
  - **Then:** 叙事卡片不渲染。仪表盘显示统计卡 → 教练卡 → 提醒 → Top-3，无叙事卡片，无空白占位。

- AE3. AI provider 不可用
  - **Given:** 家庭数据充足但 LLM provider 熔断器处于 open 状态。
  - **When:** 用户打开仪表盘。
  - **Then:** 叙事 API 返回空，叙事卡片不渲染。仪表盘其余部分正常显示。

- AE4. 阈值警告场景
  - **Given:** 家庭负债率 55%，超过健康阈值。
  - **When:** 叙事生成。
  - **Then:** 叙事提及负债率（如「负债率目前为 55%，高于健康区间」），但不包含行动建议（如「建议提前还贷」属于教练卡职责）。

- AE5. 异步加载时序 — 教练卡先于叙事卡
  - **Given:** 叙事缓存过期，LLM 调用需要 2s；教练卡数据已就绪。
  - **When:** 用户打开仪表盘。
  - **Then:** 统计卡立即显示 → 叙事卡位显示骨架屏 → 教练卡 0.5s 后出现（独立于叙事）→ 叙事卡 2s 后替换骨架屏。最终顺序：统计卡 → 叙事卡 → 教练卡。中间过程中教练卡可能先出现。

- AE6. 用户编辑数据后缓存失效
  - **Given:** 叙事缓存有效（2h 前生成），用户新增一笔 ¥50,000 定期存款。
  - **When:** 用户返回仪表盘。
  - **Then:** 叙事缓存已失效，触发重新生成。新叙事反映最新的资产构成。统计卡数字与叙事内容一致。

- AE7. 用户关闭叙事卡
  - **Given:** 叙事卡片正在显示。
  - **When:** 用户点击右上角 × 按钮。
  - **Then:** 叙事卡以动画收起（高度渐变为 0），其余卡片上移填充空间。本次会话（tab 关闭前）叙事卡不再出现。下次冷启动后叙事卡重新显示。

### Scope Boundaries

**Deferred for later:**
- 逐资产叙事（per-asset AI advocate 注解）
- 前瞻性预测（"按当前节奏，6 个月后净资产将达到…"）
- 调度器预生成（scheduler worker 定期刷新叙事缓存）
- 交互式"展开详情"下钻（叙事卡片点击展开完整分析）
- 规则检测层（hybrid approach — rules detect + LLM narrate）

**Outside this product's identity:**
- 叙事内容编辑/自定义（用户不能修改叙事文案）
- 多语言叙事（v1 仅中文，后续 i18n 框架已就绪可扩展）
- 叙事分享（导出/分享叙事文本给其他家庭成员以外的人）

### Dependencies / Assumptions

**Dependencies:**
- 财务 Hub 重构 (`docs/plans/2026-07-22-001-feat-finance-hub-overview-redesign-plan.md`) 已完成——叙事卡片依赖重构后的仪表盘布局（OverviewStatCard + FinanceCoachCard 的相对位置已确定）。
- `/dashboard/overview` 和 `/dashboard/insights` 端点可用且返回充足数据。
- SkillRegistry 基础设施可用（commit eb0c7851 后的版本）。

**Assumptions:**
- `/dashboard/insights` 端点返回的 structured signals（smart discoveries、retention rate 等）足以作为 LLM context 生成有意义的叙事。
- 4h 缓存 TTL 在实际使用中提供合理的成本/新鲜度平衡。
- 家庭配置的 AI provider 能处理 ~200 token input + ~100 token output 的轻量请求。

### Outstanding Questions

- **Resolve Before Planning:** 无。
- **Deferred to Planning:** 无——所有问题已在 Planning Contract 和 Implementation Units 中解决。

---

## Planning Contract

### Key Technical Decisions

KTD1. **Extend the FinanceCoachCard/WishAdviceCard pattern — not introduce a new abstraction.** The narrative card reuses the established AI card infrastructure: cookie-auth fetch with `credentials:'include'`, bare `JSONResponse` (not EnvelopeResponse-wrapped), `AIReport` table-based skill cache with `skill_id`-scoped TTL, and `invalidate_skill()` for CRUD hooks. Rationale: three existing AI cards already share this pattern; diverging would create a fourth parallel implementation with no benefit. Governs R3, R4, R12, R14.

KTD2. **Full agent dispatch via `worker.run_agent(app="dashboard-narrative")` for LLM generation.** The brainstorm decided to use SkillRegistry, which requires the full dispatch chain: SKILL.md definition, worker dispatch branch, gateway allowlist entry, and `RESERVED_NAMES` registration. Rationale: lightweight LLM (`_create_lightweight_llm`) bypasses SkillRegistry and would not support per-family skill configuration or future MCP tool access. Governs R3.

KTD3. **CRUD invalidation + `?force=true` refresh.** Cache is invalidated via `invalidate_skill(db, family_id, "dashboard-narrative")` at all asset/liability/wish write sites (mirroring existing `"finance_coach"` invalidation). The endpoint also accepts `?force=true` to bypass cache, matching FinanceCoachCard's refresh pattern. Rationale: CRUD hooks handle app-internal edits; `force=true` handles edge cases (external DB edits, manual refresh). Governs R14.

KTD4. **Card-level loading state, independent of dashboard NProgress.** The narrative card manages its own skeleton/loading state via component-internal refs. It does not participate in the dashboard's `usePageLoading` `increment()/decrement()` cycle. Rationale: the narrative LLM call may take 1-3s; blocking the dashboard loading bar would delay the entire page perceived-load. Governs R12.

KTD5. **Per-family scope (not per-user).** Cache key is `family_id`-scoped. The narrative describes the family's financial picture, visible to all family members. Currency annotation in the LLM prompt uses the family's default currency from the overview data. Rationale: narrative content is about shared family assets, not individual user data. Governs R1, R4.

KTD6. **CSS variables + `[data-theme='dark']` overrides for card styling.** No inline styles for themed properties. The card uses `var(--card-bg)`, `var(--text-primary)`, `var(--text-secondary)`, and accent variables consistent with existing dashboard cards. A subtle visual distinction (e.g., left border accent or gradient tint) differentiates it from stat and coach cards. Governs R8.

---

### Implementation Units

#### U1. Backend narrative endpoint + cache

- **Goal:** Add `GET /api/v1/dashboard/narrative` endpoint that returns cached or freshly-generated narrative text, with threshold checks and graceful degradation.
- **Requirements:** R1, R2, R3, R4, R5, R8, R14
- **Files:**
  - `server/apps/backend/app/routers/dashboard.py` — add `GET /narrative` route
  - `server/apps/backend/app/schemas/dashboard.py` — add `NarrativeResponse` schema
  - `server/apps/backend/app/services/dashboard_narrative.py` — new service: threshold check, context aggregation, agent dispatch, cache read/write
- **Approach:**
  - Route: `@router.get("/narrative")` with `require_adult` dependency, optional `force: bool = Query(False)`
  - Response schema: `NarrativeResponse(BaseModel)` with `narrative: str | None`, `first_sentence: str` (required — backend must extract from narrative; fallback: split on first `。！？` or truncate to 50 chars + `…`), `generated_at: datetime | None`
  - Service logic: (1) check cache via `latest_by_skill(db, family_id, "dashboard-narrative")`; (2) if fresh and not `force`, return cached; (3) call `get_overview` + `get_insights` to build context; (4) check threshold (asset_count >= 5, snapshot history >= 3 months); (5) if below threshold, return empty; (6) dispatch via `AgentClient.stream` to `dashboard-narrative` app; (7) parse result from SSE stream; (8) persist via `upsert_skill_result`; (9) return narrative + first_sentence
  - Add `"dashboard-narrative"` to `SKILL_TTL` dict with `timedelta(hours=4)`
  - Error handling: catch agent dispatch failures, return `NarrativeResponse(narrative=None)` silently
- **Patterns:**
  - Mirror `finance_coach_cache.py` cache pattern (reuse `latest_by_skill`, `is_cache_fresh`, `upsert_skill_result`, `invalidate_skill`)
  - Mirror `app/routers/ai_finance_coach.py` endpoint pattern (cookie-auth, bare JSONResponse, AgentClient.stream)
  - Use `aiter_lines()` for reliable stream termination
- **Test Scenarios:**
  - T1.1: Cache hit returns cached narrative without LLM call
  - T1.2: Cache miss triggers agent dispatch and persists result
  - T1.3: Below threshold (asset_count < 5) returns `narrative=None`
  - T1.4: Below threshold (history < 3 months) returns `narrative=None`
  - T1.5: Agent dispatch failure returns `narrative=None` silently (no 500)
  - T1.6: `?force=true` bypasses cache and regenerates
  - T1.7: Response schema serializes correctly
- **Verification:** `uv run pytest tests/backend/ -v -k "narrative"` — all scenarios pass
- **Dependencies:** None (can start immediately)

---

#### U2. Agent skill registration + worker dispatch

- **Goal:** Register `dashboard-narrative` as a SkillRegistry builtin skill with worker dispatch, gateway allowlist, and reserved name protection.
- **Requirements:** R1, R6, R7
- **Files:**
  - `server/apps/agent/skills/builtin/public/dashboard-narrative/SKILL.md` — skill definition with prompt, allowed-tools
  - `server/apps/agent/services/runtime/worker.py` — add dispatch branch for `dashboard-narrative`
  - `server/apps/agent/app/routers/gateway.py` — add to allowlist
  - `server/apps/backend/app/routers/ai_skills.py` — add `"dashboard-narrative"` to `RESERVED_NAMES`
  - `server/apps/agent/services/runtime/bootstrap/agents.py` — register agent spec
  - `server/apps/backend/app/constants/system_ids.py` — add skill ID constant
- **Approach:**
  - SKILL.md: DeerFlow skill frontmatter with `allowed-tools: []` (pure inference, no MCP tools needed — context is passed directly from backend)
  - System prompt: instruct LLM to generate 2-3 sentences explaining financial context; explicitly forbid recommendations or action suggestions (R6); first sentence must stand alone ≤150 chars
  - Context injection: backend builds a structured JSON context from overview + insights data, passes as user message to the agent
  - Worker dispatch: new `_run_dashboard_narrative_agent` function, mirroring `_run_finance_coach_agent`
  - Gateway: add `"dashboard-narrative"` to the allowed app list
  - Reserved names: `RESERVED_NAMES = ["chat", "asset-report", "import-parse", "finance-coach", "dashboard-narrative"]`
  - Multi-currency: context includes currency-annotated amounts (e.g., "net_worth: 523000 CNY") so LLM generates correct currency references
- **Patterns:**
  - Mirror `finance-coach` SKILL.md structure (allowed-tools, thinking, max_tokens)
  - Mirror worker dispatch pattern (metadata-based routing via `app` field)
  - XML delimiter injection defense for user-controlled data (asset names, wish names) in context
- **Test Scenarios:**
  - T2.1: SKILL.md validates against DeerFlow skill schema
  - T2.2: Worker dispatch routes `app="dashboard-narrative"` to correct handler
  - T2.3: Gateway rejects unauthenticated calls for `dashboard-narrative`
  - T2.4: `RESERVED_NAMES` prevents owner from creating custom skill with same ID
  - T2.5: LLM output contains no action recommendations (keyword check for "建议", "推荐", "应该")
- **Verification:** `uv run pytest tests/ -v -k "dashboard_narrative"` — all scenarios pass; `uv run ruff check apps/agent/` clean
- **Dependencies:** None (parallel with U1)

---

#### U3. CRUD cache invalidation hooks

- **Goal:** Add `invalidate_skill(db, family_id, "dashboard-narrative")` at all asset/liability/wish write sites, mirroring existing `"finance_coach"` invalidation.
- **Requirements:** R14
- **Files:**
  - `server/apps/backend/app/services/asset.py` — add invalidation at 7 existing sites
  - `server/apps/backend/app/services/liability.py` — add invalidation at 4 existing sites
  - `server/apps/backend/app/services/wish.py` — add invalidation at 5 existing sites
  - `server/apps/backend/app/services/wish_savings.py` — add invalidation at 2 existing sites
- **Approach:**
  - At each site where `invalidate_skill(db, user.family_id, "finance_coach")` is called, add a second call: `invalidate_skill(db, user.family_id, "dashboard-narrative")`. Total: 18 new calls across 4 files (asset: 7, liability: 4, wish: 5, wish_savings: 2).
  - No new import needed — `invalidate_skill` is already imported at each file
  - Batch operations (e.g., asset batch archive) trigger a single invalidation, not per-item
- **Patterns:**
  - Exact mirror of existing `finance_coach` invalidation pattern
  - Invalidation completeness: enumerate ALL write paths before shipping
- **Test Scenarios:**
  - T3.1: After `create_asset`, `latest_by_skill("dashboard-narrative")` returns None (cache cleared)
  - T3.2: After `update_liability`, cache invalidated
  - T3.3: After `create_wish`, cache invalidated
  - T3.4: After batch archive, cache invalidated (single call)
  - T3.5: Invalidation is idempotent (calling on already-empty cache is no-op)
- **Verification:** `uv run pytest tests/backend/ -v -k "invalidate"` — all scenarios pass
- **Dependencies:** U1 (needs `dashboard-narrative` skill_id registered)

---

#### U4. Frontend DashboardNarrativeCard component + page integration

- **Goal:** Create the `DashboardNarrativeCard` Vue component with collapse/expand, close, skeleton loading, silent hide on empty, and integrate it into DashboardPage between OverviewStatCard and FinanceCoachCard.
- **Requirements:** R1, R2, R8, R9, R10, R11, R12, R13, R15, R16
- **Files:**
  - `frontend/apps/main/src/components/dashboard/DashboardNarrativeCard.vue` — new component
  - `frontend/apps/main/src/pages/DashboardPage.vue` — insert card between OverviewStatCard and FinanceCoachCard
  - `frontend/apps/main/src/components/dashboard/DashboardSkeleton.vue` — add narrative skeleton placeholder
  - `frontend/apps/main/src/api/ai.ts` — add `getNarrative(force?)` API function (alongside existing `getFinanceCoach`)
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add `dashboard.narrative.*` keys
  - `frontend/apps/main/src/i18n/locales/en-US.ts` — add `dashboard.narrative.*` keys
- **Approach:**
  - **API function:** `getNarrative(force = false)` in `api/dashboard.ts` — uses cookie-auth `fetch` with `credentials:'include'`, mirroring `getFinanceCoach()`. Returns `NarrativeResponse` type.
  - **Component state:** `loading: ref(true)`, `narrative: ref<string | null>(null)`, `firstSentence: ref<string | null>(null)`, `expanded: ref(false)`, `dismissed: ref(false)`
  - **Lifecycle:** `onMounted` calls `load()`. Does NOT participate in dashboard `increment()/decrement()`. Uses own `loading` ref for skeleton toggle.
  - **Collapse/expand:** `expanded` ref toggles between first-sentence-only and full narrative. CSS transition on `max-height` for smooth animation (duration ~250ms, ease-in-out).
  - **Close button:** `×` icon top-right. On click: set `dismissed = true`, write `sessionStorage.setItem('narrative_dismissed', '1')`. On mount: check `sessionStorage.getItem('narrative_dismissed')` — if set, skip loading entirely.
  - **Silent hide:** If API returns `narrative: null` or request fails, set `narrative = null` and render nothing (component root is `v-if="narrative && !dismissed"`).
  - **Skeleton:** While `loading && !narrative`, render a skeleton placeholder (~40px height, matching collapsed state) with `van-skeleton :row="1"`.
  - **Page integration:** In `DashboardPage.vue`, insert `<DashboardNarrativeCard />` between the hero-section closing tag and `<FinanceCoachCard />`.
  - **DashboardSkeleton:** Add a skeleton card between overview and coach skeleton sections — a short bar ~40px with `van-skeleton :row="1"`.
  - **Styling:** CSS variables (`var(--card-bg)`, `var(--text-primary)`, etc.), `[data-theme='dark']` overrides, subtle left-border accent (`border-left: 3px solid var(--color-primary)`) for visual distinction.
  - **i18n keys:** `dashboard.narrative.title` ("本月洞察"), `dashboard.narrative.expand` ("展开"), `dashboard.narrative.collapse` ("收起"), `dashboard.narrative.ariaLabel` ("财务叙事卡片")
- **Patterns:**
  - Mirror `FinanceCoachCard.vue` fetch pattern (cookie-auth, silent hide, skeleton)
  - Mirror `SmartRemindersCard.vue` collapse pattern (van-collapse or custom toggle)
  - KeepAlive `hasActivated` guard: DashboardPage already has it; the card's own `onMounted` fires once per mount, no double-fetch concern
  - Dark mode: CSS variables only, semantic modifier classes, no inline styles
- **Test Scenarios:**
  - T4.1: Component renders skeleton while loading
  - T4.2: Component renders narrative text when API returns data
  - T4.3: Component renders nothing when API returns `narrative: null`
  - T4.4: Component renders nothing when API request fails
  - T4.5: Collapse shows only first sentence + "展开" button
  - T4.6: Expand shows full narrative + "收起" button
  - T4.7: Close button hides card and sets sessionStorage
  - T4.8: On remount with sessionStorage set, component does not render
  - T4.9: DOM order is stat → narrative → coach
  - T4.10: i18n keys resolve correctly in both zh-CN and en-US
- **Verification:** `cd frontend/apps/main && pnpm typecheck && pnpm test:run` — 0 errors, all tests pass
- **Dependencies:** U1 (needs backend endpoint available)

---

## Verification Contract

| Gate | Command | Scope | Pass criteria |
|------|---------|-------|---------------|
| Backend tests | `uv run pytest tests/backend/ -v -k "narrative"` | U1, U3 | All narrative + invalidation tests pass |
| Agent tests | `uv run pytest tests/ -v -k "dashboard_narrative"` | U2 | Skill registration + dispatch tests pass |
| Backend lint | `uv run ruff check apps/backend/ apps/agent/` | U1, U2, U3 | 0 errors |
| Backend typecheck | `uv run mypy apps/backend/` | U1, U3 | 0 errors |
| Frontend typecheck | `cd frontend/apps/main && pnpm typecheck` | U4 | 0 errors |
| Frontend tests | `cd frontend/apps/main && pnpm test:run` | U4 | All tests pass, 0 regressions |
| Frontend lint | `cd frontend/apps/main && pnpm lint` | U4 | 0 new errors |

---

## Definition of Done

- All 4 Implementation Units verified (verification commands pass)
- R1-R16 requirements covered by at least one test scenario
- Narrative card renders in correct DOM order (stat → narrative → coach) on DashboardPage
- Collapse/expand animation smooth (no layout jump)
- Dark mode: card colors correct in both light and dark themes
- i18n: all UI strings resolved via `t()` keys, no hardcoded Chinese in `.vue` or `.ts`
- Cache invalidation: editing an asset/liability/wish causes next dashboard load to regenerate narrative
- Silent degradation: AI unavailable → card hidden, no error toast, no layout gap
- `DashboardSkeleton` reserves space for narrative card
- Close button: sessionStorage persistence works across page navigations within session; cold start resets
- No speculative code beyond what R1-R16 require
- Clean git status (no dead code, no TODO placeholders)
