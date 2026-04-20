# Admin Child View Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将"切换到孩子视角"功能从顶部导航栏移至家庭管理页面的孩子管理区域，并限制只有家庭管理员才能使用。

**Architecture:** 后端新增管理员专用切换API（无需PIN验证），前端在孩子管理卡片添加切换按钮，通过localStorage标识管理员视角切换模式以便退出时跳过密码验证。

**Tech Stack:** FastAPI + SQLAlchemy (后端), Vue 3 + TypeScript + Vant (前端)

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/routers/auth.py` | 新增 `/admin/switch-child/{child_id}` 路由 |
| `backend/app/services/auth.py` | 新增 `admin_switch_to_child` 服务函数 |
| `frontend/src/api/auth.ts` | 新增 `adminSwitchToChild` API调用 |
| `frontend/src/pages/FamilyPage.vue` | 添加"切换视角"按钮和切换逻辑 |
| `frontend/src/layouts/ChildLayout.vue` | 修改退出逻辑支持管理员直接返回 |
| `frontend/src/layouts/MainLayout.vue` | 移除顶部切换按钮 |

---

### Task 1: 后端测试 - 权限验证

**Files:**
- Create: `backend/tests/test_admin_child_switch.py`

- [ ] **Step 1: Write the failing test for owner permission**

```python
"""Tests for admin child view switching."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from tests.conftest import auth_headers, create_test_family, create_test_child


def test_admin_switch_child_requires_owner(db: Session, client: TestClient):
    """Only owner can switch to child view."""
    # Create family with owner and member
    family, owner, member = create_test_family(db, with_member=True)
    child = create_test_child(db, family.id, "TestChild")
    
    # Member tries to switch - should fail with 403
    member_headers = auth_headers(client, db, member.username, "password")
    response = client.post(
        f"/api/v1/auth/admin/switch-child/{child.id}",
        headers=member_headers,
    )
    assert response.status_code == 403
    assert "仅家庭管理员" in response.json()["detail"] or "Forbidden" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_child_switch.py::test_admin_switch_child_requires_owner -v`
Expected: FAIL with endpoint not found or AttributeError

- [ ] **Step 3: Commit test file**

```bash
git add backend/tests/test_admin_child_switch.py
git commit -m "test: add owner permission test for admin child switch"
```

---

### Task 2: 后端测试 - 成功切换

**Files:**
- Modify: `backend/tests/test_admin_child_switch.py`

- [ ] **Step 1: Write test for successful switch**

```python
def test_admin_switch_child_success(db: Session, client: TestClient):
    """Owner can successfully switch to child view."""
    from app.auth.deps import create_access_token, create_child_refresh_token
    
    family, owner = create_test_family(db)
    child = create_test_child(db, family.id, "TestChild")
    
    # Owner switches to child view
    owner_headers = auth_headers(client, db, owner.username, "password")
    response = client.post(
        f"/api/v1/auth/admin/switch-child/{child.id}",
        headers=owner_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    # Verify child cookies are set
    cookies = response.cookies
    assert "child_access_token" in cookies or len(cookies) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_child_switch.py::test_admin_switch_child_success -v`
Expected: FAIL with endpoint not found

- [ ] **Step 3: Commit test**

```bash
git add backend/tests/test_admin_child_switch.py
git commit -m "test: add success test for admin child switch"
```

---

### Task 3: 后端测试 - 跨家庭隔离

**Files:**
- Modify: `backend/tests/test_admin_child_switch.py`

- [ ] **Step 1: Write test for cross-family isolation**

```python
def test_admin_switch_child_cross_family_isolation(db: Session, client: TestClient):
    """Owner cannot switch to child from another family."""
    # Create two families
    family1, owner1 = create_test_family(db, name_suffix="_1")
    family2, owner2 = create_test_family(db, name_suffix="_2")
    child2 = create_test_child(db, family2.id, "OtherChild")
    
    # Owner1 tries to switch to child2 (from family2) - should fail
    owner1_headers = auth_headers(client, db, owner1.username, "password")
    response = client.post(
        f"/api/v1/auth/admin/switch-child/{child2.id}",
        headers=owner1_headers,
    )
    
    assert response.status_code == 404
    assert "孩子不存在" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_admin_child_switch.py::test_admin_switch_child_cross_family_isolation -v`
Expected: FAIL with endpoint not found

- [ ] **Step 3: Commit test**

```bash
git add backend/tests/test_admin_child_switch.py
git commit -m "test: add cross-family isolation test for admin child switch"
```

---

### Task 4: 后端服务函数实现

**Files:**
- Modify: `backend/app/services/auth.py`

- [ ] **Step 1: Write admin_switch_to_child service function**

在 `child_pin_login` 函数后面添加（约第493行后）:

```python
def admin_switch_to_child(db: Session, owner: User, child_id: str) -> TokenResponse:
    """Admin switches to child view without PIN verification.
    
    Args:
        db: Database session
        owner: Current owner user (must have role='owner')
        child_id: Target child ID to switch to
        
    Returns:
        TokenResponse with child access and refresh tokens
        
    Raises:
        AppError: If child not found or not in same family
    """
    from app.auth.deps import create_access_token, create_child_refresh_token
    
    # Verify child exists and belongs to owner's family
    child = db.query(User).filter(
        User.id == child_id,
        User.family_id == owner.family_id,
        User.role == "child",
        User.is_active == True,
    ).first()
    
    if not child:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, message="孩子不存在")
    
    # Generate child tokens (same as child_pin_login)
    return TokenResponse(
        access_token=create_access_token({"sub": child.id, "fid": child.family_id, "role": "child"}),
        refresh_token=create_child_refresh_token({"sub": child.id, "fid": child.family_id, "role": "child", "token_version": child.token_version}),
    )
```

- [ ] **Step 2: Run tests to verify service function signature is correct**

Run: `cd backend && uv run python -c "from app.services.auth import admin_switch_to_child; print('OK')"`
Expected: OK (imports successfully)

- [ ] **Step 3: Commit service function**

```bash
git add backend/app/services/auth.py
git commit -m "feat(auth): add admin_switch_to_child service function"
```

---

### Task 5: 后端路由实现

**Files:**
- Modify: `backend/app/routers/auth.py`

- [ ] **Step 1: Add import for require_owner**

在文件顶部的imports区域添加（约第27行后）:

```python
from app.auth.deps import (
    get_child_refresh_token_from_cookie,
    get_current_child_user,
    get_current_user,
    get_current_user_from_cookie,
    get_refresh_token_from_cookie,
    require_owner,  # Add this import
)
```

- [ ] **Step 2: Add admin switch-child endpoint**

在 `child_logout` 路由后面添加（约第274行后）:

```python
@router.post("/admin/switch-child/{child_id}", response_model=TokenResponse)
def admin_switch_child(
    response: Response,
    child_id: str,
    db: Session = Depends(get_db),
    owner: User = Depends(require_owner),
):
    """Admin switches to child view without PIN verification.
    
    Only family owner can use this endpoint. Returns child JWT tokens
    and sets child authentication cookies.
    
    Args:
        child_id: Target child ID to switch to
        
    Returns:
        TokenResponse with child access and refresh tokens
    """
    tokens = auth_service.admin_switch_to_child(db, owner, child_id)
    set_child_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return tokens
```

- [ ] **Step 3: Run tests to verify endpoint works**

Run: `cd backend && uv run pytest tests/test_admin_child_switch.py -v`
Expected: All 3 tests PASS

- [ ] **Step 4: Commit router implementation**

```bash
git add backend/app/routers/auth.py
git commit -m "feat(auth): add /admin/switch-child endpoint for owner"
```

---

### Task 6: 前端API函数

**Files:**
- Modify: `frontend/src/api/auth.ts`

- [ ] **Step 1: Add adminSwitchToChild API function**

在文件末尾添加:

```typescript
export function adminSwitchToChild(childId: string) {
  return http.post<AuthResponse>('/auth/admin/switch-child/' + childId)
}
```

- [ ] **Step 2: Run typecheck to verify**

Run: `cd frontend && npm run typecheck`
Expected: PASS (no type errors)

- [ ] **Step 3: Commit API function**

```bash
git add frontend/src/api/auth.ts
git commit -m "feat(api): add adminSwitchToChild function"
```

---

### Task 7: FamilyPage.vue - 添加切换按钮

**Files:**
- Modify: `frontend/src/pages/FamilyPage.vue`

- [ ] **Step 1: Add imports**

在 `<script setup>` 的 imports 区域（约第142-149行）添加:

```typescript
import { useRouter } from 'vue-router'
import { adminSwitchToChild } from '@/api/auth'
import { setUser } from '@/utils/storage'
import type { ChildUser } from '@/types'
```

并添加 router 声明:
```typescript
const router = useRouter()
```

- [ ] **Step 2: Add switchToChildView function**

在 script 区域添加函数（在 `doGrant` 函数后）:

```typescript
async function switchToChildView(child: ChildUser) {
  try {
    // 调用管理员专用API获取孩子JWT
    await adminSwitchToChild(child.id)
    
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

- [ ] **Step 3: Add button in template**

在 `child-mgmt-actions` div内（第101-105行）添加按钮:

```vue
<div class="child-mgmt-actions">
  <van-button size="mini" plain type="primary" to="/family/chore-approvals">审批家务</van-button>
  <van-button size="mini" plain type="primary" to="/family/wish-review">审批心愿</van-button>
  <van-button size="mini" plain type="success" @click="openGrantSheet(child)">赠送星星</van-button>
  <van-button size="mini" plain type="warning" @click="switchToChildView(child)">切换视角</van-button>
</div>
```

- [ ] **Step 4: Run typecheck to verify**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit FamilyPage changes**

```bash
git add frontend/src/pages/FamilyPage.vue
git commit -m "feat(family): add 'switch to child view' button for owner"
```

---

### Task 8: ChildLayout.vue - 修改退出逻辑

**Files:**
- Modify: `frontend/src/layouts/ChildLayout.vue`

- [ ] **Step 1: Add computed for admin child view**

在 `<script setup>` 区域添加 computed:

```typescript
import { computed } from 'vue'

const hasAdminChildView = computed(() => localStorage.getItem('admin_child_view') !== null)
```

- [ ] **Step 2: Modify handleReturnToAdult function**

替换原有的 `handleReturnToAdult` 函数:

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

- [ ] **Step 3: Modify dialog template**

替换现有的 `van-dialog`:

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

- [ ] **Step 4: Run typecheck to verify**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 5: Commit ChildLayout changes**

```bash
git add frontend/src/layouts/ChildLayout.vue
git commit -m "feat(child): support admin direct return without password"
```

---

### Task 9: MainLayout.vue - 移除顶部按钮

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Remove switch-child-btn from template**

删除 template 中的按钮元素（第5-7行）:

```vue
<!-- DELETE this -->
<div class="switch-child-btn" @click="router.push('/child/select')">
  <van-icon name="friends-o" /> 切换到孩子视角
</div>
```

修改后的 template:
```vue
<template>
  <div class="main-layout">
    <div class="top-bar">
      <NotificationBell class="notification-bell-btn" />
    </div>
    <router-view />
    <AppTabBar />
  </div>
</template>
```

- [ ] **Step 2: Remove CSS styles**

删除 `.switch-child-btn` 相关样式（约第48-64行）:

```css
/* DELETE all these */
.switch-child-btn {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.9);
  ...
}
```

- [ ] **Step 3: Run typecheck to verify**

Run: `cd frontend && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit MainLayout changes**

```bash
git add frontend/src/layouts/MainLayout.vue
git commit -m "refactor: remove top-bar child view switch button"
```

---

### Task 10: 构建验证

**Files:**
- None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `cd backend && uv run pytest tests/test_admin_child_switch.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run backend full tests**

Run: `cd backend && uv run pytest tests/ -v`
Expected: All tests PASS (no regressions)

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds without errors

- [ ] **Step 4: Rebuild Docker containers**

Run: `docker-compose up -d --build`
Expected: All containers start successfully

- [ ] **Step 5: Manual smoke test**

1. 登录管理员账号
2. 进入家庭管理页面
3. 在孩子管理卡片中点击"切换视角"
4. 确认进入孩子视角（孩子首页）
5. 点击顶部"大人模式"按钮
6. 确认直接返回（无密码验证）

---

### Task 11: 清理和文档

**Files:**
- None

- [ ] **Step 1: Run lint checks**

Run backend lint:
```bash
cd backend && uv run ruff check . && uv run ruff format .
```

Run frontend lint:
```bash
cd frontend && npm run lint:fix && npm run format
```

Expected: No lint errors

- [ ] **Step 2: Final commit (if any formatting changes)**

```bash
git add -A
git commit -m "style: format code after admin child view switch feature"
```

---

## Summary

- **Backend**: 新增 `/auth/admin/switch-child/{child_id}` 路由，只有owner可调用，返回孩子JWT
- **Frontend**: FamilyPage添加切换按钮，ChildLayout支持管理员直接返回，MainLayout移除顶部按钮
- **Tests**: 3个测试覆盖权限、成功切换、跨家庭隔离
- **Implementation Order**: 后端API → 前端API → UI按钮 → 退出逻辑 → 清理