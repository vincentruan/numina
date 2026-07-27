# AI 侧多币种数据修复提案

> **日期**: 2026-07-27
> **状态**: ✅ 已实施（方案 A）
> **影响范围**: AI 智能体、资产报告、理财教练、心愿建议

---

## 一、现状分析

### 1.1 数据链路梳理

AI 获取家庭财务数据有 **三条主要链路**：

| 链路 | 入口 | 用途 | 币种处理 |
|------|------|------|----------|
| **A. AI Context** | `GET /ai/context` | 智能体系统提示词注入 | 硬编码 `¥`，无 currency |
| **B. MCP 工具** | `get_assets` / `get_liabilities` / `get_family_overview` | 资产报告、智能体查询 | 混合：overview 已转，assets/liabilities 未转 |
| **C. 快照注入** | `finance_coach_snapshot` / `wish_advice` | 理财教练、心愿建议 | 未转换，未标注币种 |

### 1.2 具体问题

#### 链路 A：AI Context Builder

```
文件: server/apps/backend/app/services/ai_context_builder.py
```

| 行号 | 问题 | 影响 |
|------|------|------|
| 52-57 | `_fmt_money()` 硬编码 `¥` 符号 | USD 负债显示为 `¥10,000.00`，误导 AI |
| 73-88 | `build_liability_detail()` 不输出 currency | AI 不知道负债是什么币种 |
| 91-107 | `build_wish_detail()` 不输出 currency | 同上 |
| 110-126 | `build_liability_strategy()` 不输出 currency | 同上 |
| 129-147 | `build_wish_advice()` 不输出 currency | 同上 |

#### 链路 B：MCP 工具

```
文件: server/apps/backend/app/services/asset.py (MCP asset 工具实现)
文件: server/apps/backend/app/services/liability.py (MCP liability 工具实现)
```

| 工具 | 行号 | 问题 |
|------|------|------|
| `get_assets` | 618-626 | 返回 dict 无 `currency` 字段，金额是原始币种 |
| `get_liabilities` | 111-118 | 返回 dict 无 `currency` 字段，金额是原始币种 |
| `get_family_overview` | - | 金额已转 `default_currency`，但响应无币种标注 |

#### 链路 C：快照注入

```
文件: server/apps/backend/app/services/finance_coach_snapshot.py
文件: server/apps/backend/app/services/wish_advice.py
```

| 行号 | 问题 | 影响 |
|------|------|------|
| 57-59 | `net_worth = total_assets - total_liabilities` 直接相加不同币种 | **数学错误**：CNY 100,000 + USD 50,000 = 150,000 ??? |
| 39-140 | 整个 snapshot 无 `currency` 字段 | AI 无法知道任何金额的币种 |
| wish_advice.py:113-127 | 心愿快照无 `currency` | 同上 |

### 1.3 风险矩阵

| 场景 | 当前行为 | 潜在风险 |
|------|----------|----------|
| 用户有 USD 资产 + CNY 负债 | AI 看到 `¥10,000` (USD) 和 `¥50,000` (CNY) | 错误的净值计算、错误的建议 |
| 理财教练分析多币种家庭 | `net_worth` 是无意义的混合相加 | 建议基于错误数据 |
| 资产报告汇总 | 各资产原始金额、无币种标注 | AI 可能给出错误的占比分析 |

---

## 二、方案对比

### 方案 A：统一转换为用户默认币种（推荐）

**思路**：所有给 AI 的数据，统一调用 `ExchangeRateService.convert()` 转为 `default_currency`，并在响应中标注币种。

**优点**：
- AI 拿到一致的数据，无需理解汇率
- 复用已有的 dashboard 转换逻辑
- 对 AI 提示词长度影响最小

**缺点**：
- AI 无法区分原始币种（但大多数场景不需要）
- 需要处理汇率缺失的情况

**改动范围**：

| 文件 | 改动 |
|------|------|
| `ai_context_builder.py` | 添加 `default_currency` 参数，`_fmt_money()` 动态符号，每个 builder 做转换 |
| `asset.py` (MCP) | `list_assets_for_family()` 转换 + 加 `currency` 字段 |
| `liability.py` (MCP) | `list_liabilities_for_family()` 转换 + 加 `currency` 字段 |
| `finance_coach_snapshot.py` | 所有金额先转换再汇总 |
| `wish_advice.py` | 所有金额先转换 |
| `schemas/dashboard.py` | `OverviewResponse` 加 `currency` 字段 |

---

### 方案 B：保留原始币种并标注

**思路**：每条记录携带自己的 `currency` 字段，金额不做转换，让 AI 自己理解混合币种场景。

**优点**：
- 数据最准确，不丢失原始信息
- 用户问 "我的美元资产有多少" 时 AI 能直接回答

**缺点**：
- AI 可能误解混合币种数据（需要更复杂的提示词）
- 快照汇总类数据（如 `net_worth`）仍需转换
- AI 提示词长度增加

**改动范围**：

| 文件 | 改动 |
|------|------|
| `ai_context_builder.py` | 每个 builder 输出 `currency` 字段，`_fmt_money()` 动态符号 |
| `asset.py` (MCP) | 加 `currency` 字段 |
| `liability.py` (MCP) | 加 `currency` 字段 |
| `finance_coach_snapshot.py` | 每条记录加 `currency`，但汇总类数据仍需转换 |
| `wish_advice.py` | 每条心愿加 `currency` |

---

### 方案 C：混合方案（快照转 + MCP 保留）

**思路**：
- **快照类数据**（finance_coach、wish_advice）：统一转为 `default_currency`
- **MCP 查询类数据**（get_assets、get_liabilities）：保留原始币种 + 标注

**优点**：
- 平衡了准确性和简洁性
- AI 报告能识别原始币种

**缺点**：
- 两套逻辑，维护成本高
- AI 可能混淆两种数据来源

---

## 三、推荐方案：A（统一转换）

### 3.1 设计原则

1. **AI 不应关心汇率**：AI 的职责是分析趋势、提供建议，不是做货币换算
2. **一致性优先**：所有金额在同一币种下，AI 逻辑更简单
3. **显式标注**：即使转换了，也要告诉 AI 当前是什么币种

### 3.2 实现任务

#### 任务 1：修复 AI Context Builder（P0）

```python
# ai_context_builder.py 修改点

def build_family_context(db: Session, user: User) -> str:
    default_currency = user.default_currency or "CNY"
    # 传递给所有 builder

def _fmt_money(v: Any, currency: str) -> str:
    """Format with dynamic currency symbol."""
    f = _dec(v)
    if f is None:
        return "未设置"
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{symbol}{f:,.2f}"

def build_liability_detail(db: Session, user: User, default_currency: str) -> str:
    for liab in liabilities:
        converted = ExchangeRateService.convert(
            float(liab.remaining_amount), liab.currency, default_currency, db
        )
        lines.append(f"- {liab.name}: {_fmt_money(converted, default_currency)} ({liab.currency} → {default_currency})")
```

#### 任务 2：修复 MCP 工具（P0）

```python
# asset.py - list_assets_for_family()

def list_assets_for_family(db: Session, user: User) -> list[dict]:
    default_currency = user.default_currency or "CNY"
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "category": a.category,
            "current_value": ExchangeRateService.convert(
                float(a.current_value or 0), a.currency, default_currency, db
            ),
            "original_currency": a.currency,  # 保留原始币种供参考
        }
        for a in rows
    ]
```

#### 任务 3：修复理财教练快照（P0）

```python
# finance_coach_snapshot.py

def build_family_finance_snapshot(db: Session, user: User) -> dict:
    default_currency = user.default_currency or "CNY"
    
    total_assets = sum(
        ExchangeRateService.convert(float(a.current_value or 0), a.currency, default_currency, db)
        for a in assets
    )
    # 类似处理所有金额...
    
    return {
        "currency": default_currency,  # 标注币种
        "net_worth": net_worth,
        # ...
    }
```

#### 任务 4：修复心愿建议快照（P0）

同上，统一转换 + 标注币种。

#### 任务 5：Dashboard 响应加币种字段（P1）

```python
# schemas/dashboard.py

class OverviewResponse(BaseModel):
    currency: str  # 新增
    total_assets: float
    total_liabilities: float
    # ...
```

### 3.3 边界情况处理

| 情况 | 处理 |
|------|------|
| 汇率缺失 | `convert()` 返回原始金额，日志警告，响应中标注 `rate_missing: true` |
| 单币种用户 (CNY only) | 转换为 1:1，无额外开销 |
| 新币种（数据库无汇率） | 提示用户去设置获取汇率 |

### 3.4 测试验证

1. **单元测试**：为每个修改的函数添加多币种场景测试
2. **集成测试**：用多币种家庭数据验证 AI 报告输出
3. **E2E 测试**：模拟用户切换默认币种，验证 AI 响应变化

---

## 四、工作量估算

| 任务 | 预估工时 | 优先级 |
|------|----------|--------|
| 修复 AI Context Builder | 2h | P0 |
| 修复 MCP get_assets | 1h | P0 |
| 修复 MCP get_liabilities | 1h | P0 |
| 修复理财教练快照 | 2h | P0 |
| 修复心愿建议快照 | 1h | P0 |
| Dashboard 响应加币种 | 0.5h | P1 |
| 单元测试 | 2h | P0 |
| 集成测试 | 1h | P1 |
| **总计** | **10.5h** | - |

---

## 五、待决策项

1. **是否保留原始币种字段？**
   - 推荐：保留 `original_currency` 字段供调试/审计，但不影响 AI 逻辑

2. **汇率缺失时是否阻断 AI 调用？**
   - 推荐：不阻断，返回原始金额 + 警告标记，让 AI 继续但提示用户

3. **AI Context 文本格式**
   - 方案 A：纯文本，如 `净资产: ¥1,000,000 (已转换为人民币)`
   - 方案 B：结构化 JSON，让 AI 解析

---

## 六、附录：相关文件清单

```
server/apps/backend/app/services/ai_context_builder.py
server/apps/backend/app/services/asset.py
server/apps/backend/app/services/liability.py
server/apps/backend/app/services/finance_coach_snapshot.py
server/apps/backend/app/services/wish_advice.py
server/apps/backend/app/schemas/dashboard.py
server/apps/backend/app/services/mcp_session.py
server/packages/domain/exchange_rate/service.py
```