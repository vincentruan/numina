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
| util | 前后端双版本（Python domain + TS utils） |
| D2/A1a finance_coach | 独立 capability，复用 8h 缓存机制 |
| D2 卡片条数 | 前 3 条 suggestions |
| A1b context | URL query 传 entity id，`/ai/chat` 加载时拉取注入 |

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
4. 8h 缓存机制（复用现有 report capability 基础设施）— D2/W4 共用

---

## 2. W1 — 心愿储蓄进度字段

### 2.1 数据模型

**`wish` 表迁移**（Alembic）：
- `saved_amount NUMERIC(18,2) DEFAULT 0` — 冗余计数器，写日志时同步
- `target_date DATE NULL`
- `monthly_saving NUMERIC(18,2) DEFAULT 0`
- `ignore_debt_warning BOOLEAN DEFAULT FALSE` — W5 用

**新表 `wish_savings_log`**：
| 列 | 类型 | 说明 |
|----|------|------|
| id | BIGINT(snowflake) | PK |
| wish_id | BIGINT | FK wish |
| family_id | BIGINT | 隔离 |
| amount | NUMERIC(18,2) | 正存入/负取出 |
| log_date | DATE | 记录日期 |
| note | VARCHAR(200) NULL | 备注 |
| created_at | DATETIME | |

索引：`(wish_id, log_date DESC)`、`(family_id, created_at)`

### 2.2 后端 API

- `POST /wishes/{id}/savings` — body `{amount, log_date?, note?}` → 写 log + 事务内 `UPDATE wish SET saved_amount = saved_amount + amount` → 返回更新后 wish
- `GET /wishes/{id}/savings` — 流水列表（分页，按 log_date DESC）
- `DELETE /wishes/{id}/savings/{log_id}` — 删除 + 事务内 `UPDATE wish SET saved_amount = saved_amount - log.amount`
- Wish response schema 增 `saved_amount`/`target_date`/`monthly_saving`/`savings_count`

**一致性**：savings 增删必须在同一事务内更新 `wish.saved_amount`，用 `SELECT ... FOR UPDATE` 锁 wish 行。

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

### 4.3 交互（被动）

- 卡片展示"AI 建议：本月优先为「X」存 ¥2000"+ 理由
- "采纳" → 弹窗确认 redistribution → 批量 PATCH 各 wish.monthly_saving
- "看完整建议" → `/ai/chat?source=wish_advice` 带上下文
- 卡片可关闭，8h 内不再提示（复用缓存）

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

### 5.2 触发条件

任一 active 负债 `interest_rate ≥ 其category阈值` 且有心愿设定 monthly_saving → 触发。

### 5.3 触发点（被动）

| 位置 | 形态 |
|------|------|
| 心愿列表 W4 卡片下方 | 黄色提示条"你有¥X高息负债(利率18%)，每月利息¥Y。先还债比存钱买心愿更划算。查看还款建议 →"跳负债列表 |
| 心愿详情储蓄计划区上方 | 同提示条 + "忽略"按钮(该心愿 `ignore_debt_warning=TRUE`) |
| 心愿表单设定 monthly_saving 时 | inline 提示"检测到高息负债，建议优先还款" |

### 5.4 与 W4 关系

W5 触发时，提示条显示在 W4 卡片**上方**（先止血再储蓄）。

### 5.5 数据

wish 表 `ignore_debt_warning BOOLEAN DEFAULT FALSE`（W1 迁移一并加）。

---

## 6. L1 + L2 — 负债还款策略 + 利息成本预测

### 6.1 共享 util — 精确摊还模型

**后端** `server/packages/domain/liability_calculator.py`：
**前端** `frontend/apps/main/src/utils/liabilityCalculator.ts`（镜像）：

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

**无 interest_rate**：返回 None，调用方不显示利息区。

### 6.2 L1 — 还款顺序建议（列表顶部，被动）

仅 active 负债 ≥ 2 时显示。**纯计算排序**（不用 AI）：

- **雪崩法**：按 `interest_rate` 降序，标注每笔月利息(`remaining × 月利率`)
- **雪球法**：按 `remaining_amount` 升序
- 对比"雪崩法比雪球法省 ¥Y 利息"（用 6.1 util 算两策略总利息差）

UI：双卡片对比展示 + `[采纳雪崩法]` + `[问 AI 详细规划 →]`（跳 `/ai/chat?source=liability_strategy` 带全部负债 context）。

### 6.3 L2 — 利息成本预测（详情页）

价值卡下方加"利息预测"区（无 interest_rate 不显示）：

```
预计总利息  ¥18,400    剩余 14 个月还清
若每月多还 ¥500：可省 ¥3,200，提前 3 个月
若每月多还 ¥1000：可省 ¥5,800，提前 6 个月
[模拟其他金额 →]
```

"模拟其他金额"弹窗输入自定义 extra → 前端 util 实时算省息+提前月数。

### 6.4 单测

两端各覆盖：等额本息正常 / 提前还款省息 / 最低还款覆盖利息 / 最低还款不覆盖利息(报警) / 无利率 五种。

---

## 7. D2 + A1 — AI 教练触点

### 7.1 finance_coach capability（独立，新建）

区别于 `asset-report`（完整报告），轻量处方性建议。作为 RESERVED_NAMES 之外的新 capability，走 worker `typed_stream_dispatch` 通用 skill 流式入口。

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

**输出**（结构化 JSON）：
```json
{
  "suggestions": [
    {"id","severity":"high|medium|low","title","action",
     "target_type":"liability|asset|wish","target_id","cta_label"}
  ]
}
```

### 7.2 D2/A1a — Dashboard 主动推送卡片

**位置**：hero (NetWorthCard) 下方，SmartRemindersCard 上方。

**内容**：finance_coach 输出前 3 条 suggestions，每条卡片(severity 色条 + title + action + CTA 按钮)。

**缓存**：key=`family_id:finance_coach`，TTL 8h，复用现有 report capability 缓存基础设施。资产/负债/心愿增删改失效。

**加载**：异步 skeleton → 填充；失败静默不显示。

**刷新**：右上角"刷新"按钮 force=true 绕过缓存。

### 7.3 A1b — 被动按钮

| 位置 | 按钮 | 跳转 |
|------|------|------|
| 负债详情 actions 区 | "问 AI 优化还款" | `/ai/chat?source=liability_detail&id={id}` |
| 心愿详情储蓄计划区 | "问 AI 规划储蓄" | `/ai/chat?source=wish_detail&id={id}` |
| 负债列表 L1 卡片 | "问 AI 详细规划" | `/ai/chat?source=liability_strategy` |
| 心愿列表 W4 卡片 | "看完整建议" | `/ai/chat?source=wish_advice` |

**context 注入**：URL query 传 entity id + source，`/ai/chat` 页面加载时按 source 拉取对应 entity 数据（负债/心愿/全部负债/全部心愿）注入对话首条 context，AI 无需用户重复描述。

### 7.4 与 W4/W5/L1 关系

- D2 suggestions 里高息负债建议 = W5 逻辑、心愿建议 = W4 逻辑——**共享 finance_coach AI 输出**避免重复调用
- A1b 跳转后 AI chat 可继续 W4/L1 详细规划

---

## 8. 依赖与实现顺序

```
W1 (字段+日志表+API) ──┬─→ W2 (afford bar)
                       ├─→ W4 (AI建议, 读 W1 数据)
                       └─→ W5 (联动提示, 读 W1 + 依赖 L1 识别高息)

L1+L2 (util + UI) ───────→ W5 (识别高息负债)
                         ↗
finance_coach capability ──→ D2/A1a (主动卡片)
                       └──→ A1b (被动按钮, 跳 /ai/chat context 注入)
```

**建议实现顺序**：
1. W1（后端迁移+API → 前端 form/detail）— 基础
2. L1+L2（util 双版本+单测 → 列表/详情 UI）— 独立可并行
3. W2（前端 afford bar 重构，依赖 W1 字段）
4. finance_coach capability（后端 agent → 缓存）
5. D2/A1a（Dashboard 卡片，依赖 finance_coach）
6. A1b（被动按钮 + /ai/chat context 注入）
7. W4（心愿列表卡片，依赖 W1 + finance_coach prompt）
8. W5（联动提示，依赖 W1 + L1）

---

## 9. 测试策略

- **后端**：liability_calculator 5 case 单测；wish_savings CRUD 事务一致性测试；finance_coach capability 流式输出测试
- **前端**：liabilityCalculator.ts 镜像 5 case 单测；WishDetailPage 进度条/流水交互；L2 模拟弹窗；D2 卡片 skeleton/缓存/降级
- **集成**：W5 阈值判定（各 category）；A1b context 注入端到端
- **回归**：现有 wish/liability 测试不受影响（W1 迁移向后兼容，新字段有默认值）

---

## 10. 风险与未决

| 风险 | 缓解 |
|------|------|
| 精确摊还模型两端漂移 | 共享 5 case 单测作契约，CI 双跑 |
| finance_coach 缓存失效粒度粗 | 初版 8h TTL + 手动刷新，后续按 entity 变更精确失效 |
| A1b context 注入数据量大 | 仅传必要字段，大列表走 summary |
| W5 阈值配置 UI 复杂 | 初版用默认值，配置 UI 留 P1 |

---

## 11. P1/P2 待登记（本轮不展开）

- P1：N1 财务 hub(②B+⑥C)、D1/D3/D4/D5/D6/D7、L4/L5/L3、A2/A3、B4、F3/F7
- P2：W6、L6、D9/D10、A4/A5/A7、B2/B3/B5、S1/S2/S3/F2/F6、N2/N3
- P3：W6b、L7、D8、A6、B1
