# i18n Specification

## Purpose
TBD - created by archiving change add-missing-specs. Update Purpose after archive.
## Requirements
### Requirement: 系统必须支持多语言

系统 SHALL 支持至少两种语言：简体中文（zh-CN）和英文（en-US）。

#### Scenario: 用户切换语言

- **WHEN** 用户在设置中选择语言
- **THEN** 所有界面文本切换为对应语言

### Requirement: 翻译 key 必须遵循命名约定

翻译 key SHALL 使用点分隔的层级命名格式：`模块.功能.具体文本`。

#### Scenario: 翻译 key 命名

- **WHEN** 开发者添加新翻译
- **THEN** 使用格式如 `asset.status.in_use` 而非 `assetStatusInUse`

### Requirement: 货币和日期必须本地化显示

金额和日期 SHALL 根据用户区域设置格式化显示。

#### Scenario: 金额格式化

- **WHEN** 显示金额
- **THEN** 中文用户显示 ¥1,234.56，英文用户显示 ¥1,234.56

#### Scenario: 日期格式化

- **WHEN** 显示日期
- **THEN** 中文用户显示 2026年3月29日，英文用户显示 Mar 29, 2026

