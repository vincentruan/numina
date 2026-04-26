# 资产时光机 Phase 3 设计文档

**日期：** 2026-04-26
**状态：** 已批准
**范围：** What-if 消费模拟、财务推演、购买力时光机

---

## 背景

Numina Phase 2 已实现：消费漏洞检测、购买 vs 租赁计算器、消费等价换算。

Phase 3 新增"资产时光机"功能组，帮助家庭模拟消费决策的长远影响、推演未来财务状况、直观感受通胀对购买力的侵蚀。

### 设计原则

- **纯计算优先**：核心逻辑为确定性数学模型，不依赖 LLM，与 Phase 2 的 buy-vs-rent / cost-equivalence 模式一致
- **LLM 可选增强**：AI 启用时，Agent 生成自然语言解读；未启用时 `summary` 返回 `null`，前端不展示解读卡片
- **无 DB 存储**：What-if 和购买力计算为纯计算端点；财务推演仅新增一张种子数据表（分类默认参数）

---

## 功能一：What-if 消费模拟器

### 目标

用户构造假设场景（如"卖掉闲置车，资金转入基金"），系统计算两条时间线（维持现状 vs 执行变更）在未来 N 年的净资产差异。

### 计算模型

```
场景 A（维持现状）：
  每年净资产 = 当前净资产
    + Σ(资产_i × 年增值率_i)
    - Σ(资产_i × 年折旧率_i)
    - Σ(年维护成本_i)
    - Σ(负债月供_i × 12)

场景 B（执行变更）：
  在场景 A 基础上：
    - 移除被处置资产的折旧/维护成本
    + 处置收入（current_value × 变现折扣率）
    + 新增投资的年化收益
    - 新增支出项

输出：
  两条净资产曲线 + 每年差额 + N 年后总差异 + 盈亏平衡点
```

### Schemas

```python
# schemas/whatif.py

class WhatIfAction(BaseModel):
    action_type: Literal["sell", "buy", "invest", "stop_expense"]
    asset_id: int | None = None          # sell: 要处置的资产; stop_expense: 要停止维护的资产
    amount: float | None = None          # buy: 购买金额; invest: 投资金额; stop_expense: 年节省金额（为空时自动取资产 annual_maintenance_cost）
    annual_return_rate: float = 0.0      # invest: 年化收益率
    annual_cost: float = 0.0             # buy: 年维护成本
    liquidation_rate: float = 0.8        # sell: 变现折扣率（0-1）

class WhatIfRequest(BaseModel):
    actions: list[WhatIfAction]          # 1-5 个操作
    projection_years: int = 10           # 1-30
    inflation_rate: float = 0.03         # 默认 3%

class WhatIfYearPoint(BaseModel):
    year: int
    baseline_net_worth: float
    scenario_net_worth: float
    difference: float

class WhatIfResponse(BaseModel):
    projection: list[WhatIfYearPoint]
    total_difference: float              # N 年后总差异
    breakeven_year: int | None           # 场景 B 超过 A 的年份
    summary: str | None                  # LLM 解读（AI 未启用时为 None）
```

### API 端点

```
POST /api/v1/ai/whatif
Body: WhatIfRequest
Response: WhatIfResponse
需要: require_adult
```

纯计算，无 DB 存储。如果 `ai_enabled`，额外调用 Agent 生成 `summary`。

---

## 功能二：财务推演（未来净资产预测）

### 目标

基于 `AssetSnapshot` 历史数据 + 资产折旧/增值模型，推演未来 N 年的净资产曲线，同时展示扣除通胀后的真实购买力。

### 计算模型

```
历史趋势：
  从 asset_snapshots 取最近 12 个月的 net_worth 数据点
  计算月均增长率 = (最新 - 最早) / 月数

逐资产推演：
  实物资产：current_value × (1 - 年折旧率)^n
    年折旧率 = 1 / expected_lifespan_years（无寿命数据则用分类默认值）
  金融资产：current_value × (1 + annual_return_rate)^n
    无利率数据则用分类默认值（存款 2%、基金 6%、股票 8%）

负债推演：
  按月供递减 remaining_amount，到 end_date 归零

综合：
  future_net_worth[year] = Σ(资产推演值) - Σ(负债推演值)
  real_net_worth[year] = future_net_worth[year] / (1 + inflation_rate)^year
```

### 数据库表：`category_financial_defaults`

分类默认财务参数（种子数据，只读）：

```sql
CREATE TABLE category_financial_defaults (
    id                            BIGINT PRIMARY KEY,
    category_id                   BIGINT NOT NULL UNIQUE (FK categories.id),
    default_annual_depreciation   FLOAT DEFAULT 0.1,
    default_annual_return         FLOAT DEFAULT 0.0,
    default_lifespan_years        INT DEFAULT 10
);
```

种子数据：

| 分类 | 年折旧率 | 年化收益 | 默认寿命 |
|------|---------|---------|---------|
| 房产 | 0.02 | 0.03 | 50 |
| 车辆 | 0.15 | 0 | 10 |
| 数码 | 0.25 | 0 | 4 |
| 家电 | 0.10 | 0 | 10 |
| 家具 | 0.08 | 0 | 15 |
| 珠宝 | 0.01 | 0.02 | 50 |
| 服饰 | 0.30 | 0 | 3 |
| 美妆 | 0.50 | 0 | 2 |
| 运动 | 0.15 | 0 | 8 |
| 玩具 | 0.20 | 0 | 5 |
| 宠物 | 0.20 | 0 | 5 |
| 乐器 | 0.05 | 0 | 20 |
| 箱包 | 0.15 | 0 | 8 |
| 存款 | 0 | 0.02 | - |
| 基金 | 0 | 0.06 | - |
| 股票 | 0 | 0.08 | - |
| 债券 | 0 | 0.04 | - |
| 保险 | 0 | 0.03 | - |
| 理财产品 | 0 | 0.035 | - |
| 数字货币 | 0 | 0.10 | - |
| 其他金融 | 0 | 0.03 | - |

### Schemas

```python
# schemas/projection.py

class ProjectionRequest(BaseModel):
    projection_years: int = 5            # 1-30
    inflation_rate: float = 0.03         # 用于购买力修正
    custom_overrides: dict[int, float] | None = None  # asset_id → 自定义年增值/折旧率

class ProjectionYearPoint(BaseModel):
    year: int
    total_assets: float
    total_liabilities: float
    net_worth: float
    real_net_worth: float                # 扣除通胀后的真实购买力

class ProjectionResponse(BaseModel):
    history: list[ProjectionYearPoint]   # 过去数据（来自 snapshots）
    forecast: list[ProjectionYearPoint]  # 未来推演
    assumptions: dict                    # 使用的参数（透明展示）
    summary: str | None                  # LLM 解读
```

### API 端点

```
POST /api/v1/ai/projection
Body: ProjectionRequest
Response: ProjectionResponse
需要: require_adult
```

---

## 功能三：购买力时光机

### 目标

将任意金额在不同年份之间换算真实购买力。两个子功能：
- **回看**：当年花的 X 元，相当于今天的多少钱？
- **前看**：今天的 X 元，N 年后相当于多少？

### 计算模型

```
回看：real_value = amount × Π(1 + cpi[year]) for year in [from_year..to_year)
      （逐年复合，使用实际 CPI 数据）
前看：future_value = amount / (1 + inflation_rate)^years
      （使用用户自定义或默认通胀率）

CPI 数据源：内置中国近 20 年 CPI 年均数据（硬编码常量表）
用户可自定义通胀率覆盖默认值
```

### CPI 常量数据

```python
# constants/cpi.py
CHINA_CPI_ANNUAL = {
    2005: 1.8, 2006: 1.5, 2007: 4.8, 2008: 5.9,
    2009: -0.7, 2010: 3.3, 2011: 5.4, 2012: 2.6,
    2013: 2.6, 2014: 2.0, 2015: 1.4, 2016: 2.0,
    2017: 1.6, 2018: 2.1, 2019: 2.9, 2020: 2.5,
    2021: 0.9, 2022: 2.0, 2023: 0.2, 2024: 0.2,
    2025: 0.5,
}
```

### Schemas

```python
# schemas/purchasing_power.py

class PurchasingPowerRequest(BaseModel):
    amount: float                        # 金额
    from_year: int                       # 起始年份
    to_year: int                         # 目标年份
    custom_inflation_rate: float | None = None  # 覆盖默认 CPI

class PurchasingPowerResponse(BaseModel):
    original_amount: float
    adjusted_amount: float               # 换算后金额
    from_year: int
    to_year: int
    cumulative_inflation: float          # 累计通胀率
    annual_avg_inflation: float          # 年均通胀率
    explanation: str                     # 预设文案
```

### API 端点

```
GET /api/v1/ai/purchasing-power
Query: amount, from_year, to_year, custom_inflation_rate
Response: PurchasingPowerResponse
需要: require_adult
```

资产级别便捷端点：

```
GET /api/v1/assets/{id}/purchasing-power
Response: PurchasingPowerResponse
自动使用资产的 purchase_price + purchase_date 年份
```

---

## Agent 能力扩展

新增 `time_machine` capability，仅用于生成 What-if 和 Projection 的自然语言解读。

### Agent Router

```
routers/time_machine.py
POST /time-machine/interpret
Body: { type: "whatif"|"projection", data: <计算结果>, family_context: <overview> }
Response: { summary: str }
```

### LLM Prompt 模板

```
你是家庭财务顾问。以下是用户的{whatif模拟/财务推演}计算结果：
{data}

家庭财务概况：{overview}

请用 2-3 句话总结关键发现，给出一个明确的建议。
语气：温和、实用、不说教。
```

### 降级策略

AI 未启用时，三个功能的 `summary` 字段返回 `null`，前端不展示解读卡片。核心计算功能不受影响。

---

## 前端 UI 组件

### 页面结构

`AITimeMachinePage.vue` — 时光机主页面，三个 Tab 切换
- 路由：`/ai/time-machine`
- 在 AIHubPage 的 feature grid 中新增入口卡片

### Tab 1：What-if 模拟器 `WhatIfSimulator.vue`

- 操作列表：用户添加 1-5 个操作（卖出资产/新增投资/停止支出）
- 资产选择器：从现有资产列表中选择（van-picker）
- 参数调节：滑块调整投影年数（1-30）、通胀率（0-10%）
- 结果展示：ECharts 双线图（基准 vs 场景）+ 差额高亮区域 + 盈亏平衡标注线
- LLM 解读卡片（AI 启用时展示）

### Tab 2：财务推演 `ProjectionChart.vue`

- 历史+未来净资产曲线（ECharts area chart）
- 历史部分实线，未来部分虚线，分界线标注"今天"
- 双 Y 轴：名义值（左）+ 真实购买力（右）
- 参数面板：投影年数、通胀率、可逐资产覆盖增值率
- 资产明细折叠面板：展示每个资产的推演假设（分类默认值 + 用户覆盖）

### Tab 3：购买力计算器 `PurchasingPowerCalc.vue`

- 金额输入 + 年份选择器（from/to，van-date-picker 年份模式）
- 结果卡片：原始金额 → 换算金额，带数字滚动动画
- CPI 趋势小图（ECharts sparkline）
- "我的资产购买力"快捷入口：列出所有资产的购买力变化排行

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| `whatif` actions 为空 | 422 Validation Error |
| `whatif` asset_id 不存在 | `ASSET_NOT_FOUND` (404) |
| `whatif` actions 超过 5 个 | 422 Validation Error |
| `projection` 无 snapshot 历史数据 | 返回空 `history`，仅返回 `forecast` |
| `projection` 无资产数据 | 返回全零曲线 |
| `purchasing-power` from_year > to_year | 自动交换（回看/前看由方向决定） |
| `purchasing-power` 年份超出 CPI 数据范围 | 使用最近可用年份的 CPI 或用户自定义通胀率 |
| Agent `time_machine/interpret` 调用失败 | `summary` 返回 `null`，不影响计算结果 |
| 资产无 purchase_date | 资产级购买力端点返回 `null` 字段，不报错 |

---

## 文件变更清单

### Backend

| 文件 | 操作 |
|------|------|
| `app/constants/cpi.py` | 新建 — CPI 常量数据 |
| `app/models/category_financial_default.py` | 新建 — 分类默认财务参数模型 |
| `app/schemas/whatif.py` | 新建 |
| `app/schemas/projection.py` | 新建 |
| `app/schemas/purchasing_power.py` | 新建 |
| `app/services/whatif.py` | 新建 — What-if 计算引擎 |
| `app/services/projection.py` | 新建 — 财务推演引擎 |
| `app/services/purchasing_power.py` | 新建 — 购买力计算 |
| `app/routers/ai_time_machine.py` | 新建 — whatif + projection + purchasing-power 端点 |
| `app/routers/assets_analysis.py` | 修改 — 新增资产购买力端点 |
| `app/seed/category_financial_defaults.py` | 新建 — 种子数据 |
| `app/main.py` | 修改 — 注册新 router |
| `alembic/versions/xxxx_add_category_financial_defaults.py` | 新建 — migration |

### Agent

| 文件 | 操作 |
|------|------|
| `routers/time_machine.py` | 新建 |
| `app/main.py` | 修改 — 注册新 router |
| `services/fallback_engine.py` | 修改 — 新增 `time_machine` case |

### Frontend

| 文件 | 操作 |
|------|------|
| `src/api/timeMachine.ts` | 新建 — API 调用 |
| `src/pages/AITimeMachinePage.vue` | 新建 — 主页面（三 Tab） |
| `src/components/ai/WhatIfSimulator.vue` | 新建 |
| `src/components/ai/ProjectionChart.vue` | 新建 |
| `src/components/ai/PurchasingPowerCalc.vue` | 新建 |
| `src/pages/AIHubPage.vue` | 修改 — 新增时光机入口卡片 |
| `src/router/index.ts` | 修改 — 新增路由 |
| `src/i18n/locales/zh-CN.ts` | 修改 — 新增文案 |
| `src/i18n/locales/en-US.ts` | 修改 — 新增文案 |

---

## 不在范围内

- 自动定时推演（用户手动触发即可）
- 多家庭对比
- 外部 CPI 数据源 API 接入（硬编码足够，后续可扩展）
- 资产推演结果持久化（纯计算，不存 DB）
- What-if 场景保存/历史记录（MVP 不需要）
- LLM 生成购买力解读（预设文案已足够）
- 跨币种通胀率差异（统一使用 CNY 通胀率）
