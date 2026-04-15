---
date: 2026-04-15
topic: frontend-empty-catch-cleanup
---

# 前端空 catch 块清理

## Problem Frame

Vue 组件中存在空 `catch {}` 块和只做 `console.log` 的 catch 块，导致 API 调用失败时用户看到冻结的 UI，开发者也无从得知错误发生。axios interceptor 已集中处理错误，这些空 catch 块实际上是在压制它。

## Requirements

- R1. 扫描 `frontend/src/` 下所有 `.vue` 和 `.ts` 文件，找出所有空 `catch` 块（`catch {}` 或 `catch (e) {}`）和只含 `console.log`/`console.error` 的 catch 块。
- R2. 对于包裹 axios 调用的 try/catch：若 catch 块为空或只做 console 输出，直接删除整个 try/catch，让错误自然冒泡到 axios interceptor 处理。
- R3. 对于非 axios 调用的 try/catch（如本地计算、JSON 解析）：若 catch 块为空，补充最小错误处理（`console.error` + 合理的 fallback 值），不删除。
- R4. 清理完成后运行 `npm run build` 确认无类型错误，运行 `npm run lint` 确认无新增 lint 警告。

## Success Criteria

- `frontend/src/` 中不再有包裹 axios 调用的空 catch 块
- `npm run build` 和 `npm run lint` 通过

## Scope Boundaries

- 不引入新的错误处理机制，只做清理
- 不修改 axios interceptor 本身
- 不处理 WebSocket 相关的错误处理

## Key Decisions

- **axios 调用的 catch 直接删除**：interceptor 已处理，保留 catch 只会压制错误
- **非 axios 的空 catch 补充最小处理**：不能无声失败，但也不过度设计

## Dependencies / Assumptions

- 依赖 #1 完成（axios interceptor 已更新为统一错误处理）
- 可独立于其他想法单独执行，但建议在 #1 完成后进行

## Next Steps

→ 与 #1–#6 合并到同一个 `/ce:plan` 中规划实现，或作为独立的清理 PR
