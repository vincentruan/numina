# 智能分析 Phase 2 设计文档

**日期：** 2026-04-26  
**状态：** 已批准  
**范围：** 消费漏洞检测、购买 vs 租赁计算器、消费等价换算

---

## 背景

Numina Phase 1 已实现：老化预警（`ai_asset_alerts`）、资产配置漂移（`ai_allocation_target`）、体检报告（`ai_report`）、处置建议、负债分析、AI 对话。

Phase 2 新增三个智能分析功能，帮助家庭识别消费黑洞、评估买租决策、直观感受消费价值。

---

## 功能一：消费漏洞检测

### 目标

识别家庭资产中存在的"消费黑洞"——高成本低价值的持有模式，综合评分并给出处置建议。

### 评分维度

| 漏洞类型 | `leak_type` | 判断依据 |
|---------|-------------|---------|
| 高闲置成本 | `high_idle_cost` | `usage_frequency` = rarely/idle 且日均成本 > 阈值 |
| 冗余持有 | `redundant` | 同 `category_id` 下 ≥2 个 `in_use` 资产 |
| 高维护负担 | `high_maintenance` | `annual_maintenance_cost / current_value` > 15% |

### 数据流

```
前端 AI 页面
  → POST /api/v1/ai/spending-leaks/refresh (require_ai_enabled)
  → backend → agent POST /spending-leak
  → orchestrator.dispatch(capability="spending_leak")
  → FallbackEngine: 构建 prompt，调用 LLM
  → 结果写入 ai_spending_leaks 表
  → GET /api/v1/ai/spending-leaks 读取展示
```

### 数据库表：`ai_spending_leaks`

```sql
id                  BIGINT PRIMARY KEY
family_id           BIGINT NOT NULL (FK families.id, INDEX)
asset_id            BIGINT NOT NULL (FK assets.id)
asset_name          VARCHAR(200) NOT NULL
leak_type           VARCHAR(50) NOT NULL  -- high_idle_cost | redundant | high_maintenance
severity            VARCHAR(20) NOT NULL  -- low | medium | high
estimated_annual_waste  FLOAT             -- 估算年度浪费金额（元）
suggestion          TEXT                  -- LLM 生成的建议文字
is_dismissed        BOOLEAN NOT NULL DEFAULT FALSE
created_at          DATETIME NOT NULL
dismissed_at        DATETIME
```

### API 端点

```
GET  /api/v1/ai/spending-leaks
     → list[SpendingLeakItem]
     需要：require_adult

POST /api/v1/ai/spending-leaks/refresh
     → { "refreshed": int }
     需要：require_adult + require_ai_enabled
     行为：清除旧未 dismiss 记录，写入新记录（原子操作，同 ai_alerts 模式）

POST /api/v1/ai/spending-leaks/{id}/dismiss
     → { "ok": true }
     需要：require_adult
```

### Agent capability

- capability name: `spending_leak`
- 新增 `agent/routers/spending_leak.py`（同 `alerts.py` 结构）
- `fallback_engine.py` 新增 `spending_leak` case
- LLM prompt 输入：家庭资产列表（含 usage_frequency、annual_maintenance_cost、purchase_price、current_value、category_id）+ dashboard_overview
- LLM 输出结构：`{ leaks: [{ asset_id, asset_name, leak_type, severity, estimated_annual_waste, suggestion }] }`

### 前端位置

AI 分析页面，与老化预警并列，独立卡片 `SpendingLeaksCard.vue`。

---

## 功能二：购买 vs 租赁计算器

### 目标

给定物品参数，计算买入 vs 持续租赁的总成本，找出盈亏平衡点，给出推荐。

### 计算逻辑

```
买入总成本 = purchase_price
           + annual_maintenance_cost × usage_years
           - purchase_price × residual_value_rate × (1 - usage_years/depreciation_years)

租赁总成本 = monthly_rent × usage_months

盈亏平衡月数 = purchase_price / (monthly_rent - annual_maintenance_cost/12)

recommendation:
  - rent_total < buy_total → "租赁更划算"
  - buy_total < rent_total → "购买更划算"
  - 差距 < 10% → "两者相近，建议租赁以保持灵活性"
```

### API 端点

```
POST /api/v1/assets/buy-vs-rent
Body:
  purchase_price        float  (必填)
  monthly_rent          float  (必填)
  usage_months          int    (必填, 1-600)
  annual_maintenance_cost float (选填, default 0)
  depreciation_years    int    (选填, default 10)
  residual_value_rate   float  (选填, default 0.1, 0-1)

Response:
  buy_total             float
  rent_total            float
  breakeven_months      float | null  (月租 ≤ 月均维护费时为 null)
  recommendation        str   -- "购买更划算" | "租赁更划算" | "两者相近，建议租赁以保持灵活性"
  buy_advantage_pct     float -- 正数=买更省，负数=租更省
```

无 DB 存储，无 LLM 调用，纯计算。

### 前端位置

资产详情页，独立组件 `BuyVsRentCalculator.vue`。用户可修改参数实时重算。

---

## 功能三：消费等价换算

### 目标

将资产总持有成本换算为三种直观维度：时间成本、机会成本、日均成本。

### 计算逻辑

```
held_days         = (today - purchase_date).days  (purchase_date 为空则返回 null)
total_held_cost   = purchase_price + annual_maintenance_cost × (held_days/365)

daily_cost        = total_held_cost / held_days

time_cost_hours   = total_held_cost / hourly_wage
                    (hourly_wage 由前端传入，默认 50 元/小时)

opportunity_cost  = total_held_cost × (1 + yield_rate)^years - total_held_cost
                    (yield_rate 默认 0.05，years 默认 10)
```

### API 端点

```
GET /api/v1/assets/{id}/cost-equivalence
Query params:
  hourly_wage   float (选填, default 50)
  yield_rate    float (选填, default 0.05)
  years         int   (选填, default 10, 1-30)

Response:
  asset_id          int
  asset_name        str
  held_days         int | null
  total_held_cost   float | null
  daily_cost        float | null
  time_cost_hours   float | null
  opportunity_cost  float | null
  -- 任何字段为 null 表示数据不完整（如无 purchase_price/purchase_date），不报错
```

无 DB 存储，无 LLM 调用，纯计算。

### 前端位置

资产详情页，独立组件 `CostEquivalenceCard.vue`，展示三个换算结果。

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| `spending-leaks/refresh` agent 调用失败 | `AI_SERVICE_UNAVAILABLE` (503) |
| `spending-leaks/refresh` 写库失败 | `AI_DATA_WRITE_FAILED` (500)，rollback |
| `cost-equivalence` 资产无 purchase_price | 返回 null 字段，不报错 |
| `buy-vs-rent` 参数校验失败 | 422 Validation Error |
| dismiss 不存在的 leak | `AI_SPENDING_LEAK_NOT_FOUND` (404) |

新增 ErrorCode：`AI_SPENDING_LEAK_NOT_FOUND`

---

## 文件变更清单

### Backend

| 文件 | 操作 |
|------|------|
| `app/models/ai_spending_leak.py` | 新建 |
| `app/routers/ai_spending_leaks.py` | 新建 |
| `app/routers/assets_analysis.py` | 新建（buy-vs-rent + cost-equivalence） |
| `app/errors/codes.py` | 新增 `AI_SPENDING_LEAK_NOT_FOUND` |
| `app/main.py` | 注册新 router |
| `alembic/versions/xxxx_add_ai_spending_leaks.py` | 新建 migration |

### Agent

| 文件 | 操作 |
|------|------|
| `routers/spending_leak.py` | 新建 |
| `app/main.py` | 注册新 router |
| `services/fallback_engine.py` | 新增 `spending_leak` case |

### Frontend

| 文件 | 操作 |
|------|------|
| `src/api/aiSpendingLeaks.ts` | 新建 |
| `src/api/assetsAnalysis.ts` | 新建 |
| `src/views/ai/SpendingLeaksCard.vue` | 新建 |
| `src/views/assets/components/BuyVsRentCalculator.vue` | 新建 |
| `src/views/assets/components/CostEquivalenceCard.vue` | 新建 |
| `src/views/assets/AssetDetailPage.vue` | 修改：嵌入两个新组件 |
| `src/views/ai/AIPage.vue` | 修改：嵌入 SpendingLeaksCard |

---

## 不在范围内

- LLM 生成买租建议（纯计算已足够）
- 消费等价换算的 LLM 解读
- 历史漏洞趋势图表
- 跨家庭基准对比
