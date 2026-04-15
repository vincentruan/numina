---
date: 2026-04-15
topic: validation-error-field-codes
---

# Validation Error 字段级错误码标准化

## Problem Frame

FastAPI 默认的 422 响应返回 Pydantic 的原始错误结构 `{ loc, msg, type }`，前端只能拼接 `msg` 字符串显示。本需求在 #1 的 R5 基础上，将 422 错误的 `details` 数组标准化为包含语义化 `code` 的结构，使前端可以程序化处理字段级错误（如高亮对应表单字段）。

## Requirements

**后端：422 错误转换**

- R1. 全局异常处理器捕获 `RequestValidationError` 时，将 Pydantic 的 `error.type`（如 `string_too_short`、`value_error`）映射为语义化的 `ValidationCode` 字符串常量（如 `TOO_SHORT`、`INVALID_FORMAT`、`REQUIRED`、`INVALID_VALUE`）。
- R2. 422 响应的 `details` 数组格式为：`[{ "field": str, "code": str, "msg": str }]`，其中：
  - `field`：字段路径，取 Pydantic `loc` 的最后一个元素（如 `"password"`，而非 `["body", "password"]`）
  - `code`：映射后的语义化错误码
  - `msg`：根据 `Accept-Language` 翻译后的字段错误描述
- R3. 在语言文件（`zh-CN.json`、`en-US.json`）中为 `ValidationCode` 添加对应消息，支持参数插值（如 `TOO_SHORT` 的消息为 `"长度至少 {min_length} 位"`）。
- R4. 未能映射的 Pydantic error type 统一归为 `INVALID_VALUE`，`msg` 使用 Pydantic 原始消息作为 fallback。

**前端：字段级错误展示**

- R5. axios interceptor 处理 422 错误时，将 `details` 数组存入一个响应式的 `validationErrors` 对象（key 为 `field`，value 为 `{ code, msg }`），通过 `provide/inject` 或 Pinia store 供表单组件读取。
- R6. 表单页面（`AssetFormPage.vue`、`LiabilityFormPage.vue`、`RegisterPage.vue` 等）可选择性地消费 `validationErrors`，在对应字段下方显示错误消息。若不消费，axios interceptor 仍会 fallback 到拼接 `msg` 显示 toast（与 #1 R8 行为一致）。

## Success Criteria

- 422 响应的 `details` 数组包含 `field`、`code`、`msg` 三个字段
- 常见 Pydantic error type（`string_too_short`、`missing`、`value_error`、`string_pattern_mismatch`）均有对应的语义化 `code`
- 前端表单页面可读取 `validationErrors` 并在字段级别展示错误

## Scope Boundaries

- 不要求所有表单页面都实现字段级展示，只提供机制，各页面按需接入
- 不处理嵌套对象的字段路径（只取 `loc` 最后一个元素）
- 不引入前端表单验证库（如 vee-validate）

## Key Decisions

- **field 取 loc 最后一个元素**：简化前端匹配逻辑，避免处理 `["body", "password"]` 这类嵌套路径
- **ValidationCode 独立于 ErrorCode**：字段级校验码与业务错误码是不同维度，分开定义避免 enum 膨胀
- **前端通过 provide/inject 传递 validationErrors**：不污染全局 Pinia store，表单组件按需消费

## Dependencies / Assumptions

- 依赖 #1 完成（全局异常处理器已存在，422 的基本 envelope 格式已定义）
- Pydantic v2 的 `error.type` 字段稳定，不会在小版本升级中变化

## Outstanding Questions

### Deferred to Planning

- [影响 R5][技术] `validationErrors` 通过 `provide/inject` 还是轻量 Pinia store 传递更合适？需结合现有 store 结构判断。
- [影响 R3][需调研] Pydantic v2 中 `string_too_short` 等 error type 是否携带 `ctx`（如 `min_length`）供消息插值使用？

## Next Steps

→ 与 #1、#2、#3 合并到同一个 `/ce:plan` 中规划实现
