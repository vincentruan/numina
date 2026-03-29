## Why

OpenSpec 深度审查发现，当前 6 个 spec 文件的 `Purpose` 字段全部为 `TBD`，只有高层 SHALL 语句，没有实际内容。同时，多个已实现的核心功能完全没有 spec 记录，包括：心愿单系统、多币种支持、资产生命周期、数据导入导出、活动日志等。这导致 spec 文件与实际代码之间存在巨大鸿沟，无法发挥文档的指导作用。

## What Changes

- 填写所有现有 spec 的 `Purpose` 字段
- 新增 `wish-system` spec：心愿单 CRUD + realize 操作
- 新增 `multi-currency` spec：多币种 + 汇率自动更新
- 新增 `data-lifecycle` spec：资产状态机
- 新增 `data-portability` spec：CSV/JSON 导入导出
- 新增 `observability` spec：Activity 日志 + 快照服务
- 新增 `i18n` spec：国际化架构
- 完善 `data-models` spec：补充 Wish、Activity、AssetValuation、PaymentRecord、Currency、ExchangeRate 实体
- 完善 `api-spec` spec：补充缺失端点

## Capabilities

### New Capabilities

- `wish-system`: 心愿单系统，包括 CRUD、优先级管理、心愿实现为资产
- `multi-currency`: 多币种支持，包括币种管理、汇率更新、金额换算
- `data-lifecycle`: 资产生命周期管理，包括状态机、卖出流程、退役流程
- `data-portability`: 数据导入导出，包括 CSV/JSON 格式、导入校验
- `observability`: 可观测性，包括活动日志、快照服务
- `i18n`: 国际化支持，包括多语言、本地化格式

### Modified Capabilities

- `data-models`: 补充 Wish、Activity、AssetValuation、PaymentRecord、Currency、ExchangeRate 实体定义
- `api-spec`: 补充心愿、活动、导出、导入、上传、币种模块端点
- `architecture`: 更新 Purpose，补充多数据库、定时任务、文件上传架构

## Impact

- 完善 OpenSpec 文档体系
- 为 Claude Code 提供完整的项目上下文
- 不影响现有代码功能
- 提升文档与代码的一致性