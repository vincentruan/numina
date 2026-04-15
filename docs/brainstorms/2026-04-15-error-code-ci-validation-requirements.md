---
date: 2026-04-15
topic: error-code-ci-validation
---

# Error Code CI 完整性验证

## Problem Frame

#1 建立了 ErrorCode enum 和语言文件，但没有机制防止后续开发者：
- 新增 ErrorCode 但忘记在语言文件中添加对应翻译
- 在 router 中重新引入裸 `HTTPException(detail="中文字符串")`

随着时间推移，这两种情况都会悄悄破坏 i18n 体系。

## Requirements

- R1. 在 `backend/tests/test_error_codes.py` 中新增 pytest 测试，验证 `ErrorCode` enum 中每个枚举值在 `zh-CN.json` 和 `en-US.json` 中均有对应 key。测试失败时输出缺失的 key 列表。
- R2. 同文件新增测试，扫描 `backend/app/routers/` 目录下所有 `.py` 文件，断言不存在 `HTTPException(` 调用（使用 `ast` 模块解析，不做字符串匹配）。允许通过注释 `# noqa: allow-http-exception` 豁免个别行（用于 FastAPI 内部兼容场景）。
- R3. 上述测试纳入现有 `uv run pytest tests/ -v` 命令，无需额外 CI 步骤。

## Success Criteria

- 新增 ErrorCode 但未更新语言文件时，`pytest` 失败并列出缺失 key
- router 中出现裸 `HTTPException` 调用时，`pytest` 失败并列出违规文件和行号
- 现有 CI workflow 无需修改

## Scope Boundaries

- 不检查 `ValidationCode`（字段级校验码，数量多且变化频繁）
- 不检查 agent 模块
- 不检查前端代码

## Key Decisions

- **用 `ast` 模块而非字符串匹配检查 HTTPException**：避免注释或字符串中的误报
- **豁免注释 `# noqa: allow-http-exception`**：为极少数必须使用原生 HTTPException 的场景留出出口

## Dependencies / Assumptions

- 依赖 #1 完成（ErrorCode enum 和语言文件已存在）

## Next Steps

→ 与 #1–#5 合并到同一个 `/ce:plan` 中规划实现
