---
date: 2026-05-27
topic: wish-asset-modeling
---

# Wish 模型资产化

## Summary

补全心愿与资产之间的双向关联：新增 `fulfilled_at` 实现时间戳、`Asset.from_wish_id` 反向引用、父端心愿详情跳转链接，以及子端跳转（路由方案确认后）。让心愿实现在父母和孩子两侧都形成可见的时间锚点和导航入口。

---

## Problem Frame

当前系统记录了心愿转为资产的事件（`Wish.realized_asset_id`），但这条链接是单向且无时间信息的：

- 父母在心愿详情页看到"已转为资产"字样，但无法点击跳转到资产详情。
- `Asset` 侧无法反溯"这件东西来自哪个心愿"，家庭账本缺少这条故事线。
- 心愿何时实现无记录，父母侧时间线缺少锚点，AI 顾问和日历视图对心愿事件盲区。
- 孩子端只看到 ✅ 图标，无法感受愿望与现实物品的连接感。

---

## Actors

- A1. 父母：在主应用查看家庭资产和心愿，审批并实现心愿。
- A2. 孩子：在子端查看自己的心愿状态和已实现心愿。

---

## Requirements

**心愿实现时间戳**

- R1. `wishes` 表新增 `fulfilled_at TIMESTAMP WITH TIME ZONE NULL`，在 `realize_wish()` 原子事务内写入 `datetime.now(timezone.utc)`。
- R2. `WishResponse` schema 新增 `fulfilled_at: datetime | None`，父端心愿详情页展示"实现于 YYYY-MM-DD"；`ChildWishResponse` 及子端服务查询同步更新（OQ-4 决策：纳入同一 PR）。

**资产反向引用**

- R3. `assets` 表新增 `from_wish_id BIGINT NULL`，FK → `wishes.id`，加复合索引 `(family_id, from_wish_id)`。Alembic migration 必须先于服务代码变更部署（防止事务内 `AttributeError` 导致回滚）。
- R4. `realize_wish()` 在同一原子事务内同步写入 `asset.from_wish_id = wish.id`（先写 `fulfilled_at`，再写 `from_wish_id`，最后 commit）。
- R5. `AssetResponse` 新增 `from_wish_id: str | None`（SnowflakeBase 序列化，符合 bigint → string 规则）。
- R6. 资产详情页展示"来自心愿：{name}"入口，点击跳转到对应心愿详情。

**父端心愿详情跳转**

- R7. `WishDetailPage.vue:53` 的静态 `<div v-if="wish.realized_asset_id">` 改为 `<router-link>`，导航至 `/assets/${wish.realized_asset_id}`。

**子端心愿详情跳转**

- R8. 子端新增 `/assets/:id` 详情页路由，展示资产名称、金额等基本信息。
- R9. 子端心愿详情页（`ChildWishDetailPage.vue`）在 `realized_asset_id` 存在时展示"愿望实现了！点击查看"跳转入口，导航至子端 `/assets/${realized_asset_id}`。

**心愿生命周期事件记录**（条件项，依赖 OQ-2）

- R9. 在 `wish_service.create_wish()`、`realize_wish()`、取消流程末尾向 `activities` 表写入事件（`entity_type='wish'`，`type='wish_created'`/`'wish_realized'`/`'wish_cancelled'`）。
- R10. 时间线页面和 AI 顾问的 Activity 查询支持处理 `entity_type='wish'` 类型事件。

---

## Acceptance Examples

- AE1. **Covers R1, R2.** Given 父母点击"实现心愿"并提交，when `realize_wish()` 事务成功，then `Wish.fulfilled_at` 非 NULL，心愿详情页显示"实现于 2026-05-27"。
- AE2. **Covers R3, R4, R5.** Given `realize_wish()` 成功，when 父母查看对应资产详情，then 资产页显示"来自心愿：{name}"，`AssetResponse.from_wish_id` 为字符串形式的 ID。
- AE3. **Covers R7.** Given 心愿已实现（`realized_asset_id` 非 NULL），when 父母在心愿详情页点击"已转为资产"，then 导航至对应资产详情页。
- AE4. **Covers R3, R4.** Given `assets.from_wish_id` migration 尚未运行，when 尝试调用 `realize_wish()`，then 整个事务回滚（资产和心愿均未变更）而非部分写入。
- AE5. **Covers R9, R10.** Given R9 条件项已实施，when `realize_wish()` 成功，then `activities` 表存在一条 `entity_type='wish'`、`type='wish_realized'` 的记录，时间线页面可渲染该事件。

---

## Success Criteria

- 父母在心愿详情页看到"实现于 YYYY-MM-DD"且可一键跳转到对应资产。
- 资产详情页展示来源心愿，家庭账本形成完整的心愿 → 资产故事线。
- 孩子端在心愿实现后能看到并点击跳转入口（路由方案确认后）。
- `realize_wish()` 事务原子性不变：`fulfilled_at`、`from_wish_id` 要么全写入要么全回滚。
- 所有新增 ID 字段在 API 响应中序列化为字符串（无 JS 精度丢失）。

---

## Scope Boundaries

- #4 承诺负债（将未实现心愿建模为仪表盘负债）— 需先验证父母是否接受财务会计语义，延后。
- #6 周年纪念推送 — 依赖不存在的推送通知基础设施，作为独立项目规划。
- `fulfillment_note` 字段（#6 数据层）— 工作量极低，可在 v1.1 低成本补入，本次暂不纳入。
- `Wish.status` 枚举扩展（新增 `approved`）— 超出本次范围，如需添加单独规划。
- Activity 表 CHECK 约束 / enum 类型迁移 — 取决于 OQ-2 决策，可能成为 R9/R10 的前置条件。

---

## Key Decisions

- `fulfilled_at` 使用 `datetime.now(timezone.utc)` 而非 `datetime.utcnow()`：Python 3.12 已弃用后者，统一使用 aware datetime 避免时区比较错误。
- `from_wish_id` 在 `AssetResponse` 中类型为 `str | None`（而非 `int | None`）：遵循项目 SnowflakeBase bigint → string 序列化规则，防止 JS 精度丢失。
- `from_wish_id` migration 部署顺序：必须先于服务代码，否则事务内 `AttributeError` 导致 `realize_wish()` 整体回滚。
- R9/R10（Activity 记录）设为条件项：实施前需先解决 OQ-2（entity_type 扩展策略），否则新事件会被现有查询静默过滤。

---

## Dependencies / Assumptions

- `realize_wish()` 已是原子事务，R1/R4 的新增写入在现有事务边界内安全追加。
- `SnowflakeBase` 对所有 `_id` 后缀字段自动序列化为字符串，R5 无需手动 `str()`。
- 父端主应用已有 `/assets/:id` 路由，R7 的 `router-link` 目标有效。
- 子端 `/assets/:id` 为新建页面（OQ-1 已决策：方案 a），R8 包含路由定义和基本页面实现。
- `ChildWishResponse` 和子端服务查询同步更新以暴露 `fulfilled_at`（OQ-4 已决策：纳入同一 PR）。

---

## Outstanding Questions

### Deferred to Planning

- [Affects R9, R10][Technical] **OQ-2：Activity entity_type 扩展策略。** 现有 `entity_type` 注释为 `asset/liability`。需确认：(a) 正式扩展值域（更新注释 + 如有 CHECK 约束则加 migration + 修改读取 Activity 的查询）；或 (b) 单独建 `wish_events` 表。
- [Affects R9][Technical] **OQ-2b：Activity.type 列长度。** `type` 为 `String(30)`，`wish_realized`（13 字符）在限制内，但实施前确认无 CHECK 约束。
