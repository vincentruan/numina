# B1 per-template 粒度 — Implementation Plan

> **状态**：complete（B1 per-template 粒度实现并验证，2026-07-22）
> **完成日期**：2026-07-22
> **日期**：2026-07-22
> **父文档**：[2026-07-22-b1-education-linkage-plan.md](./2026-07-22-b1-education-linkage-plan.md) §Deferred（per-template 粒度扩展）+ [2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md) §3 B1
> **范围**：B1 教育联动从 family 级扩展到 per-template 粒度——ChoreTemplate 加 `real_reward_enabled`，家长可精细控制哪些家务给真实教育奖励。
> **决策**：查询（非快照）+ default=True（向后兼容）。
> **侦察依据**：B1 per-template scout（2026-07-22）。

---

## Product Decision（已确认 2026-07-22）

| fork | 决策 | 理由 |
|------|------|------|
| 快照 vs 查询 | **查询**（approval 时查 template.real_reward_enabled）| approval 即时行为，flag 是一次性门控（非历史记录字段），与 coin_to_yuan_rate 实时读 config 一致；编辑 template 不回溯改已审批实例 |
| 默认值 | **default=True** | 5 现有 B1 测试不传此字段，default=True 保持 family 开关 ON→写 Activity 现有行为；default=OFF 会静默破坏所有现有 template + 5 测试 |

**语义变化**：family 开关从"全局门"变成"全局门 × per-template 门"。default=True = 所有现有 template 默认参与（opt-out 语义），不破坏现有行为。

---

## Goal Capsule

**一句话**：ChoreTemplate 加 `real_reward_enabled`（default True）+ alembic + schema + approve 门控 + 前端 chore 表单 van-switch（family 开关 OFF 时 disable）+ 测试。

**为什么**：B1 family 级开关是全有或全无；per-template 让家长精细控制（如"做家务给教育奖励，但整理床铺这种小事不给"）。default=True 向后兼容，现有家庭行为不变。

**完成标准**：template flag + approve 门控 + 前端表单 + i18n + 测试；`pytest`/`typecheck`/`ruff`/`mypy` 不新增失败。

---

## Planning Contract

### 侦察结论
- `ChoreTemplate`（`chore.py:31`）：加 `real_reward_enabled: Mapped[bool]` default True。
- `approve_instance_async`（`chores.py:275`）B1 块（:341-383）：当前 `if config and config.education_reward_enabled:` → 加 `and template and template.real_reward_enabled`。**查询 template**（`db.query(ChoreTemplate).filter_by(id=instance.template_id).first()` 或 `instance.template` lazy load）。
- `ChoreInstance`（`chore.py:50`）快照 chore_name/emoji/coin_reward（`chores.py:224`），**不快照 reward flag**（决策：查询）。
- alembic head = `e5d75abd9827`（B1 migration）。
- 前端表单：`BabyChoreCreatePage.vue`（form :91, submit :110）+ `BabyChoreTemplateEditPage.vue`（form :110, submit :165, load :141）。
- `api/chores.ts`：ChoreTemplate/Create/Update 接口。
- `schemas/chore.py`：ChoreTemplateCreate(:20)/Update(:62)/Response(:93)。
- 现有 5 B1 测试（`test_chores.py:566-721`）用 `daily_template` fixture 不传 flag——default=True 保持通过。

### KTD-1：ChoreTemplate 列 + migration
- model `chore.py:31` 加 `real_reward_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)`。加 Boolean import。
- alembic 新文件 down_revision=`e5d75abd9827`：`op.add_column('chore_templates', sa.Column('real_reward_enabled', sa.Boolean(), nullable=False, server_default='1'))`。**fresh-DB guard**：`_existing_columns` has_column 短路（复用 B1 migration e5d75abd9827 的 `_existing_columns` 模式）。downgrade 同 guard。

### KTD-2：schema + service
- `schemas/chore.py`：Create `real_reward_enabled: bool = True`；Update `bool | None = None`；Response `real_reward_enabled: bool`。
- `services/chores.py`：
  - `create_template`（:37）：ctor 传 `real_reward_enabled=req.real_reward_enabled`。
  - `update_template`（:81）：`if req.real_reward_enabled is not None: t.real_reward_enabled = ...`。
  - **approve B1 块（:350）**：`if config and config.education_reward_enabled:` → 加查询 template + `and template and template.real_reward_enabled:`。

### KTD-3：前端表单 van-switch + family 开关联动
- `BabyChoreCreatePage.vue` + `BabyChoreTemplateEditPage.vue`：加 van-switch 绑 `form.real_reward_enabled`，submit payload 含字段；edit 页 load `found.real_reward_enabled`。
- **family 开关联动**：per-template 开关在 family `education_reward_enabled` OFF 时无意义——disable 或 hide（读 family config state，CoinRatesPage 已有 economy config fetch 模式）。决策：**family OFF 时 disable + hint**（比 hide 更可发现，家长知道有此选项）。
- `api/chores.ts`：3 接口加 `real_reward_enabled`。
- i18n：`baby.choreForm.realRewardEnabled` + `realRewardEnabledHint`（zh+en，说明"family 开关关闭时此项无效"）。

### KTD-4：测试
- 现有 5 B1 测试 default=True 不变通过。
- 新增：template flag OFF + family ON → 不写 Activity；create/update endpoint 持久化 flag。

---

## Implementation Units

| ID | 任务 | 改动点 | Effort |
|----|------|--------|--------|
| B1t-a | ChoreTemplate 列 + migration + schema | chore.py + alembic + schemas/chore.py | small |
| B1t-b | service approve 门控 + create/update | services/chores.py | small |
| B1t-c | 前端表单 van-switch + family 联动 + api 类型 + i18n | BabyChoreCreate/EditPage + api/chores.ts + i18n | small-medium |
| B1t-d | 测试 | test_chores.py | small |

---

## Verification Contract

- 后端：`uv run pytest tests/backend/test_chores.py -v`（41+2 passed）+ `ruff`/`mypy` touched；alembic fresh-DB guard。
- 前端：`pnpm typecheck` 0；`pnpm test:run` 968+1预存；`pnpm lint` touched。
- 手动：family ON + template ON→写 Activity；template OFF→不写；前端 family OFF 时 per-template 开关 disable。
- 无 fake completion。

---

## Definition of Done

- [x] B1t-a：ChoreTemplate.real_reward_enabled（bool default True, server_default="1"）+ alembic `f6e87bc90e3a`（down_revision e5d75abd9827 + `_existing_columns` fresh-DB guard）+ schema 3 字段。
- [x] B1t-b：approve 门控 `family ON AND template.real_reward_enabled`（查询 template，:367 + :741）；create/update 传字段。
- [x] B1t-c：前端 BabyChoreCreate/EditPage van-switch（`:disabled="!familySwitchOn"` family 联动 + hint）+ api 类型 + i18n 双 locale（realRewardEnabled/realRewardEnabledHint）。
- [x] B1t-d：2 新测试（template OFF→不写 Activity；create/update 持久化 flag）；现有 5 B1 测试 default=True 不变通过。
- [x] `uv run pytest tests/backend/` 1248 passed/0 failed/1 skipped（1246 基线+2 新）；`pnpm typecheck` 0；`pnpm test:run` 968+1预存；`ruff`/`mypy` 无新增（预存 B904 stash 验证）；alembic upgrade head + downgrade round-trip + 二次 upgrade short-circuit 验证。
- [x] 无 fake completion。
