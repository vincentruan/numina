---
date: 2026-04-18
topic: chore-approval-dashboard
status: active
origin: docs/brainstorms/2026-04-18-chore-approval-badge-requirements.md
---

# Plan: 家务审批入口 + Dashboard 待审批区块

## Problem Frame

`ChoreApprovalsPage` 是孤立页面，无任何导航入口。孩子提交家务后进入 `pending_approval` 状态，父母不知道，审批延迟，激励循环断裂。

解决方案：在 Dashboard 顶部嵌入可展开的待审批区块（父母落地页），在 SettingsPage 添加家庭管理入口。

## Scope

**In scope:**
- 后端：扩展 `ChoreInstanceResponse` 加入 child 身份字段
- 前端：新建 `choreStore`，Dashboard 待审批区块，SettingsPage 家庭管理入口

**Out of scope:**
- 推送通知（WebSocket/FCM）
- 修改 AppTabBar 结构
- 修改审批业务逻辑

## Architecture Decisions

**choreStore（新建）**
新建 `frontend/src/stores/chore.ts`，不扩展 `dashboardStore`（职责分离）。Store 拥有：
- `pendingApprovals: ref<ChoreInstanceWithChild[]>` — 完整列表
- `pendingCount: computed` — 派生自列表长度
- `fetchPendingApprovals()` — 调用 `GET /family/chore-approvals`
- `approvePendingChore(id)` / `rejectPendingChore(id, returnToRedo)` — 乐观更新 + 失败回滚

**ChoreInstanceWithChild（新增前端类型）**
扩展现有 `ChoreInstance` 接口，加入 `child_user_id`, `child_display_name`, `child_avatar_color`。

**后端 ChoreInstanceResponse 扩展**
`list_pending_approvals` 服务函数需 JOIN User 表获取 child 身份字段，并在 `ChoreInstanceResponse` schema 中暴露。需要 Alembic migration（无新表，仅 schema 字段变更）。

**展开/收起状态**
不持久化到 localStorage，每次进入 Dashboard 默认折叠。理由：待审批是时效性数据，每次都应主动展开查看。

**相对时间格式化**
使用 `dayjs`（项目已有依赖，无需新增）。格式规则：`<1min=刚刚`，`<1hr=X分钟前`，`<24hr=X小时前`，`<7days=X天前`，`>=7days=MM-DD HH:mm`。

## Implementation Units

### Unit 1: 后端 — 扩展 ChoreInstanceResponse

**文件：**
- `backend/app/schemas/chore.py` — 在 `ChoreInstanceResponse` 加入 3 个 child 字段
- `backend/app/services/chores.py` — `list_pending_approvals()` JOIN User 表填充字段
- `backend/tests/test_chores.py`（或新建）— 验证响应包含 child 字段

**变更：**

`ChoreInstanceResponse`（`backend/app/schemas/chore.py:99`）新增：
```python
child_user_id: str | None = None
child_display_name: str | None = None
child_avatar_color: str | None = None
```

`list_pending_approvals`（`backend/app/services/chores.py:299`）改为 JOIN User：
```python
# 伪代码方向（不是实现代码）
pending = (
    db.query(ChoreInstance, User)
    .join(User, User.id == ChoreInstance.child_user_id, isouter=True)
    .filter(...)
    .all()
)
# 构建带 child 字段的 ChoreInstanceResponse
```

注意：`ChoreInstance.child_user_id` 字段已存在于模型（`backend/app/models/chore.py:45`），无需 Alembic migration，仅 schema 层变更。

**测试场景：**
- `GET /family/chore-approvals` 返回的每条记录包含 `child_user_id`、`child_display_name`、`child_avatar_color`
- 当 `child_user_id` 为 null（pool chore 无指定孩子）时，三个字段均为 `null`，不报错
- 非 adult 角色调用返回 403

---

### Unit 2: 前端 — choreStore

**文件：**
- `frontend/src/stores/chore.ts`（新建）

**Store 结构（方向性，非实现代码）：**
```typescript
// state
pendingApprovals: ChoreInstanceWithChild[]

// computed
pendingCount: number  // pendingApprovals.length

// actions
fetchPendingApprovals()   // GET /family/chore-approvals
approvePendingChore(id)   // POST .../approve，乐观移除，失败回滚
rejectPendingChore(id, returnToRedo)  // POST .../reject，乐观移除，失败回滚
```

**乐观更新模式（参考 `frontend/src/stores/liability.ts` 的 delete 模式）：**
1. 保存被移除项的引用和原始索引
2. 立即从 `pendingApprovals` 中 splice 移除
3. 调用 API
4. 失败时：在原始索引处 splice 回插，`showFailToast` 提示错误

**类型扩展（`frontend/src/types/chore.ts` 或 inline）：**
```typescript
interface ChoreInstanceWithChild extends ChoreInstance {
  child_user_id: string | null
  child_display_name: string | null
  child_avatar_color: string | null
}
```

**测试场景：**
- `fetchPendingApprovals` 成功时 `pendingApprovals` 被填充，`pendingCount` 正确
- `approvePendingChore` 乐观移除后 API 失败时，卡片回滚到原位置
- `rejectPendingChore(id, true)` 发送 `return_to_redo: true`，`rejectPendingChore(id, false)` 发送 `return_to_redo: false`
- `pendingCount` 是 computed，随 `pendingApprovals` 变化自动更新

---

### Unit 3: 前端 — PendingApprovalsSection 组件

**文件：**
- `frontend/src/components/dashboard/PendingApprovalsSection.vue`（新建）

**组件职责：**
- 接收 `choreStore.pendingApprovals` 和 `choreStore.pendingCount` 作为 props（或直接使用 store）
- 管理展开/收起本地状态（`isExpanded: ref<boolean>(false)`）
- 渲染折叠标题：`待审批家务 (N)` + chevron 图标
- 展开后渲染卡片列表
- 每张卡片：头像色圆圈 + 孩子姓名、家务 emoji + 名称、星星币奖励、相对时间
- 三个操作按钮：批准（绿）、退回（橙）、拒绝（红）
- 操作时调用 `choreStore.approvePendingChore` / `choreStore.rejectPendingChore`
- 操作中禁用按钮（`actioningId` ref 追踪当前操作中的卡片 id）

**卡片布局方向：**
```
┌─────────────────────────────────────────┐
│ 🟡  小明          扫地 🧹    +15⭐      │
│     2小时前                             │
│                    [✓批准][↩退回][✗拒绝]│
└─────────────────────────────────────────┘
```
头像色圆圈（左，40px，`background: child_avatar_color`）+ 内容区（flex-grow）+ 操作按钮（右，竖排）

**测试场景：**
- 无待审批时组件不渲染（`v-if="pendingCount > 0"`）
- 默认折叠，点击标题展开，再次点击收起
- 操作中按钮禁用，操作完成后卡片消失
- 最后一张卡片处理后整个区块消失

---

### Unit 4: 前端 — DashboardPage 集成

**文件：**
- `frontend/src/pages/DashboardPage.vue`

**变更：**
1. 导入 `useDashboardStore` 旁边加入 `useChoreStore`，导入 `PendingApprovalsSection`
2. `onMounted` 中（`DashboardPage.vue:685`）：若 `authStore.user?.role === 'owner'`，调用 `choreStore.fetchPendingApprovals()`
3. `onRefresh`（`DashboardPage.vue:680`）：在 `dashboardStore.fetchAll()` 之后，若 owner，调用 `choreStore.fetchPendingApprovals()`
4. 模板中在 `<NetWorthCard>` 之后、`<StatusSummaryGrid>` 之前插入：
   ```html
   <PendingApprovalsSection v-if="authStore.user?.role === 'owner'" />
   ```

**测试场景：**
- owner 角色进入 Dashboard，`fetchPendingApprovals` 被调用
- member/child 角色进入 Dashboard，`fetchPendingApprovals` 不被调用，区块不渲染
- 下拉刷新后待审批列表同步更新

---

### Unit 5: 前端 — SettingsPage 家庭管理入口

**文件：**
- `frontend/src/pages/SettingsPage.vue`

**变更：**
在「账户信息」`van-cell-group`（`SettingsPage.vue:26`）之前插入新 section：
```html
<van-cell-group
  v-if="authStore.user?.role === 'owner' || authStore.user?.role === 'member'"
  inset
  title="家庭管理"
  class="section"
>
  <van-cell title="家庭成员管理" icon="friends-o" is-link to="/family" />
</van-cell-group>
```

**测试场景：**
- owner 和 member 角色在 SettingsPage 看到「家庭成员管理」入口
- child 角色不显示该 section
- 点击跳转到 `/family` 路由

---

## Sequencing

```
Unit 1 (后端 schema 扩展)
    │
    ▼
Unit 2 (choreStore) ──► Unit 3 (PendingApprovalsSection)
                                │
                                ▼
                         Unit 4 (Dashboard 集成)

Unit 5 (SettingsPage 入口) — 独立，可并行
```

Unit 1 必须先完成，因为 Unit 2/3 依赖 `child_display_name` 等字段。Unit 5 完全独立。

## Key Risks

| 风险 | 缓解 |
|------|------|
| `ChoreInstance.child_user_id` 对 pool chore 可能为 null | Unit 1 中 JOIN 用 `isouter=True`，schema 字段设为 `Optional` |
| 乐观更新回滚时原始索引已变（并发操作） | 用 item id 查找而非保存索引，找不到则不回滚（已被其他操作处理） |
| DashboardPage 已有 `onMounted` 逻辑，新增 fetch 可能影响首屏性能 | `fetchPendingApprovals` 独立调用，不阻塞 `dashboardStore.fetchAll()` |
| `ChoreApprovalsPage` 现有「审批家务」按钮在 FamilyPage（line 102）造成重复入口 | 本次不处理，FamilyPage 的按钮保留；后续可单独清理 |

## Test File Paths

- `backend/tests/test_chores.py` — Unit 1 后端测试
- `frontend/src/stores/chore.test.ts` — Unit 2 store 测试
- `frontend/src/components/dashboard/PendingApprovalsSection.test.ts` — Unit 3 组件测试（可选，优先手动验证）

## References

- `backend/app/schemas/chore.py:99` — ChoreInstanceResponse 当前定义
- `backend/app/services/chores.py:299` — list_pending_approvals 当前实现
- `frontend/src/api/chores.ts:80` — getPendingApprovals / approveChore / rejectChore
- `frontend/src/pages/DashboardPage.vue:680` — onRefresh
- `frontend/src/pages/DashboardPage.vue:685` — onMounted
- `frontend/src/pages/SettingsPage.vue:26` — 账户信息 section 位置
- `frontend/src/stores/family.ts` — 71 行，参考 store 结构
- `frontend/src/components/common/AlertCards.vue` — Dashboard 现有卡片组件，参考样式模式
