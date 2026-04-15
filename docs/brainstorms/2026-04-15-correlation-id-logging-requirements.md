---
date: 2026-04-15
topic: correlation-id-structured-logging
---

# Correlation ID + 结构化错误日志

## Problem Frame

当用户报告错误时，目前无法将前端错误与服务端日志关联。日志中缺少请求上下文（user_id、endpoint、error_code），排查问题需要靠时间戳猜测。本需求在 #1 的全局异常处理器基础上，为每个请求注入唯一 ID，并在错误日志中携带关键上下文字段。

## Requirements

**Middleware**

- R1. 新增 `RequestIDMiddleware`（在 `backend/app/middleware/` 中），对每个请求生成 UUID4 作为 `request_id`，存入 `request.state.request_id`。若请求头已携带 `X-Request-ID`，则使用该值（允许客户端传入，便于端到端追踪）。
- R2. 所有响应（成功和错误）均在响应头中返回 `X-Request-ID`。

**错误响应扩展**

- R3. 全局异常处理器（#1 中定义）在错误 envelope 中加入 `request_id` 字段：`{ "code": str, "message": str, "data": null, "request_id": str }`。成功响应 envelope 不包含 `request_id`（通过响应头获取即可）。

**日志**

- R4. 全局异常处理器记录错误日志时，在日志消息中包含以下字段：`request_id`、`error_code`、`endpoint`（`request.url.path`）、`method`（HTTP method）、`user_id`（若已认证，从 `request.state` 获取；未认证则为 `anonymous`）。格式为现有文本日志，字段以 key=value 形式附加。
- R5. 日志级别：`AppError` 记录为 `WARNING`（业务错误，非系统故障）；未预期异常（非 `AppError`、非 `HTTPException`）记录为 `ERROR` 并包含完整 traceback。

**前端**

- R6. 前端 axios interceptor 在错误 toast 下方（或"复制错误详情"按钮）展示 `request_id`，格式为：`错误 ID: xxxxxxxx`（取 UUID 前 8 位即可）。用户可长按复制完整 ID 用于反馈。

## Success Criteria

- 每个 API 请求的响应头中包含 `X-Request-ID`
- 错误响应 envelope 包含 `request_id`
- 错误日志包含 `request_id`、`error_code`、`endpoint`、`user_id` 字段
- 前端错误提示中展示缩短的 `request_id`

## Scope Boundaries

- 不引入分布式追踪系统（OpenTelemetry、Jaeger 等）
- 不修改成功响应 envelope（`request_id` 只在错误响应体中，成功响应通过响应头获取）
- 不对所有日志做结构化改造，只在错误处理路径上添加上下文字段
- WebSocket 连接不在范围内

## Key Decisions

- **request_id 包含在错误响应体中**：前端可直接读取并展示给用户，无需解析响应头
- **文本日志 + key=value 字段**：不改变现有日志基础设施，改动最小
- **AppError 记录为 WARNING**：业务错误（资产不存在、权限不足）不应触发告警，只有未预期异常才是 ERROR

## Dependencies / Assumptions

- 依赖 #1 完成（全局异常处理器已存在）
- `user_id` 需从 `request.state` 获取，要求认证中间件在处理请求时将 user_id 写入 `request.state`（需在 planning 阶段确认现有认证流程是否已做此操作）

## Outstanding Questions

### Deferred to Planning

- [影响 R4][需调研] 现有认证流程（`get_current_user` dependency）是否将 `user_id` 写入 `request.state`？若否，全局异常处理器如何获取当前用户 ID？

## Next Steps

→ 与 #1、#2 合并到同一个 `/ce:plan` 中规划实现
