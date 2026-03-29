# data-models MODIFIED Specification

## ADDED Requirements

### Requirement: 数据模型必须包含 Wish 实体

Wish 实体 SHALL 包含 id, family_id, user_id, name, description, expected_price, priority, status, category_id, currency, realized_asset_id 字段。

#### Scenario: 创建心愿记录

- **WHEN** 用户创建心愿
- **THEN** 系统创建 Wish 记录，status 默认为 pending

### Requirement: 数据模型必须包含 Activity 实体

Activity 实体 SHALL 记录用户操作历史，包含 id, family_id, user_id, type, entity_type, entity_id, title, amount 字段。

#### Scenario: 记录操作日志

- **WHEN** 用户执行资产操作
- **THEN** 系统创建 Activity 记录

### Requirement: 数据模型必须包含 AssetValuation 实体

AssetValuation 实体 SHALL 记录资产估值历史，包含 id, asset_id, value, valued_at, notes 字段。

#### Scenario: 记录估值变更

- **WHEN** 用户更新资产当前价值
- **THEN** 系统创建 AssetValuation 记录

### Requirement: 数据模型必须包含 PaymentRecord 实体

PaymentRecord 实体 SHALL 记录负债还款历史，包含 id, liability_id, amount, payment_date, notes 字段。

#### Scenario: 记录负债还款

- **WHEN** 用户记录负债还款
- **THEN** 系统创建 PaymentRecord 记录，更新负债剩余金额

### Requirement: 数据模型必须包含 Currency 实体

Currency 实体 SHALL 定义支持的币种，包含 code, name_zh, name_en, symbol, flag_emoji, is_favorite, sort_order 字段。

#### Scenario: 查询支持的币种

- **WHEN** 用户选择币种
- **THEN** 系统返回 Currency 列表

### Requirement: 数据模型必须包含 ExchangeRate 实体

ExchangeRate 实体 SHALL 记录汇率数据，包含 id, from_currency, to_currency, rate, fetched_at, source 字段。

#### Scenario: 查询汇率

- **WHEN** 系统进行货币换算
- **THEN** 使用最新的 ExchangeRate 记录

### Requirement: Asset 必须支持出售相关字段

Asset SHALL 包含 sell_price, sell_date, sell_fee, sell_channel 字段用于记录出售信息。

#### Scenario: 记录资产出售

- **WHEN** 用户出售资产
- **THEN** 填写出售相关字段，状态变为 sold

### Requirement: Asset 必须支持退役相关字段

Asset SHALL 包含 retire_date, target_daily_cost 字段用于记录退役信息。

#### Scenario: 记录资产退役

- **WHEN** 用户退役资产
- **THEN** 填写 retire_date，状态变为 retired