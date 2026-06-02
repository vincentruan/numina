# Numina 项目本体方法论 (Project Ontology)

## 概述

本文档定义了 Numina（家庭资产可视化）项目的领域本体——即核心概念、它们之间的关系、以及约束规则。本体作为需求分析、系统设计和开发的统一语言基础。

## 核心领域划分

```
┌─────────────────────────────────────────────────────────────────┐
│                        Numina 领域模型                            │
├──────────────┬──────────────┬──────────────┬───────────────────┤
│  家庭与身份   │  资产与负债   │  儿童经济     │   AI 智能体       │
│              │              │              │                   │
│  Family      │  Asset       │  ChoreTemplate│  AIChatSession   │
│  User        │  Liability   │  ChoreInstance│  AIAgent         │
│  DeviceSession│  Category   │  CoinTransaction│ AIReport       │
│  InviteCode  │  Valuation   │  ChildWish   │  AITask          │
│              │  Wish        │  BlindBoxGift│  AIAlert         │
│              │  Tag         │  BlindBoxDraw│  AIExtraction    │
│              │  Snapshot    │  BlindBoxConfig│                 │
│              │  PaymentRecord│ ChildMilestone│                 │
│              │              │  BonusDraw   │                   │
└──────────────┴──────────────┴──────────────┴───────────────────┘
```

---

## 一、家庭与身份域 (Identity & Access)

### 实体

| 实体 | 核心属性 | 说明 |
|------|---------|------|
| **Family** | name, settings | 多租户隔离单元，所有数据归属于家庭 |
| **User** | display_name, email, role, family_id, is_child | 家庭成员，角色区分家长/孩子 |
| **DeviceSession** | device_fingerprint, user_id, is_trusted | 设备信任与会话管理 |
| **FamilyInvitationCode** | code, family_id, expires_at | 家庭邀请码 |

### 关系

```
Family ──1:N──→ User (has_member)
Family ──1:N──→ FamilyInvitationCode (has_invite)
User   ──1:N──→ DeviceSession (has_device)
```

### 约束

- 每个 User 必须属于且仅属于一个 Family
- Family 至少有一个 role=admin 的 User
- is_child=true 的 User 不能访问资产/负债管理功能
- 所有数据查询必须带 family_id 过滤（租户隔离）

---

## 二、资产与负债域 (Wealth Management)

### 实体

| 实体 | 核心属性 | 说明 |
|------|---------|------|
| **Asset** | name, asset_type(physical/financial), category_id, current_value, status, currency | 家庭资产 |
| **Liability** | name, category, original_amount, remaining_amount, monthly_payment, interest_rate | 家庭负债 |
| **Category** | name, asset_type, icon, family_id? | 资产分类（系统预设+家庭自定义） |
| **Valuation** | asset_id, value, valued_at | 资产估值历史 |
| **Wish** | name, expected_price, priority, status, converts_to_asset | 成人心愿（可转化为资产） |
| **Tag** | name, family_id | 资产标签 |
| **Snapshot** | family_id, total_assets, total_liabilities, net_worth, snapshot_date | 家庭净值快照 |
| **PaymentRecord** | liability_id, amount, paid_at | 还款记录 |
| **AssetLifecycleEvent** | asset_id, event_type, details | 资产生命周期事件 |

### 关系

```
Family   ──1:N──→ Asset (owns)
Family   ──1:N──→ Liability (owes)
Family   ──1:N──→ Category (has_category)
User     ──1:N──→ Asset (created_by)
User     ──1:N──→ Wish (wishes)
Asset    ──N:1──→ Category (categorized_as)
Asset    ──1:N──→ Valuation (has_valuation)
Asset    ──1:N──→ AssetLifecycleEvent (has_event)
Liability──N:1──→ Asset (linked_to, optional)
Liability──1:N──→ PaymentRecord (has_payment)
Wish     ──0:1──→ Asset (realized_as)
Asset    ──N:M──→ Tag (tagged_with)
Family   ──1:N──→ Snapshot (has_snapshot)
```

### 状态机

**Asset.status:**
```
in_use → idle → sold
  ↓              ↑
  └──→ retired ──┘
  (reactivate: sold/retired → in_use)
```

**Wish.status:**
```
pending → realized (creates Asset)
   ↓
cancelled
```

**Liability.is_active:**
```
active (is_active=true) → settled (is_active=false)
```

### 约束

- Asset.current_value ≥ 0
- Liability.remaining_amount ≥ 0
- Wish 实现时 converts_to_asset=true 则必须创建对应 Asset
- Category.asset_type ∈ {physical, financial}
- 所有金额字段默认 currency=CNY

---

## 三、儿童经济域 (Child Economy)

### 实体

| 实体 | 核心属性 | 说明 |
|------|---------|------|
| **ChoreTemplate** | name, emoji, coin_reward, frequency, assignment_type | 家务模板（家长定义） |
| **ChoreInstance** | template_id, child_user_id, date_bucket, status, streak_count | 家务实例（每日/每周生成） |
| **CoinTransaction** | child_user_id, transaction_type, amount, ref_id | 星币流水 |
| **ChildWish** | child_user_id, name, star_coin_cost, status | 儿童心愿（用星币兑换） |
| **ChildWishCostHistory** | wish_id, old_cost, new_cost | 心愿价格变更历史 |
| **BlindBoxConfig** | family_id, enabled, base_draw_prob, surprise_threshold_coins | 盲盒系统配置 |
| **BlindBoxGift** | name, emoji, value_score, source_wish_id?, is_active | 盲盒奖品池 |
| **BlindBoxDraw** | child_user_id, coins_spent, gift_id, is_surprise, status | 盲盒抽取记录 |
| **BonusDraw** | child_user_id, source_wish_id?, status, expires_at | 额外抽奖机会 |
| **ChildMilestone** | child_user_id, milestone_type, triggered_at | 里程碑成就 |
| **ChildEconomyConfig** | family_id, settings | 儿童经济系统配置 |
| **ChallengeGrant** | family_id, child_user_id, amount | 挑战奖励 |

### 关系

```
Family        ──1:N──→ ChoreTemplate (defines)
ChoreTemplate ──1:N──→ ChoreInstance (generates)
ChoreTemplate ──N:M──→ User[child] (assigned_to)
User[child]   ──1:N──→ ChoreInstance (performs)
User[child]   ──1:N──→ CoinTransaction (earns/spends)
User[child]   ──1:N──→ ChildWish (desires)
User[child]   ──1:N──→ BlindBoxDraw (draws)
User[child]   ──1:N──→ ChildMilestone (achieves)
Family        ──1:1──→ BlindBoxConfig (configures)
Family        ──1:N──→ BlindBoxGift (offers)
BlindBoxDraw  ──N:1──→ BlindBoxGift (wins)
ChildWish     ──0:1──→ BlindBoxGift (source_for)
ChildWish     ──1:N──→ ChildWishCostHistory (price_history)
```

### 状态机

**ChoreInstance.status:**
```
available → pending_approval → approved (coins awarded)
                    ↓
                rejected (return_to_redo → available)
```

Pool chores (assignment_type=pool):
```
available + is_pool_unclaimed → claimed (child claims) → pending_approval → ...
                                   ↓
                              abandoned (→ available again)
```

**ChildWish.status:**
```
pending → redemption_requested → realized (coins deducted, may create Asset)
   ↓              ↓
cancelled    rejected (→ pending)
```

**BlindBoxDraw.status:**
```
pending_fulfillment → fulfilled
```

**BonusDraw.status:**
```
available → used
    ↓
expired
```

### 经济循环

```
完成家务 → 获得星币 → 兑换心愿 / 盲盒抽奖
   ↑                        ↓
连续打卡(streak) → 额外奖励    奖品兑现(家长确认)
```

### 约束

- CoinTransaction.amount: 正数=收入，负数=支出
- 兑换心愿前必须检查余额 ≥ star_coin_cost
- ChoreInstance 只能由 is_child=true 的 User 完成
- ChoreInstance 审批只能由 is_child=false 的 User 执行
- BlindBoxGift.value_score ∈ [1, 10]
- streak_count 连续中断则重置为 0
- 盲盒抽取概率由 BlindBoxConfig 控制

---

## 四、AI 智能体域 (AI Agent)

### 实体

| 实体 | 核心属性 | 说明 |
|------|---------|------|
| **AIChatSession** | user_id, family_id, title | AI 对话会话 |
| **AIChatMessage** | session_id, role, content | 对话消息 |
| **AIAgent** | name, type, config | AI 代理配置 |
| **AIReport** | family_id, report_type, content | AI 生成的报告 |
| **AITask** | family_id, task_type, status, result | AI 异步任务 |
| **AIAssetAlert** | asset_id, alert_type, message | 资产智能提醒 |
| **AISpendingLeak** | family_id, category, amount, suggestion | 消费漏洞分析 |
| **AIAllocationTarget** | family_id, category, target_pct | 资产配置目标 |
| **AIAllocationDriftResult** | family_id, drift_pct, suggestion | 配置偏移检测 |
| **AIDisposalSuggestion** | asset_id, reason, suggested_action | 资产处置建议 |
| **AIExtractionAudit** | source, extracted_data, confidence | AI 提取审计 |
| **AIProviderConfig** | family_id, provider, model, api_key_ref | AI 服务配置 |

### 关系

```
Family         ──1:N──→ AIChatSession (has_session)
User           ──1:N──→ AIChatSession (initiates)
AIChatSession  ──1:N──→ AIChatMessage (contains)
Family         ──1:N──→ AIReport (receives)
Family         ──1:N──→ AITask (runs)
Asset          ──1:N──→ AIAssetAlert (triggers)
Asset          ──1:N──→ AIDisposalSuggestion (suggested_for)
Family         ──1:N──→ AISpendingLeak (detected_in)
Family         ──1:N──→ AIAllocationTarget (targets)
```

### 约束

- AI 功能基于 DeerFlow 框架
- AIProviderConfig 不存储明文密钥（使用 secret_ref）
- AITask 有超时机制
- AI 生成内容需标记来源（AIExtractionAudit.confidence）

---

## 五、跨域关系

```
Wish ──realizes──→ Asset (成人心愿实现转资产)
ChildWish ──realizes──→ Asset (儿童心愿兑现转资产，家长确认)
Liability ──linked_to──→ Asset (负债关联资产，如房贷关联房产)
BlindBoxGift ──source_from──→ ChildWish (心愿可作为盲盒奖品来源)
AIAssetAlert ──monitors──→ Asset (AI 监控资产状态)
AIDisposalSuggestion ──targets──→ Asset (AI 建议处置)
Snapshot ──aggregates──→ Asset + Liability (定期快照净值)
```

---

## 六、设计原则

### 1. 多租户隔离 (Tenant Isolation)

所有实体必须通过 `family_id` 隔离。查询层面强制过滤，不依赖应用层逻辑。

### 2. 角色分离 (Role Separation)

| 角色 | 可访问域 |
|------|---------|
| 家长 (admin) | 全部四个域 |
| 家长 (member) | 资产负债域（只读AI域） |
| 孩子 (child) | 仅儿童经济域 |

### 3. 状态驱动 (State-Driven)

所有核心实体使用显式状态机。状态转换必须通过服务层方法，不允许直接修改状态字段。

### 4. 经济闭环 (Closed Economy)

儿童经济系统是封闭的：
- 星币只能通过家务获得
- 星币只能通过心愿兑换或盲盒消耗
- 家长控制所有参数（奖励金额、概率、价格）

### 5. 资产生命周期 (Asset Lifecycle)

资产从创建到处置的完整生命周期被追踪：
- 创建来源（手动/心愿实现/AI提取）
- 估值变化（Valuation 时间序列）
- 状态变迁（AssetLifecycleEvent）
- 最终处置（出售/报废）

### 6. AI 辅助决策 (AI-Assisted)

AI 不直接修改数据，只生成建议：
- 资产提醒 → 用户确认后操作
- 处置建议 → 用户决定是否执行
- 消费分析 → 展示洞察，不自动调整

---

## 七、本体应用指南

### 需求分析时

1. 新需求涉及哪个域？是否跨域？
2. 需要新增实体还是扩展现有实体？
3. 新关系是否破坏现有约束？
4. 状态机是否需要新增状态或转换？

### 系统设计时

1. 数据模型是否符合本体定义？
2. API 边界是否与域边界对齐？
3. 权限控制是否遵循角色分离？
4. 跨域操作是否有事务保证？

### 开发实现时

1. 新代码是否在正确的模块中？（按域组织）
2. 查询是否带 family_id 过滤？
3. 状态变更是否通过服务层？
4. 是否有对应的测试覆盖状态转换？

---

## 八、术语表

| 中文 | 英文 | 说明 |
|------|------|------|
| 家庭 | Family | 多租户单元 |
| 资产 | Asset | 有价值的物品或金融产品 |
| 负债 | Liability | 贷款、信用卡等欠款 |
| 心愿 | Wish | 想要购买的东西 |
| 家务 | Chore | 孩子可完成的任务 |
| 星币 | Star Coin | 儿童虚拟货币 |
| 盲盒 | Blind Box | 随机奖励机制 |
| 连续打卡 | Streak | 连续完成家务的天数 |
| 里程碑 | Milestone | 成就系统触发点 |
| 净值 | Net Worth | 总资产 - 总负债 |
| 快照 | Snapshot | 某时刻的净值记录 |
| 估值 | Valuation | 资产当前价值评估 |
