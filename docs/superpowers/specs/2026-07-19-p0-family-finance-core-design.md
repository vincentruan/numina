# P0 批次设计 — 家庭财务闭环核心（8 项）

> **状态**：设计已确认，待 writing-plans
> **日期**：2026-07-19
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](./2026-07-19-family-finance-optimization-requirements.md)
> **范围**：W1 / W2 / W4 / W5 / L1 / L2 / D2 / A1（D2 与 A1a 合并）

---

## 0. 决策汇总

| 决策点 | 选择 |
|--------|------|
| W1 储蓄数据粒度 | 流水日志表 + `saved_amount` 冗余存表（写时同步更新，避免 SUM） |
| W2 净资产购买力 | 保留为次要参考行 |
| W2 需加速提示 | 要做 |
| W4 采纳方式 | 批量改 monthly_saving |
| W4 卡片位置 | 顶部独立卡片 |
| W5 阈值 | 按负债 category 场景维护（信用卡12%/消费贷10%/房贷6%/其他10%） |
| W5 忽略粒度 | 按心愿粒度（wish 表 `ignore_debt_warning`） |
| L1 排序 | 纯计算（利率降序/余额升序），AI 仅介入"详细规划" |
| L2 利息模型 | 精确摊还（逐月迭代，不做简化估算） |
| util | 前后端双版本（Python domain + TS utils）— ⚠️ review 后改为 single-source，见 §6.1 修订 |
| D2/A1a finance_coach | 独立 capability，**新建** capability-cache（非复用 report 缓存，见 §7.2 修订） |
| D2 卡片条数 | 前 3 条 suggestions |
| A1b context | URL query 传 entity id，`/ai/chat` 加载时拉取注入（**greenfield 新建**，见 §7.3 修订） |

> **⚠️ ce-doc-review 修订（2026-07-19）**：7 reviewer 审出两个 load-bearing 假前提，已修正——(1) "复用 report 8h 缓存"是假的（`ai_reports` 无 capability 列，会与 asset-report 碰撞），改为新建 capability-cache；(2) finance_coach "走 worker 通用流式入口"是假的（R1 allowlist 硬拒非 numina/asset-report/import-parse 的 app），改为显式接入链路。详见各章"review 修订"小节与 §12。

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                          │
│  DashboardPage  WishListPage  WishDetailPage             │
│  LiabilityListPage  LiabilityDetailPage  AIChatPage      │
│       │              │              │                    │
│       ▼              ▼              ▼                    │
│  finance_coach   wish_savings    liability_calculator    │
│  卡片(主动)      流水UI          L1/L2 UI                │
│       │              │              │                    │
└───────┼──────────────┼──────────────┼────────────────────┘
        │              │              │
        ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                 后端 (FastAPI)                           │
│  /ai/finance-coach   /wishes/{id}/savings                │
│  (capability)        (CRUD)                              │
│       │                  │                              │
│       ▼                  ▼                              │
│  finance_coach      WishSavingsLog model                 │
│  agent (stream_run) liability_calculator.py (domain)     │
└─────────────────────────────────────────────────────────┘
```

**四个共享资产**（P0 内部依赖）：
1. `liability_calculator.py`（后端）↔ `liabilityCalculator.ts`（前端）— L1/L2 共用精确摊还
2. `finance_coach` capability / prompt 模板 — D2/A1a 主动 + A1b 被动共用
3. wish 储蓄数据（W1 字段 + 日志表）— W2/W4/W5 都读
4. 8h 缓存机制 — D2（`family_id:finance_coach`，资产/负债/心愿增删改失效）与 W4（`family_id:wish_advice:{fingerprint}`，心愿变更失效）各自独立缓存键与失效策略，非同一机制（详见 §4.4/§7.2）

---

## 2. W1 — 心愿储蓄进度字段

### 2.1 数据模型

**`wish` 表迁移**（Alembic）：
- `saved_amount NUMERIC(18,2) DEFAULT 0` — 冗余计数器，写日志时同步（**见 §2.2 不变量**）
- `target_date DATE NULL`
- `monthly_saving NUMERIC(18,2) DEFAULT 0`
- `ignore_debt_warning BOOLEAN DEFAULT FALSE` — W5 用

> **review 修订（scope-guardian/adversarial/security-lens）**：现有 wish/liability/asset money 字段全 `Float`，新字段用 `NUMERIC(18,2)`。统一序列化契约：API response 所有 money 字段序列化为 `str`（2 位小数，对齐 bigint-as-string 约定，前端用 string-numeric 而非 JS `number` 避免精度损失）；W2 算术混 `saved_amount`(NUMERIC) 与 `expected_price`(Float) 时先 coerce 到 Decimal 再比较。或同迁移把 `expected_price` 改 NUMERIC（推荐，一次性统一）。

**新表 `wish_savings_log`**：
| 列 | 类型 | 说明 |
|----|------|------|
| id | BIGINT(snowflake) | PK |
| wish_id | BIGINT | FK wish |
| family_id | BIGINT | 隔离 |
| user_id | BIGINT | 记录者（DELETE 鉴权用） |
| amount | NUMERIC(18,2) | 正存入/负取出 |
| log_date | DATE | 记录日期 |
| note | VARCHAR(200) NULL | 备注 |
| created_at | DATETIME | |

索引：`(wish_id, log_date DESC)`、`(family_id, created_at)`

> **review 修订（security-lens）**：加 `user_id` 列承载记录者，支撑 DELETE 鉴权。

### 2.2 后端 API

- `POST /wishes/{id}/savings` — body `{amount, log_date?, note?}` → 写 log(含 user_id) + 事务内 `UPDATE wish SET saved_amount = saved_amount + amount` → 返回更新后 wish
- `GET /wishes/{id}/savings` — 流水列表（分页，按 log_date DESC）
- `DELETE /wishes/{id}/savings/{log_id}` — 删除 + 事务内 `UPDATE wish SET saved_amount = saved_amount - log.amount`
- Wish response schema 增 `saved_amount`/`target_date`/`monthly_saving`/`savings_count`

**一致性（不变量）**：savings 增删必须在同一事务内更新 `wish.saved_amount`，用 `SELECT ... FOR UPDATE` 锁 wish 行。**`wish_savings_log` 是 source of truth，`saved_amount` 是 derived cache**。任何 P0 读路径（W2 afford bar、W4 AI 输入、W5 触发）可信任 `saved_amount`。提供 `recompute_saved_amount(wish_id)` reconciliation helper，CI 断言 `saved_amount == SUM(log.amount)`（每个 CRUD 后 + 批量 canary）。**所有 future 写路径**（bulk import / migration backfill / admin fix / W4 redistribution 若触 savings）必须 in-transaction 维护 counter，否则调 `recompute`。

**授权（review 修订 — security-lens）**：复用现有 wish 模式。所有 savings endpoint `Depends(require_adult)` + `wish.family_id == caller.family_id`（复用 `get_wish` family filter）。POST 任何 family adult 可记（共同贡献）；DELETE 限 `log.user_id == caller.id` 或 family owner（复用 `update_wish` owner-check 模式）。child role 不可写 savings（复用 `_assert_not_child`）。

**DELETE 确认（review 修订 — design-lens）**：删除流水属破坏性操作（反向扣减 saved_amount），前端须 van-dialog 二次确认"删除后储蓄进度将回退 ¥X"，删除成功 toast + 就地移除该行 + 同步刷新进度条与 saved_amount，流水空时显示"暂无储蓄记录"空态。

### 2.3 前端

**WishFormPage**：price 下方加"储蓄计划"分组 → `target_date`(van-date-picker) + `monthly_saving`(number field)。`saved_amount` 不在创建表单（初始 0）。

**WishDetailPage**：
- 价值卡下方加储蓄进度条：`已存 ¥X / ¥Y (Z%)` + 预计 N 月达成（N=`ceil((price-saved)/monthly_saving)`，monthly_saving=0 显示"未设定月存"）
- "记录存入"按钮 → 弹窗(金额/日期/备注) → POST savings
- "储蓄流水"入口 → 弹窗或子页展示流水列表（金额/日期/备注/删除）
- 进度条色：Z≥80% 绿、50-80% 蓝、<50% 橙、超额(saved>price) 金

---

## 3. W2 — Afford bar 逻辑重构

### 3.1 新逻辑（列表 + 详情）

| 场景 | 显示 |
|------|------|
| monthly_saving 未设定(=0) | 主"设定月存以规划"，次"购买力：净资产 ¥X 覆盖/未覆盖" |
| monthly_saving 设定 且 saved<price | 主`按月存 ¥M 预计 N 月达成`+预计达成日期，次"购买力..." |
| saved ≥ price | 主`已达成储蓄目标 ✓`(绿) |
| target_date 设定 | 加对照`距目标 D 天，需月存 ¥X`(X=`(price-saved)/ceil(D/30)`)；X>当前 monthly_saving 显红"需加速" |

### 3.2 视觉

afford bar 改双行：第一行进度文字(蓝/绿/橙)，第二行(灰小字)净资产购买力参考。

列表用单行精简（`预计 N 月达成`），详情用双行完整。

> **review 修订（design-lens）— 列表单行降级**：列表单行只显主状态文字（未设定月存/预计 N 月达成/已达成✓/需加速），次要购买力行与 target_date 对照行仅详情显示；列表"需加速"红字前加 `!` 图标保证截断时仍可见状态色。

删除：原 `expected_price <= net_worth` 主判断逻辑（保留为次要参考）。

---

## 4. W4 — 心愿优先级 AI 建议

### 4.1 触发

心愿列表顶部独立卡片，仅当 pending 心愿 ≥ 2 且 ≥1 设定 monthly_saving 时显示。

### 4.2 AI 输出（结构化 JSON）

```json
{
  "primary_wish_id": "...",
  "reason": "距目标日期仅剩90天且优先级高",
  "suggested_monthly": 2000,
  "redistribution": [
    {"wish_id":"...", "suggested_amount":2000, "note":"本月优先"},
    {"wish_id":"...", "suggested_amount":0, "note":"暂缓"}
  ]
}
```

> **review 修订（coherence）**：W4 输出 `redistribution` 与 finance_coach 的 `suggestions[]` 是**不同 AI 调用、不同 schema**（见 §7.1）。W4 独立 prompt + 独立 cache key。

### 4.3 交互（被动）

- 卡片展示"AI 建议：本月优先为「X」存 ¥2000"+ 理由
- "采纳" → 弹窗确认 redistribution → 批量 PATCH 各 wish.monthly_saving
- "看完整建议" → `/ai/chat?source=wish_advice` 带上下文
- 卡片可关闭，8h 内不再提示

> **review 修订（design-lens）— redistribution 弹窗交互态**：弹窗为只读确认列表（每条 wish 显 当前 monthly_saving → 建议值），提供"全部采纳"与"取消"两动作（不支持逐条编辑/部分采纳，避免复杂态）；批量 PATCH 逐条执行，失败项弹窗内标红保留打开，成功项标灰，完成显"X/N 条已更新"汇总而非静默关闭。
> **review 修订（product-lens）— 现金流校验**：系统不 track 月可支配收入（④A），故采纳弹窗显"本月总月存 ¥X（建议值合计）"让用户自判是否超承受力；AI 输出 guardrail：每条 `suggested_amount ≥ 0`（schema 校验失败则整批丢弃不展示，见 §7.1 advice baseline）。
> **review 修订（design-lens）— 关闭与缓存冲突**："已关闭"状态独立于内容缓存存 localStorage（标记 `wish_fingerprint_hash + 关闭时间戳`），8h 窗口内即使内容缓存因数据变更失效也不重新弹卡；8h 后 fingerprint 相同继续抑制，fingerprint 变化才允许重弹。

### 4.4 缓存

key=`family_id:wish_advice:{wish_fingerprint_hash}`，TTL 8h，心愿变更失效。

### 4.5 降级

AI 不可用/无 model 配置 → 不显示卡片（不报错）。

---

## 5. W5 — 高息负债与心愿联动提示

### 5.1 阈值配置

settings 加"负债类型利率阈值"配置，按负债 category 维护：

| category | 默认阈值 |
|----------|---------|
| 信用卡类 | 12% |
| 消费贷 | 10% |
| 房贷 | 6% |
| 其他 | 10% |

owner 可在 settings 配置，存 user settings API。判定时取负债所属 category 对应阈值比较 `interest_rate`。

> **review 修订（security-lens）— owner-only authz**：阈值配置写入须 `require_owner`（`role==owner`），复用 `family.py update_family_settings` 的 owner-only 守卫（`if user.role != 'owner': raise FAMILY_FORBIDDEN`）；读取对所有 family 成员可见。非 owner 改阈值可抑制/解除全家高息提醒，须 stated requirement。

### 5.2 触发条件

任一 active 负债 `interest_rate ≥ 其category阈值` 且有心愿设定 monthly_saving → 触发。

### 5.3 触发点（被动）

| 位置 | 形态 |
|------|------|
| 心愿列表 W4 卡片下方 | 黄色提示条"你有¥X高息负债(利率18%)，每月利息¥Y。先还债比存钱买心愿更划算。查看还款建议 →"跳负债列表 |
| 心愿详情储蓄计划区上方 | 同提示条 + "忽略"按钮(该心愿 `ignore_debt_warning=TRUE`) |
| 心愿表单设定 monthly_saving 时 | inline 提示"检测到高息负债，建议优先还款" |

> **review 修订（design-lens）— 提示条跳转目标**：跳负债列表带 query `?focus=liability_strategy`，列表 onMount 检测该 query 滚动并展开 L1 卡片；若 L1 不满足显示条件（active<2），提示条文案改"查看高息负债"仅跳列表顶部，避免承诺不存在的建议（断链）。
> **review 修订（design-lens）— 表单提示时机**：inline 提示在 `monthly_saving` 字段失焦且值>0 时触发；新建表单（无 wish_id）只显提示不显"忽略"按钮（文案"检测到高息负债，建议优先还款"）；编辑表单（有 wish_id）显提示 + "忽略"按钮，点击立即 PATCH `ignore_debt_warning=TRUE` 并隐藏提示。

### 5.4 与 W4 关系

W5 触发时，提示条显示在 W4 卡片**上方**（先止血再储蓄）。

### 5.5 数据

wish 表 `ignore_debt_warning BOOLEAN DEFAULT FALSE`（W1 迁移一并加）。

---

## 6. L1 + L2 — 负债还款策略 + 利息成本预测

### 6.1 共享 util — 精确摊还模型（single-source）

> **review 修订（scope-guardian/adversarial）**：原"前后端双版本镜像"改为 **single-source**——仅后端 `server/packages/domain/liability_calculator.py`，L2 模拟弹窗调轻量 `POST /liabilities/simulate`（body `{remaining, annual_rate, monthly_payment, extra_monthly}` → `{total_interest, months, savings_vs_baseline, months_saved}`）。消除双语言漂移风险（spec 原 §10 风险"精确摊还模型两端漂移"随之移除）。前端不持摊还逻辑。

**后端** `server/packages/domain/liability_calculator.py`：

```python
def calc_amortization(remaining: Decimal, annual_rate: Decimal,
                      monthly_payment: Decimal, extra_monthly: Decimal = 0) -> AmortizationResult:
    """逐月迭代精确摊还。返回 {total_interest, months, schedule?}"""
```

**等额本息**（有 monthly_payment + interest_rate + remaining）：
- 每月：`利息 = 剩余本金 × 月利率`，`还本 = 月供 - 利息`，`剩余 -= 还本`
- 逐月迭代至 `剩余 ≤ 0`，总利息 = Σ 月利息
- 加 extra_monthly：月供变 `monthly_payment + extra`，重算，对比省息+提前月数

**最低还款/信用卡**（有 interest_rate + remaining，无 monthly_payment）：
- 最低还款 = `max(remaining × 5%, min_payment)`（min_payment 默认 ¥100，可配）
- 逐月：`利息 = 剩余 × 月利率`，`还本 = max(最低还款 - 利息, 0)`
- `还本 ≤ 0` → 报警"最低还款不足，建议增加月供"
- 兜底：最大迭代 1200 月（100 年）防无限循环

**无 interest_rate / monthly_payment**（review 修订 — adversarial）：返回 None，调用方不显示利息区。**数据质量前置**：`liability.interest_rate` 与 `monthly_payment` 均 nullable Float，visualization-first 产品 default 多数负债无 rate。P0 实现前先 `SELECT COUNT(*) WHERE interest_rate IS NULL` 摸底，若 >50% 为 NULL 则 L2 多数用户不可见——L2 form 应提示用户补全 rate/monthly_payment 才能启用利息预测（引导式，非阻塞）。

### 6.2 L1 — 还款顺序建议（列表顶部，被动）

仅 active 负债 ≥ 2 时显示。**纯计算排序**（不用 AI）：

- **雪崩法**：按 `interest_rate` 降序，标注每笔月利息(`remaining × 月利率`)
- **雪球法**：按 `remaining_amount` 升序
- 对比"雪崩法比雪球法省 ¥Y 利息"（用 6.1 util 算两策略总利息差）

UI：双卡片对比展示 + `[采纳雪崩法]` + `[问 AI 详细规划 →]`（跳 `/ai/chat?source=liability_strategy` 带全部负债 context）。

> **review 修订（design-lens）**：`[采纳雪崩法]` 不写负债表（无 schema 变更），仅 localStorage 标记用户偏好，点击后按钮变灰"已采纳雪崩法" + toast"建议已记录，请按利率从高到低分配还款"；真正还款计划落地走"问 AI 详细规划"跳 chat。明确采纳副作用避免实现者猜测。

> **review 修订（product-lens）**：L1 本身只交付排序（计算器层），可执行计划（本月多还 ¥X/N 月清零）由 finance_coach 输出与 D2 卡片联动，或 A1b 跳 chat 生成。L1 不单独构成教练触点，定位为"排序工具 + 跳转入口"。

### 6.3 L2 — 利息成本预测（详情页）

价值卡下方加"利息预测"区（无 interest_rate 不显示）：

```
预计总利息  ¥18,400    剩余 14 个月还清
若每月多还 ¥500：可省 ¥3,200，提前 3 个月
若每月多还 ¥1000：可省 ¥5,800，提前 6 个月
[模拟其他金额 →]
```

"模拟其他金额"弹窗输入自定义 extra → 调 `POST /liabilities/simulate` 实时算省息+提前月数。

> **review 修订（design-lens）— 弹窗边界态**：输入限非负整数（min 0）；0 显示无 extra 基线值；触达 util 报警（还本≤0 / 超 1200 月）弹窗内显黄"该金额下无法还清，请增加月供"非空结果；extra ≥ 剩余本金显"将立即还清"+ 0 利息。

### 6.4 单测

后端覆盖：等额本息正常 / 提前还款省息 / 最低还款覆盖利息 / 最低还款不覆盖利息(报警) / 无利率 / extra≥剩余本金(立即还清) 六种。（single-source 无需双端契约测试）

---

## 7. D2 + A1 — AI 教练触点

### 7.1 finance_coach capability（独立，新建）

区别于 `asset-report`（完整报告），轻量处方性建议。作为新 capability 加入 `RESERVED_NAMES`。

> **review 修订（adversarial/feasibility — 核心问题2）**：spec 原"走 worker `typed_stream_dispatch` 通用 skill 流式入口"是假前提。代码现实：`sse_gateway.py:196` R1 allowlist 硬拒除 `numina/asset-report/import-parse` 外的 app（400）；`gateway.py` 仅 `/runs/asset-report/{thread_id}` per-app 路由无 generic dispatcher；worker 是 `if/elif` on app 无 generic 分支。**finance_coach 接入须完整链路**（precedent import-parse = 整个 U8 单元）：
> 1. `RESERVED_NAMES` 加 `"finance-coach"`（`ai_skills.py:55`）
> 2. Alembic migration 插 system-agent 行（`memory_enabled=False`，参照 `f8a4c2e1b9d6`）
> 3. `gateway.py` 加 dedicated 路由 `/runs/finance-coach/{thread_id}`
> 4. `sse_gateway.py:196` R1 allowlist 加 `"finance-coach"`
> 5. worker 加 `_run_finance_coach_agent` 分支
> 6. SKILL.md `allowed-tools` 用**基名**（非 `numina-*` 前缀），避免 U4 pilot 的 `filter_tools_by_skill_allowed_tools` 过滤光业务工具的 systemic bug
>
> 此为独立实现单元（§8 step 4 展开），非"复用通用入口"。

**输入**：家庭财务快照
```json
{
  "net_worth": 0,
  "total_liabilities": 0,
  "high_interest_debts": [{"id","name","rate","monthly_interest"}],
  "idle_assets": [{"id","name","daily_cost"}],
  "top_daily_cost_assets": [{"id","name","daily_cost"}],
  "wishes": [{"id","name","price","saved","monthly_saving","target_date"}]
}
```

> **review 修订（security-lens）— PII 最小化**：快照是敏感 aggregate PII。字段最小化：entity `name` 改传 `id + category`（除非 prompt 必需，AI 输出用 id 回链不用 name）；不持久化 raw 快照到 log/chat 表超出现有 session retention；LLM provider 经 `AIProviderConfig` 按家庭配置（现有 per-family key 机制，数据不进共享中央账号）。注：现有 PII redaction 层（`PIIRedactor`/`desensitize`）在生产被架构性绕过（MCP tool 结果直送 LLM 未脱敏），finance_coach 沿用同路径——此为 pre-existing 缺陷非本 spec 引入，但 finance_coach 的快照输入应在构建时即脱敏（populate `FamilyContext` structured 字段后 redact，或在喂 LLM 前 `desensitize_*`）。

> **review 修订（adversarial）— advice 可信度 baseline**：W4/W5/D2 全 rest on LLM 产 sound advice。spec 原"AI 不可用→不显示"只处理 absence 不处理 wrong output。增 guardrails：(a) suggestions JSON 在 W4 采纳按钮 enable 前过 schema-validation gate；(b) W4 redistribution 校验每条 `suggested_amount ≥ 0` 且（若系统知月可支配则 Σ ≤ 可支配，④A 不 track income 则仅 ≥0 校验 + 采纳弹窗显"本月总月存 ¥X"提示让用户自判）；(c) AI 输出加"基于你录入的数据"免责标注（W1 全手动，数据可信度有限）。do-nothing baseline：用户不看卡片 vs 看到错误建议，后者更糟——故 wrong output 一律不展示（schema 校验失败静默丢弃 + 记录）。

**输出**（结构化 JSON）：
```json
{
  "suggestions": [
    {"id","severity":"high|medium|low","title","action",
     "target_type":"liability|asset|wish","target_id","cta_label"}
  ]
}
```

> **review 修订（coherence c100 — 核心矛盾）**：原 §7.4 称 W4 共享 finance_coach 输出，但 W4 输出 `primary_wish_id/redistribution`（§4.2）与本 `suggestions[]` schema **互斥**。修正：finance_coach 是 D2/A1a 专用（产 `suggestions[]`）；W4 心愿建议是**独立 AI 调用**产 `redistribution`（不同 prompt、不同 cache key `wish_advice:{fingerprint}`），不共享输出。§7.4 的"共享"表述作废。两者共享的是 **prompt 模板骨架**（家庭财务教练角色设定），非输出 schema。

### 7.2 D2/A1a — Dashboard 主动推送卡片

**位置**：hero (NetWorthCard) 下方，SmartRemindersCard 上方。

**内容**：finance_coach 输出前 3 条 suggestions，每条卡片(severity 色条 + title + action + CTA 按钮)。

> **review 修订（adversarial/feasibility/scope-guardian — 核心问题1）**：原"复用现有 report capability 缓存基础设施"是假前提。代码现实：`ai_reports` 表 `_latest_report` 只按 `family_id + status='completed'` 过滤**无 capability 列**；`REPORT_CACHE_TTL=8h` 是 `ai_report.py` module-level 硬编码绑定 `AIReport` 持久化行 + `AITaskService capability="report"`。**改为新建 capability-cache**：
> - Alembic migration 给 `ai_reports` 加 `capability VARCHAR(32) NOT NULL DEFAULT 'report'` 列，backfill 现有行为 `'report'`
> - `_latest_report` 改按 `(family_id, capability, status)` 过滤
> - 三个独立 cache key：`family_id:report`（现有）、`family_id:finance_coach`（D2）、`family_id:wish_advice:{fingerprint}`（W4）
> - TTL 参数化（`capability_ttl` map，初版均 8h），非硬编码常量
> - 失效：资产/负债/心愿任一写操作即失效（event 驱动，非纯 TTL 兜底）——reviewer 指出 8h 对前瞻性建议过期风险高，P0 即交付 entity 变更精确失效，不留"后续"

**加载**：异步 skeleton → 填充；失败静默不显示。

> **review 修订（design-lens）— 空态**：AI 返回 suggestions 为空数组 → 静默不显示卡片（与失败降级一致）；不足 3 条按实际条数渲染；severity 色条 high(红)/medium(橙)/low(蓝) 区分，不因全 low 隐藏。
> **review 修订（product-lens P3）**：输入过滤掉 `saved_amount=0 且 monthly_saving=0` 的心愿，prompt 指示 AI 跳过无储蓄计划心愿，确保前 3 条聚焦高息负债/闲置资产等有数据支撑项。

**刷新**：右上角"刷新"按钮 force=true 绕过缓存。

### 7.3 A1b — 被动按钮

| 位置 | 按钮 | 跳转 |
|------|------|------|
| 负债详情 actions 区 | "问 AI 优化还款" | `/ai/chat?source=liability_detail&id={id}` |
| 心愿详情储蓄计划区 | "问 AI 规划储蓄" | `/ai/chat?source=wish_detail&id={id}` |
| 负债列表 L1 卡片 | "问 AI 详细规划" | `/ai/chat?source=liability_strategy` |
| 心愿列表 W4 卡片 | "看完整建议" | `/ai/chat?source=wish_advice` |

**context 注入**：URL query 传 entity id + source，`/ai/chat` 页面加载时按 source 拉取对应 entity 数据（负债/心愿/全部负债/全部心愿）注入对话首条 context，AI 无需用户重复描述。

> **review 修订（adversarial — greenfield 非 reuse）**：spec 原语气暗示"接线"，实为 greenfield 新建——`AIChatPage.vue` 今日零 `useRoute`/`route.query`/`source`/prefill handling。须新建：(a) 前端 `AIChatPage`/`AIChatBox` 加 query-param 解析 + entity 拉取 + first-message 注入；(b) 后端 entity-by-id summary endpoint（按 source 路由：`liability_detail`→liabilities、`wish_detail`→wishes、`liability_strategy`→全部负债 summary、`wish_advice`→全部心愿 summary）。此为 A1 的 load-bearing 工作，独立实现单元。
> **review 修订（security-lens）— cross-family 校验**：拉取 entity 须按 `entity.id AND entity.family_id == caller.family_id` 过滤（复用 `get_wish`/`get_liability` family-scoped 查询），id 不属本 family 返回 404，不得注入任何数据。注入的 entity 数据视为 PII，按 chat log retention posture 处理。
> **review 修订（design-lens）— 失败态**：context 拉取设 3s 超时；超时或 404 时 chat 页以普通空白对话启动 + toast"上下文加载失败，请直接描述"，不阻塞输入；成功注入后输入框上方显"已带入：X 上下文"可移除标签。
> **review 修订（security-lens）— prompt 注入**：注入的 entity JSON 须 sanitization（参照 `asset_suggest.py` 的 XML 分隔符 + `_sanitize_user_text` 控制字符剥离 + 长度 cap）再进 first user turn。

### 7.4 与 W4/W5/L1 关系（已修正）

- ~~共享 finance_coach AI 输出~~（作废，见 §7.1 schema 互斥修正）
- finance_coach（D2/A1a，产 `suggestions[]`）与 W4（独立调用产 `redistribution`）共享 prompt 模板骨架，非输出
- W5 高息判定 = 纯计算（L1 利率排序逻辑复用），非 AI
- A1b 跳转后 AI chat 可继续 W4/L1 详细规划
- D2/W4/L1 三处建议**不重复推送同一逻辑**（review 修订 product-lens）：D2 是唯一主动推送入口；W4 仅心愿列表内给储蓄 redistribution；L1 仅负债列表内给排序——各管各的实体域，不跨域重复

---

## 8. 依赖与实现顺序

```
W1 (字段+日志表+API) ──┬─→ W2 (afford bar)
                       ├─→ W4 (AI建议, 读 W1 数据 + finance_coach prompt)
                       └─→ W5 (联动提示, 读 W1 + 依赖 L1 识别高息)

L1+L2 (util + UI) ───────→ W5 (识别高息负债)

finance_coach capability ──┬─→ D2/A1a (主动卡片)
                           ├─→ A1b (被动按钮, 跳 /ai/chat context 注入)
                           └─→ W4 (AI建议 prompt 模板)
```

**建议实现顺序**：
1. W1（后端迁移+API+授权+不变量 → 前端 form/detail+流水删除确认）— 基础
2. L1+L2（single-source util + `/liabilities/simulate` endpoint + 单测 → 列表/详情 UI + 弹窗边界态）— 独立可并行
3. W2（前端 afford bar 重构 + 列表/详情降级，依赖 W1 字段）
4. **finance_coach capability 接入**（核心问题2 — 完整链路：RESERVED_NAMES + system-agent Alembic + gateway 路由 + R1 allowlist + worker 分支 + SKILL.md allowed-tools 基名 + capability-cache 新建[核心问题1：ai_reports 加 capability 列 + 参数化 TTL + entity 变更失效]）— 重单元，可能需拆子步骤
5. D2/A1a（Dashboard 卡片 + 空态，依赖 finance_coach + capability-cache）
6. A1b（被动按钮 + /ai/chat greenfield context 注入[query 解析 + entity summary endpoint + family 校验 + 失败态 + prompt 注入 sanitization]）
7. W4（心愿列表卡片 + redistribution 弹窗交互态 + 关闭/缓存独立 + 现金流提示，依赖 W1 + 独立 AI prompt）
8. W5（联动提示 + 跳转目标 + 表单提示时机 + owner-only 阈值，依赖 W1 + L1）

---

## 9. 测试策略

- **后端**：liability_calculator 6 case 单测（single-source）；wish_savings CRUD 事务一致性 + `saved_amount == SUM(log)` reconciliation 断言；finance_coach capability 流式输出 + schema-validation gate 测试；capability-cache 多 capability 隔离测试（finance_coach/report/wish_advice 不互相污染）
- **前端**：WishDetailPage 进度条/流水删除确认交互；L2 模拟弹窗边界态（0/负/超额/无解）；D2 卡片 skeleton/缓存/空态/降级；W4 redistribution 弹窗部分失败态；A1b context 注入超时/404/family 校验
- **集成**：W5 阈值判定（各 category + owner-only）；A1b context 注入端到端（含跨家庭 404）；finance_coach R1 allowlist + dispatch 链路
- **回归**：现有 wish/liability/asset-report 测试不受影响（W1 迁移向后兼容；ai_reports 加 capability 列 backfill='report' 不破坏现有 report 查询）

---

## 10. 风险与未决

| 风险 | 缓解 |
|------|------|
| ~~精确摊还模型两端漂移~~ | ~~CI 双跑~~ → 已改 single-source（§6.1），风险消除 |
| finance_coach 接入链路重（R1/gateway/worker/RESERVED_NAMES/system-agent/SKILL） | 独立实现单元（§8 step4），参照 import-parse U8 precedent；SKILL.md allowed-tools 用基名避免 U4 前缀 bug |
| capability-cache 新建（ai_reports 加 capability 列） | Alembic migration backfill='report' 不破坏现有；参数化 TTL；entity 变更 event 失效 |
| A1b context 注入 greenfield（AIChatPage 无 query 解析） | 独立实现单元（§8 step6）；entity summary endpoint 按 source 路由；family 校验 + sanitization |
| L2 多数负债无 interest_rate（nullable） | 实现前 SELECT 摸底 NULL 占比；form 引导补全 rate/monthly_payment |
| saved_amount counter drift | reconciliation helper + CI 断言 + future 写路径约束（§2.2 不变量） |
| W5 阈值配置 UI 复杂 | 初版用默认值，配置 UI 留 P1 |
| AI advice wrong output（非 absence） | schema-validation gate + guardrails + 免责标注 + wrong 一律不展示（§7.1） |
| 闭环结构性（/finance hub deferred P1） | P0 是 additive 价值（各模块内闭环），结构性连接靠 P1 N1；P0 不宣称"打通全链路"，仅"各触点就位" |

---

## 11. P1/P2 待登记（本轮不展开）

- P1：N1 财务 hub(②B+⑥C)、D1/D3/D4/D5/D6/D7、L4/L5/L3、A2/A3、B4、F3/F7
- P2：W6、L6、D9/D10、A4/A5/A7、B2/B3/B5、S1/S2/S3/F2/F6、N2/N3
- P3：W6b、L7、D8、A6、B1

---

## 12. ce-doc-review 修订总结（2026-07-19）

7 reviewer（coherence/feasibility/product-lens/design-lens/security-lens/scope-guardian/adversarial）审出 37 条发现，2 条 safe_auto 已静默修复（§1 缓存共用表述、§8 依赖图 W4 边），其余 actionable findings 的 suggested_fix 已并入各章"review 修订"小节。

**两个 load-bearing 核心问题（4/3 reviewer 独立证实）**：
1. **缓存复用前提假**（§7.2）— `ai_reports` 无 capability 列，"复用 report 缓存"会碰撞 → 改新建 capability-cache
2. **finance_coach dispatch 被阻断**（§7.1）— R1 allowlist 硬拒非 numina/asset-report/import-parse → 改完整接入链路

**其余主要修订**：
- §2 W1：加授权模型（require_adult + family filter + DELETE owner-check）、counter 不变量与 reconciliation、序列化契约（NUMERIC/Float→str）、流水删除确认
- §4 W4：redistribution 弹窗交互态、关闭/缓存独立、现金流提示
- §5 W5：owner-only 阈值、提示条跳转目标、表单提示时机
- §6 L1/L2：dual-util→single-source、L1 采纳 persistence、L2 弹窗边界态、nullable-rate 数据质量
- §7 D2/A1：PII 最小化、advice baseline guardrails、schema 互斥修正、capability-cache 新建、context 注入 greenfield+family 校验+失败态+prompt 注入 sanitization、空态
- §7.4：W4/finance_coach 不共享输出（schema 互斥），共享仅 prompt 骨架；三处建议不跨域重复
- §8：实现顺序反映 finance_coach 接入与 A1b greenfield 是重单元
- §10：风险表更新（dual-util 漂移消除，新增接入/greenfield/nullable-rate/counter drift/advice wrong output/闭环结构性）

**未决（留 writing-plans）**：finance_coach 接入是否拆独立 plan；capability-cache 用 `ai_reports` 加列 vs 新表；A1b entity summary endpoint 路由归属。

