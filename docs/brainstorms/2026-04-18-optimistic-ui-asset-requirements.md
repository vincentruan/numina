---
date: 2026-04-18
topic: optimistic-ui-asset
---

# Optimistic UI for Asset Operations

## Problem Frame

移动端弱网场景下，用户点击"保存/删除"后等待 1-2 秒才能看到结果，这感觉像"卡住"或"bug"。金融资产管理应该有即时反馈，即使网络延迟。

**Who is affected:** 所有在移动网络（3G/4G）下使用 Numina 的家庭成员
**What is changing:** Asset 创建/更新/删除操作从 pessimistic（等待服务端确认）改为 optimistic（立即更新 UI，后台同步）
**Why it matters:** 移动 UX 的核心痛点，每次写操作的感知延迟直接影响用户信任度

## Requirements

**乐观更新触发条件**
- R1. 创建资产时立即将临时资产对象添加到 `assets` 列表顶部
- R2. 更新资产时立即在 `assets` 列表中替换对应项
- R3. 删除资产时立即从 `assets` 列表中移除对应项

**失败回滚行为**
- R4. 服务端返回错误时，立即撤销 UI 变更恢复到操作前状态
- R5. 显示 Toast 提示错误信息（使用 Vant `showToast`）
- R6. 不阻塞后续操作，用户可以继续编辑其他资产

**临时 ID 处理**
- R7. 创建资产的临时对象使用客户端生成的 UUID（`crypto.randomUUID()`）
- R8. 服务端成功返回后，替换临时 ID 为真实 ID（保持列表位置不变）

**Dashboard 同步策略**
- R9. 乐观更新仅影响 `assets` 列表，不主动刷新 Dashboard 概览数据
- R10. Dashboard 数据在 2 分钟 TTL 过期后自动重新获取（依赖现有 staleness guard）

**不适用乐观更新的操作**
- R11. 资产价值更新（`updateValue`）保持 pessimistic — Dashboard 依赖精确数值
- R12. 资产出售（`sellAsset`）保持 pessimistic — 涉及复杂业务逻辑
- R13. 负债操作（Liability）全部保持 pessimistic — 降低实现复杂度

## Success Criteria

- 用户点击"保存"后立即看到资产列表更新（感知延迟 < 100ms）
- 服务端拒绝时用户明确看到错误提示，UI 恢复正确状态
- 并发操作（快速连续创建/删除）不产生 UI 状态混乱
- Dashboard 概览在资产变更后最多 2 分钟内反映真实数据

## Scope Boundaries

- **不处理并发冲突** — 家庭成员同时编辑同一资产时，后提交者覆盖前者（服务端无乐观锁）
- **不实现操作队列** — 失败的操作不自动重试，用户手动重试
- **不处理网络断开** — 网络完全断开时请求失败，按 R4-R6 回滚处理
- **不同步计算 Dashboard** — 避免前端复杂聚合逻辑，等待 TTL 刷新

## Key Decisions

- **仅 Asset 启用乐观更新**：Liability 操作频率低，降低实现复杂度
- **静默回滚 + Toast**：不保留"失败状态"UI，立即恢复避免用户困惑
- **Dashboard 非同步更新**：依赖现有 staleness guard，避免前端聚合逻辑复杂化
- **价值更新不乐观**：Dashboard overview 依赖精确数值，乐观更新会导致概览与明细不一致

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Technical] 创建资产时临时对象哪些字段必须预填充（name、category_id 等）vs 等待服务端返回
- [Affects R7][Technical] 临时 UUID 生成时机：函数入口 vs API 调用前
- [Affects R4][Technical] 回滚时是否需要保存操作前的完整状态快照，还是仅记录变更的资产 ID

## Next Steps

→ `/ce:plan` for structured implementation planning