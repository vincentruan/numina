# 盲盒功能闭环设计

**日期:** 2026-05-12  
**状态:** 已确认

---

## 背景与问题

盲盒功能已有完整的后端模型、API 和儿童端 UI，但存在三处断链：

1. **大人端入口缺失** — 礼物池管理、概率配置、兑现记录页面已实现，但没有任何导航入口
2. **触发逻辑未接通** — `is_special_day()` 和 `should_trigger_free_draw()` 已定义但从未被调用；惊喜升级的生日上下文硬编码为 `False`
3. **生日数据缺失** — `users` 表有 `birthday` / `birthday_is_lunar` 字段，但大人端无法为孩子设置生日

---

## 目标

1. 在 Baby 页面加入盲盒管理入口（礼物池 + 兑现记录）
2. 将 FamilyPage 的"赠送星星"改为"修改信息"，支持编辑昵称、头像颜色、生日（阳历/农历）
3. 接通后端触发逻辑：任务审批通过后，根据生日/概率决定是否自动触发盲盒，并将结果返回给儿童端
4. 儿童端在任务完成后自动弹出盲盒动画（如果触发）

---

## 范围

**本次包含：**
- Baby 页面盲盒入口（礼物池 + 待兑现角标）
- FamilyPage 宝贝信息编辑弹窗（昵称 + avatar_color + 生日）
- 后端 `PATCH /family/members/{member_id}` 新增 birthday/nickname/avatar_color 字段
- 后端任务审批接通盲盒触发逻辑，`approve_instance` 响应新增 `blind_box_draw` 字段
- 儿童端任务完成后轮询或接收触发结果并弹出盲盒动画

**本次不包含：**
- 节日（非生日）触发逻辑（数据模型不支持，留后续）
- 任务难度影响概率（当前 `should_trigger_free_draw` 不接受难度参数，留后续）
- 推送通知

---

## 架构设计

### 1. Baby 页面盲盒入口

**位置：** `BabyPage.vue` 现有功能区（任务、心愿卡片同级）

**新增两个入口卡片：**
- **礼物池** — 点击跳转 `/blind-box/gifts`
- **待兑现** — 点击跳转 `/blind-box/draws`，显示 `pending_fulfillment` 数量角标

角标数据来源：复用已有的 `blindBoxStore`，在 BabyPage 挂载时调用 `fetchDraws()`，过滤 `status === 'pending_fulfillment'` 计数。

### 2. 宝贝信息编辑（替换赠送星星）

**位置：** `FamilyPage.vue` 每个孩子卡片的操作按钮区

**改动：**
- 将 `action-btn--star`（赠送星星）改为 `action-btn--edit`（修改信息）
- 点击打开 `EditChildSheet`（新建 van-popup 组件，复用现有 sheet 样式）

**EditChildSheet 字段：**
| 字段 | 组件 | 说明 |
|------|------|------|
| 昵称 | van-field | 最长 20 字符 |
| 头像颜色 | 色块选择器（复用现有 avatar_color 选项） | 6 个预设颜色 |
| 生日 | van-date-picker | 默认阳历 |
| 农历切换 | van-switch | 切换后重新选择日期 |

**后端接口：** `PATCH /family/members/{member_id}`（已有 role patch，扩展同一路由或新增端点）

请求体：
```json
{
  "display_name": "string | null",
  "avatar_color": "string | null",
  "birthday": "YYYY-MM-DD | null",
  "birthday_is_lunar": "boolean | null"
}
```

响应：`UserResponse`（已有 schema，需确认包含 birthday 字段）

### 3. 后端触发逻辑接通

**触发时机：** 家长审批任务通过时（`POST /family/chore-approvals/{instance_id}/approve`）

**流程：**
```
approve_instance()
  ├── 现有逻辑（审批、发金币、milestone 检测）
  └── 新增：blind_box_trigger()
        ├── 检查家庭盲盒配置是否 enabled
        ├── 获取孩子、父母、兄弟姐妹的 birthday
        ├── 调用 is_special_day() 判断今天是否特殊日
        ├── 调用 should_trigger_free_draw(config, is_special) 决定是否触发
        ├── 如果触发：
        │     ├── 调用 should_upgrade_surprise(config, {is_parent_bday, is_sibling_bday})
        │     ├── 调用 pick_gift(gifts, config)
        │     ├── 创建 BlindBoxDraw 记录（coins_spent=0，标记为 auto_triggered）
        │     └── 返回 BlindBoxDraw 对象
        └── 如果不触发：返回 None
```

**`ChoreInstanceResponse` 新增字段：**
```python
blind_box_draw: BlindBoxDrawResponse | None = None
```

`BlindBoxDraw` 模型新增字段：
```python
is_auto_triggered: bool = False  # 区分自动触发 vs 主动抽奖
```

### 4. 儿童端自动弹出盲盒

**触发点：** 孩子完成任务后，儿童端主动轮询任务审批状态，检测到审批通过时触发盲盒计算展示。

**当前流程：** 孩子完成任务 → 等待家长审批 → 家长审批后孩子刷新任务列表

**新增流程：**

1. 孩子点击"完成任务"后，儿童端对该 `instance_id` 开始轮询 `GET /child/chores/{instance_id}/status`（新增轻量接口，仅返回 status 字段）
2. 轮询间隔 5 秒，最长轮询 10 分钟（超时后停止，不影响正常使用）
3. 检测到 status 从 `pending_approval` 变为 `approved` 时：
   - 停止轮询
   - 调用 `GET /child/blind-box/latest-auto-draw` 检查是否有未展示的自动触发抽奖
   - 如有，以全屏 overlay 弹出 `DrawAnimation.vue` 展示礼物
4. 如果任务无需审批（直接 `approved`），完成时立即检查一次 `latest-auto-draw`

**新增后端接口：**

`GET /child/chores/{instance_id}/status`
- 返回 `{ status: string }`，仅供轮询用

`GET /child/blind-box/latest-auto-draw`
- 返回最近一次 `is_auto_triggered=True` 且 `shown_to_child=False` 的 draw
- 返回后标记 `shown_to_child=True`（需在 `blind_box_draws` 表新增该字段）
- 无未展示抽奖时返回 `null`

**展示：** 复用现有 `DrawAnimation.vue`，在 `ChildChorePage.vue` 以全屏 overlay 弹出，关闭后继续正常使用。

---

## 数据库变更

| 表 | 变更 |
|----|------|
| `blind_box_draws` | 新增 `is_auto_triggered BOOLEAN DEFAULT FALSE` |
| `blind_box_draws` | 新增 `shown_to_child BOOLEAN DEFAULT FALSE` |

`users` 表的 `birthday` / `birthday_is_lunar` 字段已存在，无需变更。

---

## 文件变更清单

### 后端
- `backend/app/routers/family.py` — 新增 `PATCH /members/{member_id}` 端点（或扩展现有）
- `backend/app/schemas/family.py` — 新增 `UpdateMemberRequest` schema
- `backend/app/models/blind_box_draw.py` — 新增 `is_auto_triggered`, `shown_to_child` 字段
- `backend/app/routers/chores.py` — `approve_instance` 调用 `blind_box_trigger()`，响应新增字段
- `backend/app/schemas/chore.py` — `ChoreInstanceResponse` 新增 `blind_box_draw` 字段
- `backend/app/services/blind_box.py` — 新增 `blind_box_trigger()` 函数，接通现有触发函数
- `backend/app/routers/child_blind_box.py` — 新增 `GET /latest-auto-draw` 端点
- `backend/app/routers/chores.py` — 新增 `GET /child/chores/{instance_id}/status` 轻量轮询接口
- `backend/alembic/versions/` — 新建 migration

### 前端 main
- `frontend/apps/main/src/pages/BabyPage.vue` — 新增盲盒入口卡片
- `frontend/apps/main/src/pages/FamilyPage.vue` — 替换赠送星星为修改信息，新增 EditChildSheet
- `frontend/apps/main/src/api/family.ts` — 新增 `updateMember()` 方法
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增相关 i18n 字符串

### 前端 child
- `frontend/apps/child/src/pages/ChildChorePage.vue` — 任务完成后启动轮询，审批通过时检查并弹出盲盒 overlay
- `frontend/apps/child/src/api/blindBox.ts` — 新增 `getLatestAutoDraw()` 方法
- `frontend/apps/child/src/api/chores.ts` — 新增 `getChoreInstanceStatus(instanceId)` 方法
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — 新增自动触发相关字符串（如"🎁 任务奖励触发了盲盒！"）

---

## 验收标准

1. 家长在 Baby 页面能看到盲盒礼物池入口和待兑现角标
2. 家长在 FamilyPage 点击孩子卡片的"修改信息"，能编辑昵称、头像颜色、生日（含农历切换），保存后立即生效
3. 家长审批任务后，如果今天是孩子/父母/兄弟姐妹生日，触发概率提升至 80%；否则为 30%
4. 触发后孩子端自动弹出盲盒动画，展示礼物，带 `✨ 超预期惊喜！` 或普通样式
5. 每次自动触发只弹出一次（`shown_to_child` 防重复）
6. 盲盒未启用（`enabled=False`）时，审批流程不受影响
