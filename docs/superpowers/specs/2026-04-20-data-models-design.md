# Data Models Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 数据库实体关系模型和字段定义

---

## Problem

数据模型缺乏统一文档，开发者难以理解实体边界和关系。新成员无法快速定位字段定义，导致实现不一致和潜在的架构问题。

---

## Goals

1. 定义核心实体及其关系
2. 规范字段定义和约束
3. 提供清晰的实体边界说明
4. 支持业务逻辑实现参考

---

## Architecture

### 实体关系图

系统核心实体：User、Family、Asset、Category、Liability、Wish、Activity、AssetValuation、PaymentRecord、Currency、ExchangeRate。

主要关系：
- Family 1:N User（一个家庭多个用户）
- Family 1:N Category（自定义分类）
- Family 1:N AssetSnapshot
- User 1:N Asset（用户拥有资产）
- User 1:N Liability（用户拥有负债）
- User 1:N Wish（用户拥有心愿）
- Asset N:1 Category（资产属于分类）
- Asset N:M Tag（资产多对多标签）
- Liability N:1 Asset（负债可关联资产）
- Wish N:1 Category（心愿属于分类）

### 资产分类体系

系统预定义 21 个资产分类（seeded on startup）：

**实物分类（13个）**：
🏠房产, 🚗车辆, 📱数码, 📺家电, 🛋️家具, 💎珠宝, 👔服饰, 💄美妆, ⚽运动, 🎮玩具, 🐾宠物, 🎸乐器, 👜箱包

**金融分类（8个）**：
🏦存款, 📊基金, 📈股票, 📜债券, 🛡️保险, 💰理财产品, ₿数字货币, 💳其他金融

---

## Implementation Details

### 核心实体定义

#### User
```python
class User(Base):
    id: Mapped[str]
    family_id: Mapped[str]  # FK -> families.id
    username: Mapped[str]   # unique
    display_name: Mapped[str]
    role: Mapped[str]       # 'admin' | 'member'
    avatar_color: Mapped[str]
    default_currency: Mapped[str] = mapped_column(default="CNY")
```

#### Asset
```python
class Asset(Base):
    id: Mapped[str]
    family_id: Mapped[str]  # FK -> families.id
    user_id: Mapped[str]    # FK -> users.id
    category_id: Mapped[str]  # FK -> categories.id
    name: Mapped[str]
    asset_type: Mapped[str]  # 'physical' | 'financial'
    status: Mapped[str]      # 'in_use' | 'idle' | 'sold' | 'retired'
    
    # 价值字段
    purchase_price: Mapped[float]
    current_value: Mapped[float]
    currency: Mapped[str] = mapped_column(default="CNY")
    
    # 出售字段
    sell_price: Mapped[float | None]
    sell_date: Mapped[date | None]
    sell_fee: Mapped[float | None]
    sell_channel: Mapped[str | None]
    
    # 退役字段
    retire_date: Mapped[date | None]
    target_daily_cost: Mapped[float | None]
    
    # 计算字段参数
    expected_lifespan_days: Mapped[int | None]
    annual_maintenance_cost: Mapped[float | None]
    usage_frequency: Mapped[str | None]  # 'daily' | 'weekly' | 'monthly' | 'rarely' | 'idle'
```

#### Wish
```python
class Wish(Base):
    id: Mapped[str]
    family_id: Mapped[str]  # FK -> families.id
    user_id: Mapped[str]    # FK -> users.id
    category_id: Mapped[str | None]  # FK -> categories.id
    name: Mapped[str]
    description: Mapped[str | None]
    expected_price: Mapped[float]
    currency: Mapped[str] = mapped_column(default="CNY")
    priority: Mapped[str]   # 'high' | 'medium' | 'low'
    status: Mapped[str]     # 'pending' | 'realized' | 'cancelled'
    realized_asset_id: Mapped[str | None]  # FK -> assets.id
```

#### Activity
```python
class Activity(Base):
    id: Mapped[str]
    family_id: Mapped[str]  # FK -> families.id
    user_id: Mapped[str]    # FK -> users.id
    type: Mapped[str]       # 'create' | 'update' | 'delete' | 'sell' | 'retire' | 'payment'
    entity_type: Mapped[str]  # 'asset' | 'liability' | 'wish'
    entity_id: Mapped[str]
    title: Mapped[str]
    amount: Mapped[float | None]
```

#### AssetValuation
```python
class AssetValuation(Base):
    id: Mapped[str]
    asset_id: Mapped[str]   # FK -> assets.id
    value: Mapped[float]
    valued_at: Mapped[date]
    notes: Mapped[str | None]
```

#### PaymentRecord
```python
class PaymentRecord(Base):
    id: Mapped[str]
    liability_id: Mapped[str]  # FK -> liabilities.id
    amount: Mapped[float]
    payment_date: Mapped[date]
    notes: Mapped[str | None]
```

#### Currency
```python
class Currency(Base):
    code: Mapped[str]        # Primary key: "CNY", "USD"
    name_zh: Mapped[str]     # "人民币"
    name_en: Mapped[str]     # "Chinese Yuan"
    symbol: Mapped[str]      # "¥"
    flag_emoji: Mapped[str]  # "🇨🇳"
    is_favorite: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=999)
```

#### ExchangeRate
```python
class ExchangeRate(Base):
    id: Mapped[str]
    base_currency: Mapped[str]   # Always "CNY"
    target_currency: Mapped[str]  # "USD", "EUR", etc.
    rate: Mapped[float]           # target units per 1 CNY
    fetched_at: Mapped[datetime]
```

### 计算字段

计算发生在 router 响应阶段，不存储在数据库：

- **daily_cost**: `(purchase_price + annual_maintenance_cost * years) / days_used`
- **return_rate**: `(current_value - purchase_price) / purchase_price * 100`（仅金融资产）

---

## Code Pointers

| 实体 | 文件路径 |
|------|----------|
| User | `backend/app/models/user.py` |
| Family | `backend/app/models/family.py` |
| Asset | `backend/app/models/asset.py` |
| Category | `backend/app/models/category.py` |
| Tag | `backend/app/models/tag.py` |
| Liability | `backend/app/models/liability.py` |
| Wish | `backend/app/models/wish.py` |
| Activity | `backend/app/models/activity.py` |
| AssetValuation | `backend/app/models/valuation.py` |
| PaymentRecord | `backend/app/models/payment.py` |
| Currency | `backend/app/models/currency.py` |
| ExchangeRate | `backend/app/models/exchange_rate.py` |
| Snapshot | `backend/app/models/snapshot.py` |

---

## Related Specs

- **生命周期设计**：`2026-04-20-data-lifecycle-design.md` — Asset 状态流转
- **多币种设计**：`2026-03-24-multi-currency-design.md` — Currency、ExchangeRate 实体