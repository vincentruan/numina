---
date: 2026-04-15
topic: batch-partial-failure-tracking
---

# 批量操作部分失败追踪

## Problem Frame

现有 `BatchOperationResponse` 包含 `success_count`、`failed_count`、`errors: list[str]`，但 `errors` 只是字符串列表，无法关联到具体资产 ID。用户执行批量归档/分类/标签/状态变更时，若部分失败，无法得知哪些资产失败了、原因是什么。

## Requirements

**后端：响应结构升级**

- R1. 将 `BatchOperationResponse.errors` 从 `list[str]` 升级为 `list[BatchItemError]`，新增 schema：
  ```
  class BatchItemError(BaseModel):
      id: int
      error_code: str
      message: str
  ```
- R2. 新增 `partial: bool` 字段，当 `failed_count > 0` 且 `success_count > 0` 时为 `True`，全部失败时为 `False`。
- R3. 更新 `asset_service` 中的 batch 方法（`batch_archive_assets`、`batch_update_category`、`batch_update_tags`、`batch_update_status`），对每个 asset_id 单独处理并捕获异常，将失败项记录为 `BatchItemError`（使用 #1 定义的 `ErrorCode`），不因单项失败而中断整批操作。

**前端：部分失败展示**

- R4. axios interceptor 或调用方检测到响应中 `partial: true` 时，显示摘要 toast：`"X 项成功，Y 项失败"`，并在 toast 下方提供"查看详情"入口（可展开显示失败项列表）。
- R5. 全部失败（`success_count === 0`）时，显示错误 toast：`"操作失败，共 Y 项未能完成"`。

## Success Criteria

- 批量操作响应中失败项包含 `id`、`error_code`、`message` 三个字段
- 部分失败时前端展示成功/失败数量摘要
- 单项失败不中断整批操作

## Scope Boundaries

- 只覆盖 `assets` 的 4 个 batch 端点（archive、category、tags、status），不包含 `batch/export`
- 不提供失败项的自动重试功能
- 不修改 `BatchExportResponse`

## Key Decisions

- **逐项处理不中断**：批量操作改为逐项 try/except，保证部分成功的结果不被丢弃
- **`partial` 字段明确区分部分失败与全部失败**：前端可据此选择不同的提示策略

## Dependencies / Assumptions

- 依赖 #1 完成（ErrorCode enum 已定义，错误消息已有翻译）
- 现有 batch service 方法需要重构为逐项处理，可能影响数据库事务边界（planning 阶段需确认是否每项独立事务）

## Outstanding Questions

### Deferred to Planning

- [影响 R3][技术] 现有 batch service 方法是否在单个数据库事务中处理所有 asset_id？改为逐项处理后，事务边界如何调整？

## Next Steps

→ 与 #1–#4 合并到同一个 `/ce:plan` 中规划实现
