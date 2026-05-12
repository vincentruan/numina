# 盲盒功能闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 接通盲盒触发逻辑、补全大人端管理入口、支持宝贝信息编辑（含生日），实现任务审批后自动弹出盲盒动画的完整闭环。

**Architecture:** 后端在任务审批时调用 `blind_box_trigger()`，将触发结果写入 DB；儿童端完成任务后轮询审批状态，检测通过后拉取未展示的自动触发抽奖并弹出动画；大人端通过 Baby 页面新增入口访问已有的礼物池和兑现记录页面。

**Tech Stack:** Python/FastAPI/SQLAlchemy, Vue 3/TypeScript/Vant 4, Alembic, Pinia

**Spec:** `docs/superpowers/specs/2026-05-12-blind-box-closeloop-design.md`

---

## Task 1: DB migration — blind_box_draws 新增两列

**Files:**
- Create: `backend/alembic/versions/xxxx_blind_box_draw_auto_trigger.py`
- Modify: `backend/app/models/blind_box_draw.py`
- Modify: `backend/app/schemas/blind_box.py`

- [ ] `alembic revision --autogenerate -m "add_auto_trigger_fields_to_blind_box_draws"`，确认 upgrade 添加 `is_auto_triggered BOOLEAN DEFAULT false` 和 `shown_to_child BOOLEAN DEFAULT false`，运行 `alembic upgrade head`
- [ ] `BlindBoxDraw` model 新增 `is_auto_triggered: Mapped[bool]` 和 `shown_to_child: Mapped[bool]`
- [ ] `BlindBoxDrawResponse` schema 新增同名字段
- [ ] `cd backend && uv run pytest tests/test_blind_box.py -v` 通过
- [ ] Commit: `feat(db): add is_auto_triggered and shown_to_child to blind_box_draws`

---

## Task 2: Service — blind_box_trigger()

**Files:**
- Modify: `backend/app/services/blind_box.py`
- Create: `backend/tests/test_blind_box_trigger.py`

- [ ] 在 `blind_box.py` 末尾新增 `blind_box_trigger(db, child) -> BlindBoxDraw | None`：查配置是否 enabled → 检测孩子/父母/兄弟生日（调用已有 `is_special_day()`）→ 调用 `should_trigger_free_draw()` → 调用 `should_upgrade_surprise()` → 调用 `pick_gift()` → 创建 `BlindBoxDraw(is_auto_triggered=True, shown_to_child=False, coins_spent=0)`，`db.flush()` 后返回
- [ ] 写测试：disabled config 返回 None；空礼物池返回 None；正常触发创建 draw 且 `is_auto_triggered=True`
- [ ] `uv run pytest tests/test_blind_box_trigger.py -v` 通过
- [ ] Commit: `feat(service): add blind_box_trigger() connecting existing probability functions`

---

## Task 3: approve_instance 接通触发逻辑

**Files:**
- Modify: `backend/app/routers/chores.py`
- Modify: `backend/app/schemas/chore.py`

- [ ] `ChoreInstanceResponse` 新增 `blind_box_draw: BlindBoxDrawResponse | None = None`
- [ ] `approve_instance` 端点在现有逻辑后调用 `blind_box_trigger(db, child)`，`db.commit()`，将结果赋给 `resp.blind_box_draw`
- [ ] `uv run pytest tests/ -v -k "approve"` 通过
- [ ] Commit: `feat(api): approve_instance triggers blind box and returns draw in response`

---

## Task 4: 新增两个子端接口

**Files:**
- Modify: `backend/app/routers/child_blind_box.py`
- Modify: `backend/app/routers/chores.py`

- [ ] `GET /child/blind-box/latest-auto-draw`：查询 `is_auto_triggered=True AND shown_to_child=False` 最新一条，标记 `shown_to_child=True` 后返回，无则返回 `null`
- [ ] `GET /child/chores/{instance_id}/status`：返回 `{"status": instance.status}`，仅供轮询
- [ ] `uv run pytest tests/test_blind_box.py -v` 通过
- [ ] Commit: `feat(api): add latest-auto-draw and chore status polling endpoints`

---

## Task 5: PATCH /family/members/{id}/info

**Files:**
- Modify: `backend/app/routers/family.py`
- Modify: `backend/app/schemas/auth.py`

- [ ] `auth.py` 新增 `UpdateMemberInfoRequest(display_name, avatar_color, birthday, birthday_is_lunar)`，`UserResponse` 补充 `birthday` 和 `birthday_is_lunar` 字段（若缺失）
- [ ] `family.py` 新增 `PATCH /members/{member_id}/info`，校验同家庭成员，按需更新字段，返回 `UserResponse`
- [ ] `uv run pytest tests/ -v -k "member"` 通过
- [ ] Commit: `feat(api): add PATCH /family/members/{id}/info for nickname, avatar, birthday`

---

## Task 6: 前端 main — Baby 页面盲盒入口

**Files:**
- Modify: `frontend/apps/main/src/pages/BabyPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

- [ ] `zh-CN.ts` `baby` 节新增 `blindBoxGifts`、`blindBoxDraws` 字符串
- [ ] `BabyPage.vue` 引入 `useBlindBoxStore`，`onMounted` 时调用 `fetchDraws()`，computed 计算 `pendingDrawCount`
- [ ] 在现有 `van-cell` 列表区新增两个入口：礼物池（跳转 `/blind-box/gifts`）和待兑现（跳转 `/blind-box/draws`，显示 `van-badge`）
- [ ] `npm run typecheck` 通过
- [ ] Commit: `feat(main): add blind box entry points in Baby page`

---

## Task 7: 前端 main — FamilyPage 替换赠送星星

**Files:**
- Modify: `frontend/apps/main/src/pages/FamilyPage.vue`
- Modify: `frontend/apps/main/src/api/family.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

- [ ] `family.ts` 新增 `updateMemberInfo(memberId, { display_name?, avatar_color?, birthday?, birthday_is_lunar? })`，调用 `PATCH /family/members/{id}/info`
- [ ] `zh-CN.ts` 新增编辑弹窗相关字符串（标题、字段标签、保存按钮、toast）
- [ ] `FamilyPage.vue`：删除赠送星星按钮及相关逻辑（`grantTargetChild`、`openGrantSheet`、`submitGrant`、对应 sheet 模板和样式）；新增"修改信息"按钮，点击打开 EditChildSheet（van-popup，含昵称输入、颜色色块选择、日期选择器、农历 switch）；`submitEdit()` 调用 `updateMemberInfo()` 后刷新成员列表
- [ ] `npm run typecheck` 通过
- [ ] Commit: `feat(main): replace grant stars with edit child info sheet`

---

## Task 8: 前端 child — 任务完成后轮询并弹出盲盒

**Files:**
- Modify: `frontend/apps/child/src/pages/ChildTasksPage.vue`
- Modify: `frontend/apps/child/src/api/blindBox.ts`
- Modify: `frontend/apps/child/src/types/blindBox.ts`
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts`

- [ ] `blindBox.ts` type 新增 `is_auto_triggered: boolean` 和 `shown_to_child: boolean`
- [ ] `childBlindBoxApi` 新增 `getLatestAutoDraw()`，调用 `GET /child/blind-box/latest-auto-draw`
- [ ] `zh-CN.ts` `blindBox` 节新增 `autoTriggered`、`autoTriggeredClose` 字符串
- [ ] `ChildTasksPage.vue`：新增 `autoDraw` ref 和 `showAutoDrawOverlay` ref；新增 `pollForApproval(instanceId)` 函数（5s 间隔，最长 10min，检测到 `approved` 后调用 `checkAutoDraw()`）；`complete()` 成功后，若状态为 `pending_approval` 则后台启动轮询，若直接 `approved` 则立即调用 `checkAutoDraw()`；模板末尾新增全屏 overlay，内含 `DrawAnimation` 组件和关闭按钮
- [ ] `npm run typecheck` 通过
- [ ] Commit: `feat(child): poll approval and show auto-triggered blind box overlay`

---

## Task 9: 验收

- [ ] `cd backend && uv run pytest tests/ -v` 全部通过
- [ ] `cd frontend/apps/main && npm run typecheck` 通过
- [ ] `cd frontend/apps/child && npm run typecheck` 通过
