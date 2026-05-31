# 家庭成员管理优化设计

## 概述

将家庭成员管理从列表式（van-swipe-cell）改为卡片式展示，引入 root/admin/member 三级权限模型，并移除孩子管理中已冗余的审批入口。

## 需求

### R1: 成员卡片化展示

将 `FamilyPage.vue` 中成人成员的 `van-swipe-cell` 列表改为卡片布局，复用儿童卡片的 `.child-mgmt-card` 样式模式。

**卡片结构：**
- 头部行：圆形彩色字母头像 + 显示名称 + `@username` + 角色标签
- 底部操作栏（piano-key 风格按钮，与儿童卡片一致）：
  - 设为管理员 / 设为普通成员
  - 禁用账户 / 启用账户
  - 移除成员
  - 重置密码

**角色标签显示：**
- root 创建者：`创建者` (primary tag)
- 管理员（owner 但非 created_by）：`管理员` (success tag)
- 普通成员：`成员` (default tag)

### R2: 三级权限模型（root / admin / member）

**角色定义：**
- **root**（家庭创建者，唯一）：`User.role == 'owner'` 且 `User.id == Family.created_by`
- **admin**（管理员，可多个）：`User.role == 'owner'` 且 `User.id != Family.created_by`
- **member**（普通成员）：`User.role == 'member'`
- **child**（不变）：`User.role == 'child'`

**设计决策：** 复用现有 `owner` 角色值表示管理员，通过 `Family.created_by` 区分 root 和普通 admin。这样避免数据库迁移、避免改动所有现有的 `role == 'owner'` 权限检查。

**权限矩阵：**

| 操作 | root 可操作对象 | admin 可操作对象 | member |
|------|----------------|-----------------|--------|
| 设为管理员 | member | ❌ | ❌ |
| 设为普通成员 | admin | ❌ | ❌ |
| 禁用/启用账户 | admin, member | member | ❌ |
| 移除成员 | admin, member | member | ❌ |
| 重置密码 | admin, member | member | ❌ |

**核心规则：**
1. root 只有一个（家庭创建者），不可被降级、禁用或移除
2. admin 不能操作其他 admin 或 root
3. admin 只能操作 member
4. root 可以操作所有非 root 成员

### R3: 移除孩子管理中的审批入口

从 `FamilyPage.vue` 儿童卡片的操作栏中移除：
- "审批任务" 按钮（`/family/chore-approvals`）
- "审批心愿" 按钮（`/family/wish-review`）

原因：`BabyPage.vue` 已有 `PendingApprovalsSection` 提供相同功能。

## 技术方案

### 后端改动

#### 1. 新增 API 端点

**POST `/api/v1/family/members/{member_id}/reset-password`**
- 权限：owner（root 可操作所有非 root；admin 仅操作 member）
- 请求体：`{ "new_password": "string" }`
- 响应：`{ "detail": "✅ 密码已重置" }`
- 逻辑：hash 新密码并更新 `User.password_hash`

**PATCH `/api/v1/family/members/{member_id}/status`**
- 权限：owner（root 可操作所有非 root；admin 仅操作 member）
- 请求体：`{ "is_active": bool }`
- 响应：`UserResponse`
- 逻辑：设置 `User.is_active`，禁用时同时 bump `token_version` 使现有 token 失效

#### 2. 修改现有端点

**PATCH `/api/v1/family/members/{member_id}/role`**
- 当前：仅 owner 可操作，允许设为 `owner` 或 `member`
- 改为：仅 root（`user.id == family.created_by`）可操作
- 新增校验：不允许修改 root 自己的角色
- 允许值不变：`owner`（提升为管理员）、`member`（降级为普通成员）

**DELETE `/api/v1/family/members/{member_id}`**
- 当前：仅 owner 可操作
- 改为：owner 可操作，但 admin 不能删除其他 admin 或 root
- 新增校验：`is_root(target)` 时拒绝

#### 3. 权限判断辅助函数

在 `family_service.py` 中新增：

```python
def is_root(db: Session, user: User) -> bool:
    """判断用户是否为家庭创建者（root）"""
    family = db.query(Family).filter(Family.id == user.family_id).first()
    return family and family.created_by == user.id

def can_manage(db: Session, operator: User, target: User) -> bool:
    """判断 operator 是否有权管理 target"""
    if operator.role != 'owner':
        return False
    family = db.query(Family).filter(Family.id == operator.family_id).first()
    # root 不可被任何人管理
    if target.id == family.created_by:
        return False
    # admin 只能管理 member
    if operator.id != family.created_by and target.role == 'owner':
        return False
    return True
```

### 前端改动

#### 1. FamilyPage.vue — 成员卡片化

替换 `van-swipe-cell` 列表为卡片布局：

```html
<div class="member-cards">
  <div v-for="member in adultMembers" :key="member.id" class="member-card">
    <div class="member-card-header">
      <span class="member-avatar" :style="{ background: member.avatar_color }">
        {{ member.display_name[0] }}
      </span>
      <span class="member-name">{{ member.display_name }}</span>
      <span class="member-username">@{{ member.username }}</span>
      <van-tag :type="getRoleTagType(member)" size="medium">
        {{ getRoleLabel(member) }}
      </van-tag>
    </div>
    <div v-if="canShowActions(member)" class="member-card-actions">
      <!-- 按钮根据权限动态显示 -->
    </div>
  </div>
</div>
```

#### 2. 权限判断逻辑

前端需要知道：
- 当前用户是否为 root：`authStore.user.id === familyStore.family.created_by`
- 当前用户是否为 admin：`authStore.user.role === 'owner' && !isRoot`
- 目标成员的角色级别

```typescript
const isCurrentUserRoot = computed(() =>
  authStore.user?.id === familyStore.family?.created_by
)
const isCurrentUserAdmin = computed(() =>
  authStore.user?.role === 'owner' && !isCurrentUserRoot.value
)

function canManage(member: Member): boolean {
  if (member.id === familyStore.family?.created_by) return false // root 不可被管理
  if (isCurrentUserRoot.value) return true // root 可管理所有非 root
  if (isCurrentUserAdmin.value && member.role === 'member') return true
  return false
}

function canChangeRole(member: Member): boolean {
  return isCurrentUserRoot.value && member.id !== familyStore.family?.created_by
}
```

#### 3. 新增 API 调用

```typescript
// api/family.ts
export function resetMemberPassword(memberId: string, newPassword: string) {
  return http.post(`/family/members/${memberId}/reset-password`, { new_password: newPassword })
}

export function updateMemberStatus(memberId: string, isActive: boolean) {
  return http.patch(`/family/members/${memberId}/status`, { is_active: isActive })
}
```

#### 4. 移除审批按钮

从儿童卡片的 `.child-mgmt-actions` 中删除前两个按钮（审批任务、审批心愿）。

### 样式

成员卡片复用 `.child-mgmt-card` 的样式基础（圆角、阴影、padding），操作栏复用 `.child-mgmt-actions` 的 piano-key 布局。新增 `.member-card` 类名以区分，但视觉风格一致。

## 不做的事

- 不新增数据库角色值（复用 `owner` + `created_by` 判断）
- 不做数据库迁移（`created_by` 字段已存在）
- 不改动 `child` 角色的任何逻辑
- 不改动 `BabyPage.vue` 的审批功能
- 不新增成员编辑功能（仅管理操作：角色、禁用、移除、密码）

## 验收标准

1. 成人成员以卡片形式展示，包含头像、名称、账户、角色标签
2. root 用户看到所有非 root 成员的操作按钮
3. admin 用户仅看到 member 的操作按钮
4. member 用户不看到任何操作按钮
5. 角色切换仅 root 可操作
6. 禁用账户后该成员无法登录，启用后恢复
7. 移除成员后该成员从列表消失
8. 重置密码后成员可用新密码登录
9. 儿童卡片不再显示"审批任务"和"审批心愿"按钮
10. `pnpm typecheck` 通过
11. 后端 `ruff check` + `mypy` 通过
