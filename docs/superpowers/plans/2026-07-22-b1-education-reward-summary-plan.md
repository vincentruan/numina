# B1 真实资金（专项支出统计）— Implementation Plan

> **状态**：complete（2026-07-22 实现并验证）
> **日期**：2026-07-22
> **父文档**：[2026-07-22-b1-education-linkage-plan.md](./2026-07-22-b1-education-linkage-plan.md) §Deferred（真实资金扣款 fork 2/3 完整版）+ [2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md) §3 域5 B1
> **范围**：B1 真实资金的**方案 B（专项支出统计）**——新增「教育奖励支出」汇总：后端聚合 `education_reward` Activity（累计 + 本月 + 笔数），前端 FinanceHub 加一张统计卡片。**不动资产、不进净资产、不进 D8 收益率、不扣星币**。
> **决策**：方案 B（专项支出统计，不扣资产）；B-1 累计+本月按 family 聚合；B-2 FinanceHub 小卡片；B-3 不扣星币；B-4 累计+本月不做自定义区间（均已确认 2026-07-22）。
> **侦察依据**：B1 真实资金 scout（2026-07-22）。

---

## Product Decision（已确认 2026-07-22）

### 根本语义：方案 B（专项支出统计）

| 候选 | 决策 | 理由 |
|---|---|---|
| A 真扣资产余额 | ❌ | Numina 是估值系统无现金流账户；扣 `current_value` 经 `update_asset_value` 会触发 AssetValuation 重估值历史、**污染 D8 interval/annualized 收益率**、真实减少净资产——语义别扭且副作用硬伤 |
| **B 专项支出统计** | ✅ | 不动资产；聚合 `education_reward` Activity 求和，给家长「累计/本月已承诺奖励」可视化。fork 4（进 dashboard）的合理扩展：从「仅活动流」升级为「活动流 + 汇总卡片」。零污染 |
| C 不做关闭方向 | ❌ | Activity 流水已可溯，但汇总卡片有明确家长可视化价值，成本可控 |

### 实现 fork（B-1~B-4，均按推荐确认）

| # | fork | 决策 |
|---|------|------|
| B-1 | 统计口径 | **累计总额 + 本月总额 + 笔数**，按 family 聚合 `type='education_reward'` 的 Activity.amount |
| B-2 | 展示位置 | **FinanceHubPage overview card 下方一张小卡片**（复用现有卡片 + MoneyDisplay 模式） |
| B-3 | 是否扣星币 | **不扣**（星币是儿童虚拟经济独立运行）；仅统计元金额 |
| B-4 | 时间范围 | **累计 + 本月**，不做自定义区间（够用） |

---

## Goal Capsule

**一句话**：新增「教育奖励支出」专项统计——后端 `GET /dashboard/education-reward-summary` 聚合 family 的 `education_reward` Activity（累计/本月/笔数），前端 FinanceHub overview card 下方加一张统计卡片展示，让家长看到「已承诺奖励 X 元（本月 Y 元，共 Z 笔）」，不动资产、不进净资产、不污染收益率。

**为什么**：B1 真实资金的产品意图是让家长知晓教育奖励的真实货币支出规模。方案 B 用最低成本给出这个信息，避开方案 A 在估值系统里扣款的语义错误与收益率/净资产污染。数据源（`education_reward` Activity）已由 B1 教育联动写入，本批只是聚合 + 展示，无新写入路径。

**完成标准**：后端端点返回累计/本月/笔数（开关关闭或无数据时返回 0 而非报错）；前端卡片展示 3 个数字 + i18n 双 locale；后端 pytest 覆盖（无数据/累计/本月边界/多笔聚合）；前端 vitest 卡片渲染；`pytest`/`typecheck`/`ruff`/`mypy` + `pnpm typecheck`/`test:run`/`lint` 不新增失败。

---

## Scout 结论（已确认，勿重复侦察）

### 后端
- **Activity 模型**（`models/activity.py`）：`family_id`(BigInt) / `user_id` / `type`(String 30) / `entity_type` / `entity_id`(BigInt) / `title` / `amount`(Float|None) / `created_at`(DateTime, server_default=func.now())。B1 写入 `type='education_reward'`, `entity_type='chore'`, `amount=元值`(float)。
- **独立 dashboard 端点模式**（镜像）：`routers/dashboard.py:79` `@router.get("/investment-returns", response_model=list[InvestmentReturnItem])` → `dashboard_service.get_investment_returns(db, user)`。本批新增 `@router.get("/education-reward-summary", response_model=EducationRewardSummaryResponse)`。
- **聚合模式**：`func.coalesce(func.sum(...), 0)`（dashboard.py:393/450 已有）。月份边界：`created_at >= date(today.year, today.month, 1)`。
- **schema**：`schemas/dashboard.py` 新增 `EducationRewardSummaryResponse(SnowflakeBase)`：`total: float` / `month_total: float` / `count: int`。（amount 是 Float 快照，直接求和；无货币换算——education_reward 写入时已是 CNY 元值，与 family 默认币种一致假设，见 KTD-1。）

### 前端
- **api**：`api/dashboard.ts` 镜像 `getInvestmentReturns`（:143 `http.get<...>('/dashboard/investment-returns')`）→ 新增 `getEducationRewardSummary()` → `http.get<EducationRewardSummary>('/dashboard/education-reward-summary')`。
- **store**：`stores/dashboard.ts` 镜像 `investmentReturns = ref(...)` + `fetchInvestmentReturns()`（:26/:96）→ 新增 `educationRewardSummary = ref<EducationRewardSummary|null>(null)` + `fetchEducationRewardSummary()`，挂进 `fetchAll`（:135 现 `Promise.all([fetchOverview(), fetchStatesSummary()])`）。
- **FinanceHubPage**：overview card（`.finance-overview-card` :18-56）下方、`debt-wish-hint`(:59) 之前/之后加一张小卡片。用 `MoneyDisplay`（已 import :100）展示金额。数据来自 `dashboardStore.educationRewardSummary`。
- **types**：`types/index.ts` 新增 `EducationRewardSummary` 接口（`total: number; month_total: number; count: number`）。
- **i18n**：`financeHub.*` 下加 `educationReward`/`educationRewardTotal`/`educationRewardMonth`/`educationRewardCount`（zh+en）。

---

## KTD（Key Technical Decisions）

- **KTD-1（无货币换算）**：`education_reward` Activity.amount 在 B1 写入时是 `coin_reward × coin_to_yuan_rate` 的**元值（默认币种）**，非多币种资产。故聚合直接 `func.sum(amount)`，**不走 ExchangeRateService**（与 investment_returns 多币种资产不同）。若 family 默认币种变化，历史 Activity 不追溯（与 Activity 快照语义一致，memory [[paymentrecord-numeric-activity-float-decision]]）。
- **KTD-2（空数据返回 0 不报错）**：开关关闭/无 education_reward 记录时，返回 `{total:0, month_total:0, count:0}`，前端卡片据此显示「暂无教育奖励支出」或隐藏。不用 404/empty error（与 states-summary 等聚合端点一致）。
- **KTD-3（本月边界）**：`month_start = date(today.year, today.month, 1)`，`Activity.created_at >= month_start`。用 server 本地日期（与 B1 写入 created_at server_default 一致，同时区）。
- **KTD-4（卡片展示策略）**：`count === 0` 时卡片显示「暂无教育奖励支出」（i18n empty 文案），仍渲染卡片占位（避免布局跳动）；有数据时显示 累计/本月/笔数 三行或一行三栏。**决策：一行三栏紧凑卡片**（累计 | 本月 | 笔数），镜像 overview card 的 ov-row 模式。
- **KTD-5（不污染现有聚合）**：端点独立于 `get_overview`，不进净资产/分配/trend。`get_insights` 也不加（那是洞悉 Tab，B-2 决策挂 FinanceHub）。

---

## Tasks

### B1F-a（后端：schema + service + router + 测试，small-medium）
- `schemas/dashboard.py`：`EducationRewardSummaryResponse(SnowflakeBase)`：`total: float` / `month_total: float` / `count: int`。
- `services/dashboard.py`：`get_education_reward_summary(db, user) -> EducationRewardSummaryResponse`：
  - `base = db.query(func.coalesce(func.sum(Activity.amount), 0), func.count(Activity.id)).filter(Activity.family_id==user.family_id, Activity.type=='education_reward')`
  - 本月：追加 `Activity.created_at >= month_start`（KTD-3）单独求 sum。
  - 返回 `{total, month_total, count}`（total/count 全时段，month_total 本月）。
- `routers/dashboard.py`：`@router.get("/education-reward-summary", response_model=EducationRewardSummaryResponse)` → service。
- 测试 `tests/backend/test_dashboard.py`：
  - 无 education_reward → 全 0。
  - 写 2 笔 education_reward（1 笔本月、1 笔上月——上月用直接 `Activity(created_at=上月)` 构造）→ total=两笔和、month_total=本月笔、count=2。
  - 其他 type 的 Activity 不计入。
  - family 隔离：他 family 的 education_reward 不计入。

### B1F-b（前端：types + api + store + FinanceHub 卡片 + i18n + 测试，medium）
- `types/index.ts`：`EducationRewardSummary` 接口。
- `api/dashboard.ts`：`getEducationRewardSummary()`。
- `stores/dashboard.ts`：`educationRewardSummary` ref + `fetchEducationRewardSummary()` + 挂 `fetchAll` + `invalidateDashboard` 清理（:308 区域）。
- `FinanceHubPage.vue`：overview card 下方小卡片（一行三栏：累计|本月|笔数），`count===0` 显示 empty 文案。用 MoneyDisplay + i18n。
- `i18n zh-CN.ts + en-US.ts`：`financeHub.educationReward`（卡片标题「教育奖励支出」）+ `educationRewardTotal`（累计）+ `educationRewardMonth`（本月）+ `educationRewardCount`（{count} 笔）+ `educationRewardEmpty`（暂无教育奖励支出）。
- 测试 `pages/__tests__/FinanceHubPage.spec.ts`：扩展 mock dashboard store 加 `educationRewardSummary`，断言卡片渲染累计/本月/笔数 + empty 态。（该 spec 已有 useCurrency mock + store mock 模式，复用。）

---

## 验证

- 后端：`cd server && uv run pytest tests/backend/test_dashboard.py -v`（新增 4 测试全过，无回归）；`uv run ruff check apps/backend/`；`uv run mypy apps/backend/`（scope）。
- 前端：`cd frontend/apps/main && pnpm typecheck`（0）；`pnpm test:run`（基线 968 + 1 预存 InputBox TDZ，新增 FinanceHub 测试过）；`npx eslint` 触碰文件（0 新增）。
- 逻辑走查：B1 教育联动开关开 + 审批 1 笔 10 星币（rate=2）→ Activity amount=20 → 端点 total=20/count=1；卡片显示累计 ¥20。

---

## Deferred / Open Questions

- **真实扣资产（方案 A）**：已否决（估值系统语义 + 收益率/净资产污染）。永久 deferred，除非引入真正的现金流账户概念（那是另一个大功能）。
- **进净资产/分配**：B 方案明确不做（保持净资产纯净）。
- **自定义时间区间**：B-4 决策累计+本月够用；若需区间，独立后续。
- **per-child 拆分**：本批 family 级汇总；若需按孩子拆分奖励支出，需 Activity 关联 child（现 entity_id=instance_id 可追溯但需 join），独立后续。

---

## 实现备注（2026-07-22 完成）

- **后端**：
  - `schemas/dashboard.py:89` `EducationRewardSummaryResponse(SnowflakeBase)`：`total/month_total: float` + `count: int`。
  - `services/dashboard.py:389` `get_education_reward_summary(db, user)`：两次查询——全时段 `func.coalesce(func.sum(amount),0).label("total")` + `func.count(id).label("cnt")`（filter family_id+type='education_reward'）；本月追加 `created_at >= date(today.year,today.month,1)` 求 month_total（`.scalar()`）。`cnt` label 命名避免与 `func.count` callable 的 mypy row-attr 冲突。无货币换算（KTD-1），无记录返回 0（KTD-2）。
  - `routers/dashboard.py:88` `@router.get("/education-reward-summary", response_model=EducationRewardSummaryResponse)`（require_adult）。
  - `tests/backend/test_dashboard.py` +4 测试 + 2 helper（`_current_user`/`_add_education_reward`）：empty→zeros / total+month+count 含月边界 / 他 type 排除 / family 隔离。
- **前端**：
  - `types/index.ts` `EducationRewardSummary`；`api/dashboard.ts` `getEducationRewardSummary()`；`stores/dashboard.ts` `educationRewardSummary` ref + `fetchEducationRewardSummary()`（try/catch non-critical）挂 `fetchAll` Phase 2 + `invalidateDashboard` 清理 + 双导出。
  - `FinanceHubPage.vue:59` overview card 下方 `.education-reward-card`（debt-wish-hint 前）：一行三栏（累计|本月 MoneyDisplay + 笔数），`count===0` 显示 empty 占位（KTD-4 防布局跳动）。`.er-*` scoped 样式。
  - i18n zh+en 各 5 key（`financeHub.educationReward/educationRewardTotal/educationRewardMonth/educationRewardCount/educationRewardEmpty`）。
  - `FinanceHubPage.spec.ts` 扩展 dashboard-store mock + 3 测试。
- **验证**：后端 `test_dashboard.py` 45 passed（41 存 + 4 新）/ `test_chores.py -k education_reward` 6 passed（B1 写入路径完好）；ruff 266 baseline = 266（0 新增，修一处自引入 I001 import 排序）；mypy `services/dashboard.py` 39 baseline = 39（0 新增，cnt label 消除 2 个本将新增错误）。前端 typecheck 0 / vitest 971 passed + 1 预存 InputBox TDZ（968 基线 + 3 新）/ eslint 触碰 7 文件 0 错 1 预存警（stores/dashboard.ts:3 showToast 未用，改动前已存在）。
- **注意**：工作区出现一个未跟踪文件 `docs/plans/2026-07-22-001-feat-finance-hub-overview-redesign-plan.md`（ce-brainstorm 工作流产物，`docs/plans/` 非 `docs/superpowers/plans/`），与本批无关、非 executor 所建，保留未提交。
