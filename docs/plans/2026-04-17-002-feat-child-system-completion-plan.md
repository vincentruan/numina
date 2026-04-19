---
date: 2026-04-17
id: 2026-04-17-002
title: 儿童系统收尾：父母管理视角 + 家庭金币汇率配置
status: completed
origin: docs/ideation/2026-04-14-children-starcoin-ideation.md
---

# 儿童系统收尾计划

## Context

儿童星星币系统 8 个功能中，Feature #6（亲子双视角仪表盘）和 Feature #8（金银铜视觉体系）各有一个子功能未完成：

- **Feature #6 缺口**：父母管理视角——审批页（ChoreApprovalsPage、WishReviewPage）分散，无统一父母仪表盘，无法一眼看到各孩子积分余额和待办事项
- **Feature #8 缺口**：家庭金币汇率配置——`Family.coin_copper_to_silver/coin_silver_to_gold` 字段存在但无 API 读写，`CoinDisplay` 组件已支持 props 传入汇率但调用方全部使用硬编码默认值

## Architecture Decisions

### 1. 父母仪表盘：扩展 FamilyPage 而非新建页面

`FamilyPage.vue` 已有家庭成员列表。在其中新增"孩子管理"区块，展示每个孩子的积分余额、待审批数量、快捷操作入口。不新建独立路由，避免导航层级增加。

父母仪表盘所需数据：
- 各孩子积分余额：复用 `GET /child/coins/balance`（需父母身份调用，需新增父母端余额查询接口）
- 待审批家务数：`GET /family/chore-approvals`（已有）
- 待审批心愿数：`GET /family/child-wishes`（已有，过滤 `pending_review + redemption_requested`）

**决策**：新增 `GET /family/children/{child_id}/balance` 端点，供父母查询指定孩子余额。复用 `coin_service.get_balance()`，加 `require_adult` + 同家庭校验。

### 2. 家庭金币汇率：扩展现有 FamilySettings API

`PATCH /family/settings` 已有 `auto_approve_hours` 和 `ai_enabled`。直接扩展 `FamilySettingsUpdate` 和 `FamilySettingsResponse` 加入 `coin_copper_to_silver` 和 `coin_silver_to_gold`。

`GET /family/settings` 目前不存在（只有 PATCH）。需新增 `GET /family/settings` 返回当前配置，供前端初始化表单。

**决策**：不新建端点，扩展现有 `/family/settings`（GET + PATCH）。

### 3. 前端汇率传递：通过 Pinia store 全局缓存

`CoinDisplay` 已支持 `copperToSilver/silverToGold` props。问题是每个使用 `CoinDisplay` 的页面都需要知道汇率。

**决策**：在 `familyStore`（或新建 `coinConfigStore`）中缓存家庭汇率配置，在 App 初始化时（或用户登录后）一次性加载。`CoinDisplay` 的调用方从 store 读取并传入 props，不改变 `CoinDisplay` 组件本身。

---

## Implementation Units

### Unit 1: 后端 — 扩展 FamilySettings API

**文件：**
- `backend/app/schemas/family.py` — 扩展 `FamilySettingsUpdate`（加 `coin_copper_to_silver?: int`、`coin_silver_to_gold?: int`，各加 `ge=1, le=100` validator）和 `FamilySettingsResponse`（加两个字段）
- `backend/app/routers/family.py` — 新增 `GET /family/settings` 端点；扩展 `PATCH /family/settings` 处理新字段
- `backend/app/routers/family.py` — 新增 `GET /family/children/{child_id}/balance` 端点（`require_adult`，校验 child 属于同家庭）

**要点：**
- `coin_copper_to_silver` 和 `coin_silver_to_gold` 范围：`1 ≤ value ≤ 100`（防止极端值）
- `GET /family/settings` 返回 `auto_approve_hours`, `ai_enabled`, `coin_copper_to_silver`, `coin_silver_to_gold`
- `PATCH /family/settings` 所有字段可选，只更新提供的字段

**测试：** `backend/tests/test_family_settings.py`（新建）
- GET /family/settings 返回默认值（10, 10）
- PATCH 更新 coin_copper_to_silver → 持久化
- PATCH 拒绝 coin_copper_to_silver=0（422）
- PATCH 拒绝 coin_copper_to_silver=101（422）
- GET /family/children/{child_id}/balance 返回正确余额
- GET /family/children/{other_family_child_id}/balance 返回 404

---

### Unit 2: 前端 — 家庭汇率配置 store + CoinDisplay 接入

**文件：**
- `frontend/src/api/family.ts` — 新增 `getFamilySettings()` 函数（GET /family/settings）；扩展 `updateFamilySettings()` 支持 `coinCopperToSilver` 和`coinSilverToGold`
- `frontend/src/stores/familyConfig.ts`（新建）— Pinia store，缓存 `coinCopperToSilver` 和 `coinSilverToGold`，提供 `loadConfig()` action
- `frontend/src/App.vue` 或 `frontend/src/layouts/MainLayout.vue` — 登录后调用 `familyConfig.loadConfig()`（仅成人用户）
- `frontend/src/pages/child/ChildLedgerPage.vue` — `CoinDisplay` 传入 store 汇率
- `frontend/src/pages/child/ChildHomePage.vue` — `CoinDisplay` 传入 store 汇率
- `frontend/src/pages/FamilyPage.vue` — 新增汇率配置表单（两个数字输入，范围 1-100）

**要点：**
- 儿童端不需要加载汇率配置（儿童 token 无法访问 `/family/settings`）；`familyConfig.loadConfig()` 只在成人登录后调用
- `CoinDisplay` 在儿童页面使用时，从 store 读取汇率（store 初始值为默认 10/10，即使未加载也能正常显示）
- 汇率配置表单放在 `FamilyPage.vue` 的"家庭设置"区块，与 `auto_approve_hours` 并列

---

### Unit 3: 前端 — 父母仪表盘（FamilyPage 扩展）

**文件：**
- `frontend/src/api/family.ts` — 新增 `getChildBalance(childId: string): Promise<number>` 函数（GET /family/children/{child_id}/balance）
- `frontend/src/pages/FamilyPage.vue` — 新增"孩子管理"区块：
  - 每个孩子显示：头像、名字、积分余额（`CoinDisplay`）、待审批家务数、快捷跳转（审批页、心愿审核页）
  - 数据并行加载（`Promise.all`）

**要点：**
- 待审批家务数：从 `GET /family/chore-approvals` 计数（已有 API）
- 待审批心愿数：从 `GET /family/child-wishes` 过滤 `pending_review + redemption_requested`（已有 API）
- 积分余额：从新增的 `GET /family/children/{child_id}/balance` 获取
- 加载失败时各卡片降级显示（不阻塞整页）

---

## Dependencies & Sequencing

```
Unit 1 (后端 API) → Unit 2 (前端 store + CoinDisplay) → Unit 3 (父母仪表盘)
```

Unit 2 和 Unit 3 可在 Unit 1 完成后并行实现。

## Risks

| 风险 | 缓解 |
|------|------|
| 儿童端调用 `/family/settings` 返回 401 | store 只在成人登录后加载；儿童端 `CoinDisplay` 使用 store 默认值（10/10） |
| FamilyPage 并行请求过多（每个孩子一次余额请求） | `Promise.all` 并行；家庭通常 ≤5 个孩子，可接受 |
| 汇率变更后前端 store 未刷新 | PATCH 成功后更新 store；或在 FamilyPage 挂载时重新加载 |
