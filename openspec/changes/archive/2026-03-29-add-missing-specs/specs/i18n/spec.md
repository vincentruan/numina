# i18n Specification

## Purpose

国际化系统支持多语言界面，当前支持简体中文和英文，允许用户切换界面语言，并提供本地化的货币、日期格式显示。

## ADDED Requirements

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

## Supported Languages

| 语言代码 | 语言名称 | 完成度 |
|----------|----------|--------|
| zh-CN | 简体中文 | 100% |
| en-US | English | 100% |

## File Structure

```
frontend/src/i18n/
├── index.ts           # i18n 配置
└── locales/
    ├── zh-CN.ts       # 简体中文翻译
    └── en-US.ts       # 英文翻译
```

## Translation Key Convention

```
模块.功能.具体文本

示例：
- asset.title          → "资产"
- asset.status.in_use  → "服役中"
- common.save          → "保存"
- error.network        → "网络错误"
```

## Frontend Usage

```vue
<template>
  <h1>{{ $t('asset.title') }}</h1>
  <p>{{ $t('asset.status.in_use') }}</p>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { locale, t } = useI18n()

// 切换语言
function switchLanguage(lang) {
  locale.value = lang
}
</script>
```

## Localized Formats

| 类型 | 中文 | 英文 |
|------|------|------|
| 货币 | ¥1,234.56 | ¥1,234.56 |
| 日期 | 2026年3月29日 | Mar 29, 2026 |
| 数字 | 1,234.56 | 1,234.56 |