---
name: Admin Child View Switch
description: Move child view switching to FamilyPage, restrict to owner only
type: feature
module: frontend/auth
tags: [child-view, admin, permission]
---

# Admin Child View Switch Design

## Summary

将"切换到孩子视角"功能从顶部导航栏移至家庭管理页面的孩子管理区域，并限制只有家庭管理员（owner）才能使用。管理员切换时无需PIN验证，退出时无需密码验证。

## Requirements

1. 只有家庭管理员（role='owner'）可以切换到孩子视角
2. 切换时需要指定具体的孩子
3. 管理员切换后看到的内容与真实孩子看到的内容完全一致
4. 管理员退出孩子视角时无需密码验证

## UI Changes

### FamilyPage.vue

在孩子管理卡片的 `child-mgmt-actions` 区域添加新按钮：

**位置**: 第101-105行的 `child-mgmt-actions` div内

**现有按钮布局**:
```
审批家务 | 审批心愿 | 赠送星星
```

**添加后**:
```
审批家务 | 审批心愿 | 赠送星星 | 切换视角
```

**按钮属性**:
- 文字: "切换视角"
- 类型: `van-button size="mini" plain type="default"`
- 点击: 调用 `switchToChildView(child)`

### MainLayout.vue

移除顶部右侧的"切换到孩子视角"按钮：

**删除内容**:
```vue
<div class="switch-child-btn" @click="router.push('/child/select')">
  <van-icon name="friends-o" /> 切换到孩子视角
</div>
```

同时删除相关的CSS样式 `.switch-child-btn`。

## Frontend Logic

### FamilyPage.vue - switchToChildView

```typescript
async function switchToChildView(child: ChildUser) {
  try {
    // 调用管理员专用API获取孩子JWT
    const response = await adminSwitchToChild(child.id)
    
    // 存储孩子JWT（替换当前管理员JWT）
    setTokens(response.access_token, response.refresh_token)
    
    // 标识这是管理员视角切换（用于退出逻辑）
    localStorage.setItem('admin_child_view', child.id)
    
    // 更新用户状态为孩子
    setUser({
      id: child.id,
      display_name: child.display_name,
      avatar_color: child.avatar_color,
      role: 'child',
    })
    
    // 导航到孩子首页
    router.push('/child/home')
  } catch (err) {
    showToast('切换失败，请重试')
  }
}
```

### ChildLayout.vue - handleReturnToAdult 修改

```typescript
async function handleReturnToAdult() {
  const adminChildView = localStorage.getItem('admin_child_view')
  
  if (adminChildView) {
    // 管理员视角切换 - 直接返回，无需密码验证
    showReturnModal.value = false
    localStorage.removeItem('admin_child_view')
    clearAuth()
    window.location.href = '/'
    return
  }
  
  // 真实孩子登录 - 需要密码验证（现有流程保持不变）
  returnError.value = ''
  try {
    await childAuthStore.returnToAdult(parentPassword.value)
    clearAuth()
    window.location.href = '/'
  } catch {
    returnError.value = '密码错误，请重试'
  }
}
```

同时修改UI：当检测到 `admin_child_view` 时，不显示密码输入对话框，直接返回。

```vue
<van-dialog
  v-model:show="showReturnModal"
  title="返回大人模式"
  :show-cancel-button="!hasAdminChildView"
  @confirm="handleReturnToAdult"
>
  <div v-if="!hasAdminChildView" style="padding: 16px">
    <van-field
      v-model="parentPassword"
      type="password"
      placeholder="请输入大人的密码"
      :error-message="returnError"
    />
  </div>
  <div v-else style="padding: 16px; text-align: center">
    确定返回大人模式？
  </div>
</van-dialog>
```

新增 computed:
```typescript
const hasAdminChildView = computed(() => localStorage.getItem('admin_child_view') !== null)
```

## Backend API

### 新增路由: POST /auth/admin/switch-child/{child_id}

**文件**: `backend/app/routers/auth.py`

**路由定义**:
```python
@router.post("/admin/switch-child/{child_id}", response_model=TokenResponse)
def admin_switch_child(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),  # 只有owner可以调用
):
    """管理员切换到孩子视角（无需PIN验证）
    
    返回孩子JWT，管理员可以查看孩子看到的内容。
    """
```

**逻辑流程**:
1. 验证当前用户 `role='owner'`（通过 `require_owner` dependency）
2. 查询目标孩子：`db.query(User).filter(User.id == child_id, User.family_id == user.family_id, User.role == 'child').first()`
3. 如果孩子不存在或不属于同一家庭，返回 404
4. 生成孩子JWT：
   - payload 包含 `sub: child.id`, `family_id: child.family_id`, `role: 'child'`
   - 设置 child token version（如果有token_version字段）
5. 返回 `TokenResponse(access_token=..., refresh_token=...)`

**依赖**: 使用现有的 `require_owner` dependency（已定义在 `backend/app/auth/deps.py`）

## Error Handling

| Error | HTTP Status | Message |
|-------|-------------|---------|
| 非管理员调用 | 403 | "只有家庭管理员可以切换视角" |
| 孩子不存在 | 404 | "孩子不存在" |
| 孩子不属于同一家庭 | 404 | "孩子不存在" |

## Testing Considerations

1. **权限测试**: member角色用户尝试切换，应返回403
2. **跨家庭测试**: 管理员尝试切换到其他家庭的孩子，应返回404
3. **JWT验证测试**: 切换后的孩子JWT应能正常访问孩子API
4. **退出测试**: 管理员切换后退出，应直接返回大人模式，无需密码
5. **并发测试**: 管理员JWT和孩子JWT的存储切换逻辑

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/pages/FamilyPage.vue` | 添加"切换视角"按钮和switchToChildView函数 |
| `frontend/src/layouts/MainLayout.vue` | 移除顶部切换按钮和相关样式 |
| `frontend/src/layouts/ChildLayout.vue` | 修改handleReturnToAdult，支持管理员直接返回 |
| `frontend/src/api/auth.ts` | 添加adminSwitchToChild API调用 |
| `backend/app/routers/auth.py` | 添加/admin/switch-child/{child_id}路由 |
| `backend/app/schemas/auth.py` | 无需修改，使用现有TokenResponse |

## Implementation Order

1. 后端API：添加 `/admin/switch-child/{child_id}` 路由
2. 前端API：添加 `adminSwitchToChild` 函数
3. FamilyPage.vue：添加按钮和切换逻辑
4. ChildLayout.vue：修改退出逻辑
5. MainLayout.vue：移除顶部按钮
6. 测试验证