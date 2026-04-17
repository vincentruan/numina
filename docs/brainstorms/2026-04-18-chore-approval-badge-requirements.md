---
date: 2026-04-18
topic: chore-approval-dashboard
revision: 2
---

# 家务审批入口 + Dashboard 待审批区块

## Problem Frame

父母无法感知孩子已提交家务等待审批。`ChoreApprovalsPage` 是孤立页面，没有任何导航入口，父母必须知道路由地址才能访问。孩子提交家务后进入 `pending_approval` 状态，父母不知道，审批延迟，孩子的即时反馈循环断裂，激励衰减。

核心问题是**可发现性**，不只是通知：审批功能根本不在父母的视野里。

## User Flow

```
孩子提交家务
      │
      ▼
ChoreInstance.status = pending_approval
      │
      ▼
父母打开 app（落地 Dashboard）
      │
      ├─ 有待审批 ──► Dashboard 顶部显示「待审批家务」可展开区块
      │                    │
      │              点击展开 → 显示卡片列表
      │                    │
      │              批准 / 退回 / 拒绝
      │                    │
      │              即时更新列表（移除已处理卡片）
      │
      └─ 无待审批 ──► 区块完全隐藏
```

## Requirements

**Dashboard 待审批区块**
- R1. DashboardPage 顶部（NetWorthCard 之后、StatusSummaryGrid 之前）新增「待审批家务」可展开区块，仅当有待审批项时显示；无待审批时区块完全隐藏。
- R2. 区块默认折叠状态，显示「待审批家务 (N)」标题 + 展开/收起图标。点击标题切换展开/收起。
- R3. 展开后显示卡片列表，每张卡片展示：孩子姓名 + 头像色、家务名称 + emoji、星星币奖励、提交时间（相对时间，如「2小时前」）。
- R4. 每张卡片提供三个操作按钮：批准（`approve`）、退回重做（`reject` with `return_to_redo=true`）、拒绝（`reject` with `return_to_redo=false`），与现有 `ChoreApprovalsPage` 行为一致。
- R5. 操作后对应卡片立即从列表移除（乐观更新），无需整页刷新；若请求失败则回滚卡片并显示错误提示。
- R6. DashboardPage 进入时自动拉取待审批列表；下拉刷新时同步刷新。
- R7. 区块仅对 `owner` 角色显示；`member` 和 `child` 角色不显示。

**SettingsPage 家庭管理入口**
- R8. SettingsPage 在「账户信息」section 之前新增「家庭管理」section，包含一个 cell：「家庭成员管理」，icon: `friends-o`，点击跳转到 `/family` 路由（FamilyPage）。
- R9. 该 cell 仅对 `owner` 和 `member` 角色显示；`child` 角色不显示。

**数据获取**
- R10. 待审批列表通过现有 `GET /family/chore-approvals` 端点获取（返回列表）。
- R11. 待审批列表存入新建 `choreStore`（Pinia），供 DashboardPage 使用。Store 包含：`pendingApprovals` 列表、`pendingCount` computed、`fetchPendingApprovals` action、`approvePendingChore`/`rejectPendingChore` actions（乐观更新）。
- R12. DashboardPage 进入时拉取 + 下拉刷新时同步刷新，不持续轮询。跨设备同步不在范围内——列表仅反映当前设备的本地状态。

## Success Criteria

- 父母打开 app 后，在 Dashboard 能直接看到并处理所有待审批家务，无需知道任何隐藏路由。
- 有待审批时，Dashboard 顶部区块可见；处理完毕后区块消失。
- 孩子提交家务到父母完成审批的操作路径缩短至：打开 app（Dashboard）→ 看到待审批区块 → 展开 → 处理卡片。
- 父母可通过 SettingsPage → 家庭成员管理 进入 FamilyPage 查看完整家庭信息。

## Scope Boundaries

- 不新增推送通知（WebSocket、FCM、微信通知）——区块是 app 内被动提示，不是主动推送。
- 不删除现有 `ChoreApprovalsPage` 路由——保留作为兼容路径，但不再是主要入口。
- 不处理多父母同时审批同一家务的并发冲突——后端以先到请求为准，后到请求返回错误，前端显示「该家务已被处理」并刷新列表。
- 不改变审批的业务逻辑（批准/退回/拒绝的后端行为不变）。
- 不在 child 视角显示任何审批相关 UI。
- 不改变 AppTabBar 结构——6个 tab 保持不变。

## Key Decisions

- **位置选择**：审批区块放在 Dashboard 顶部（NetWorthCard 之后），而非 FamilyPage，因为 Dashboard 是父母打开 app 的默认落地页，可发现性最高。
- **交互方式**：可展开/收起区块，默认折叠，避免占用过多首屏空间。
- **Store 归属**：新建 `choreStore` 管理待审批列表状态，避免 `dashboardStore` 职责膨胀。
- **乐观更新**：操作后立即从本地列表移除卡片，不等待服务端响应；若请求失败则回滚并提示错误。
- **家庭管理入口**：放在 SettingsPage 而非新增 tab，保持 tab bar 简洁。

## Dependencies / Assumptions

- 后端 `GET /family/chore-approvals` 端点已存在且稳定，返回 `ChoreInstanceResponse[]`。
- 审批操作端点（`POST /family/chore-approvals/{id}/approve`、`POST /family/chore-approvals/{id}/reject`）已存在。
- `ChoreInstanceResponse` 需扩展以包含 child 身份字段（`child_user_id`、`child_display_name`、`child_avatar_color`）——后端 service 层需 JOIN User 表。

## Outstanding Questions

### Resolve Before Planning

- [Affects R3][Backend schema] `ChoreInstanceResponse` 需扩展以包含 child 身份字段（`child_user_id`、`child_display_name`、`child_avatar_color`）。后端 service 层需 JOIN User 表以填充这些字段。

### Deferred to Planning

- [Affects R6][Technical] DashboardPage 的 `onRefresh` 已存在，需补充调用 `choreStore.fetchPendingApprovals()`。
- [Affects R2][UX] 区块展开/收起状态是否需要持久化到 localStorage？还是每次进入 Dashboard 都默认折叠？
- [Affects R3][Technical] 相对时间格式化：使用 dayjs 还是 Intl.RelativeTimeFormat？需要添加 dayjs 依赖吗？

## Next Steps

→ 运行 `/ce:plan`
