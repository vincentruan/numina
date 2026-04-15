---
date: 2026-04-15
topic: storage-error-http-bridge
---

# Storage 异常层级桥接到 HTTP 层

## Problem Frame

`backend/app/services/storage/base.py` 已定义了完整的 StorageError 层级（`StorageRateLimitError`、`StorageConflictError`、`StorageConnectionError`、`StorageAuthError`），但这些异常从未到达 HTTP 层——router 必须手动 catch 并重新抛出 `HTTPException`，导致 `StorageRateLimitError.reset_at` 等有价值的字段被丢弃，且错误处理逻辑分散在各 router 中。

本需求依赖 #1（统一错误码系统）已完成，在其基础上扩展。

## Requirements

**ErrorCode 扩展**

- R1. 在 `backend/app/errors/codes.py` 的 `ErrorCode` enum 中新增 Storage 相关错误码：
  - `STORAGE_RATE_LIMITED`（429）
  - `STORAGE_CONFLICT`（409）
  - `STORAGE_CONNECTION_ERROR`（503）
  - `STORAGE_AUTH_ERROR`（401）
  - `STORAGE_ERROR`（500，通用兜底）
- R2. 在语言文件（`zh-CN.json`、`en-US.json`）中为上述错误码添加对应消息。

**全局异常处理器扩展**

- R3. 在 `main.py` 的全局异常处理器中注册 `StorageError` 的处理逻辑：按子类类型映射到对应 `ErrorCode`，未匹配子类 fallback 到 `STORAGE_ERROR`。
- R4. `StorageRateLimitError` 映射时，若 `reset_at` 字段非空，将其作为 `details` 字段包含在 envelope 响应中：`{ "code": "STORAGE_RATE_LIMITED", "message": "...", "data": null, "details": { "reset_at": <timestamp> } }`。

**Router 清理**

- R5. 移除各 router 中手动 catch `StorageError` 并重新抛出 `HTTPException` 的代码块。让异常自然冒泡到全局处理器。

## Success Criteria

- `StorageError` 及其子类抛出后无需 router 手动处理，全局处理器统一转换为 envelope 格式
- `StorageRateLimitError` 的 `reset_at` 字段出现在响应的 `details` 中
- 现有后端测试（含 storage 相关测试）全部通过

## Scope Boundaries

- 不修改 `StorageError` 类本身的定义（不让它继承 `AppError`）
- 不处理 Agent 模块中的 storage 错误
- 不为 storage 错误添加前端重试逻辑（属于想法 #7 范围）

## Key Decisions

- **映射在全局处理器中维护**（而非让 StorageError 继承 AppError）：保持 storage 层与 HTTP 层解耦，storage 服务不依赖 `app/errors/` 模块
- **StorageRateLimitError.reset_at 通过 details 字段透传**：不丢弃已有信息

## Dependencies / Assumptions

- 依赖 #1 完成（ErrorCode enum 和全局处理器已存在）
- `StorageError` 子类在 router 调用链中自然冒泡，不被中间层吞掉

## Next Steps

→ 与 #1 合并到同一个 `/ce:plan` 中规划实现
