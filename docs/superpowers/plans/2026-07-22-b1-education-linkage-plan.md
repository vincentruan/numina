# B1 教育联动 — Implementation Plan

> **状态**：complete（B1-a/b/c/d 后端 + B1-e 前端实现并验证，2026-07-22；B1-f no-op 无 Activity 列表前端组件）
> **完成日期**：2026-07-22
> **日期**：2026-07-22
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md) §3 域5 B1（"可选教育联动 | 家务→真实记账'教育奖励金'(需产品决策)"）+ [p0-family-finance-core-design.md](../specs/2026-07-19-p0-family-finance-core-design.md) §11
> **范围**：B1 — 家务审批通过时，按可配置汇率将虚拟星币换算成元，写入成人 Activity 活动流水（"教育奖励金"），family 级 opt-in。**不动资产/负债账户，不进净资产**。
> **侦察依据**：[p3-scout-findings memory](../../../) + B1 决策侦察（2026-07-22）。

---

## Product Decision（已确认 2026-07-22，8 fork 全部 resolve）

spec 标注"需产品决策"，8 fork 经侦察 + 用户确认，按推荐方案 resolve：

| # | fork | 决策 |
|---|------|------|
| 1 | 记账实体 | **Activity**（type=`education_reward`, entity_type=`chore`）。不动 Asset/Liability，不污染净资产。复用现有 `record_activity`。 |
| 2 | 真实 vs 虚拟 | **虚拟星币→元记账**。`coin_reward × coin_to_yuan_rate` 换算成元，写入 `Activity.amount`（float）。金额真实可看。 |
| 3 | 谁出资 | **无扣款仅记录**。不碰任何资产账户余额，家长线下兑现。"应奖励 X 元"语义。 |
| 4 | 进 dashboard? | **仅活动流**。不进净资产/分配/trend 聚合，仅 Activity 列表可见。 |
| 5 | 触发点 | **家长审批时**（`approve_instance_async`，与星币发放同点）。`_auto_approve` 跳过真实记账（避免静默创建资金记录）。 |
| 6 | 粒度 | **family 级开关**（`ChildEconomyConfig.education_reward_enabled` + `coin_to_yuan_rate`）。复用现有 family 配置表。 |
| 7 | 可逆性 | **不可逆（无需冲正）**。侦察确认 `void_instance` 仅处理 `available` 状态（hard-delete 未认领），`reject_instance` 仅处理 `pending_approval`（审批前）——**审批后无撤销路径**，与 `CoinTransaction` 同为 append-only。故无需冲正 Activity。 |
| 8 | 幂等 | **按 chore_instance_id 查重**。`approve_instance_async` 已有 `CoinTransaction` 的 `UniqueConstraint(ref_id, transaction_type)` 幂等；Activity 无 ref 唯一约束，B1 写入前按 `entity_id=instance_id` + `type='education_reward'` 查重，已存在则跳过（与 CoinTransaction IntegrityError 回滚一致）。 |

**一句话方案**：family 级 opt-in 开关（`ChildEconomyConfig.education_reward_enabled` + `coin_to_yuan_rate` 默认 1）→ 家长审批家务时，若开关开，按 `coin_reward × rate` 换算成元，写一条 `Activity`（type=`education_reward`, entity_type=`chore`, entity_id=instance_id, title=`教育奖励金-「家务名」`, amount=元值），不动任何资产账户，仅活动流水可见；`_auto_approve` 跳过；按 instance_id 查重防双写。

**为什么是 Activity 而非 Asset/新表**：Activity 模型天然适配（`amount: Float | None` + `type`/`entity_type`/`entity_id` 灵活 + `record_activity` 成熟模式，assets/liabilities 都用）；不污染净资产（Asset 会虚增家庭财富）；无新表无 migration 阻塞（仅 ChildEconomyConfig 加 2 列）。memory [[paymentrecord-numeric-activity-float-decision]] 确认 Activity.amount 故意保持 Float（跨实体快照），与 B1 元金额语义一致。

---

## Goal Capsule

**一句话**：B1 教育联动——family 级 opt-in 开关开启后，家长审批家务通过时，按可配置汇率将星币换算成元写入 Activity 活动流水"教育奖励金"，实现虚拟星币经济到真实记账的只读桥梁（不扣款、不进净资产、不可逆、幂等）。

**为什么**：spec §11 B1 要求"家务→真实记账'教育奖励金'"，补齐儿童虚拟经济与成人财务的最后一块桥梁。决策采纳最小可行真实记账——元金额进 Activity 流水满足"真实记账"语义，但不动资产负债表避免扣款/余额/净资产污染复杂度。复用现有 `record_activity` + `ChildEconomyConfig`，无新表。

**完成标准**：family 级开关 + 汇率配置 UI/API；审批时条件写入 Activity；_auto_approve 跳过；幂等查重；Activity 列表可见"教育奖励金"条目；i18n 双 locale；测试覆盖开关 on/off、汇率换算、幂等、auto_approve 跳过；`pytest`/`typecheck`/`ruff`/`mypy` 不新增失败。

---

## Product Contract

### Scope Boundaries
- **做**：ChildEconomyConfig 加 2 列（`education_reward_enabled` bool + `coin_to_yuan_rate` int）+ alembic migration；`approve_instance_async` 条件写 Activity；`_auto_approve` 跳过；Activity 列表/类型识别"教育奖励金"；family 配置 UI 加开关 + 汇率；i18n。
- **不做**：不动 Asset/Liability 余额；不进 dashboard 净资产/分配/trend 聚合；不做冲正（审批后无撤销路径）；不做 per-template/per-child 粒度（family 级够用）；不做真实资金扣款。
- **跨层**：后端 migration + model + service + config API + 前端配置 UI。

---

## Planning Contract

### Key Technical Decisions (KTDs)

#### KTD-1：ChildEconomyConfig 加 2 列，alembic migration
- `education_reward_enabled: Mapped[bool]` default False（`server_default="0"`，nullable=False）。
- `coin_to_yuan_rate: Mapped[int]` default 1（nullable=False，`server_default="1"`）。语义：1 星币 = N 元。
- alembic migration（down_revision = `7e657997df69`，最新版）`add_education_reward_to_child_economy_config`：`op.add_column` × 2。**guard fresh-DB idempotency**（memory [[alembic-fresh-db-idempotency-debt-2026-07-22]]：用 `bind.dialect.has_table`/inspection 短路，避免 fresh-DB 失败）。
- schema：`ChildEconomyConfigResponse` 加 2 字段；`ChildEconomyConfigUpdate` 加 2 字段（可选）。

#### KTD-2：approve_instance_async 条件写 Activity（与 CoinTransaction 同事务）
- 在 `approve_instance_async`（`services/chores.py:275`）写 `CoinTransaction` 后、`db.commit()` 前或后（决策：**同事务，commit 前 add，与 tx 一起 commit**——保持原子性，但 Activity 无唯一约束需先查重）：
  - 读 family 的 `ChildEconomyConfig`（已在该函数 query 了 family，扩展读 config）。
  - 若 `education_reward_enabled`：
    - **幂等查重**：`db.query(Activity).filter_by(type='education_reward', entity_id=instance_id, family_id=...).first()`——已存在则跳过。
    - `yuan_amount = float(actual_amount) * float(config.coin_to_yuan_rate)`（`actual_amount` = streak 乘后的星币数，含 bonus）。
    - 调 `record_activity(db, parent_user, 'education_reward', 'chore', instance_id, f"教育奖励金-「{instance.chore_name}」", yuan_amount)`。
    - 注意：`record_activity` 内部 `db.commit()`——若与 CoinTransaction 同事务需重构 record_activity 为不 commit 版本，或在 CoinTransaction commit 后单独调。**决策：CoinTransaction commit 后单独调 record_activity**（record_activity 自带 commit，简单；失败不回滚星币——但 record_activity 失败概率极低且仅日志影响，与现有 milestone/notification best-effort 模式一致）。best-effort try/except，失败仅 log warning 不阻断审批。
  - 若 disabled：跳过。
- **金额精度**：`yuan_amount` round 到 2 位小数（`round(..., 2)`）。

#### KTD-3：_auto_approve 跳过真实记账
- `_auto_approve`（`services/chores.py:602`）**不写 Activity**。理由：auto_approve 是超时静默通过，不应静默创建资金记录；家长显式审批 = 显式授权记账。
- 代码：`_auto_approve` 的 CoinTransaction 写入逻辑不变，仅不加 Activity 调用（自然跳过，因为 Activity 调用在 approve_instance_async 内）。

#### KTD-4：Activity 列表/类型识别"教育奖励金"
- 前端 Activity 列表（若有 type 展示）：加 `education_reward` type 的 i18n label + 图标。侦察确认 Activity type 现有 create/update/delete/sell/retire/payment/reactivate——加 `education_reward`。
- 若 Activity 列表前端不按 type 分类展示（仅 title + amount），则 title 已含"教育奖励金"中文，无需额外改动——确认 Activity 列表组件后定。**决策：最小改动——仅 i18n label 映射（若有 type label 逻辑），title 已自描述**。

#### KTD-5：family 配置 UI 加开关 + 汇率
- 前端 family/economy 配置页（侦察确认有 ChildEconomyConfig 配置 UI，auto_approve_hours + coin 兑换比率在那配）加：
  - "教育奖励金"开关（van-switch，bind `education_reward_enabled`）。
  - "星币兑换汇率"输入（van-field number，"1 星币 = N 元"，bind `coin_to_yuan_rate`）。
  - 说明文案（i18n）："开启后，家长审批家务通过时，将按汇率把星币换算成元记入活动流水'教育奖励金'，仅记录不扣款。"
- i18n：`family.educationRewardEnabled` / `educationRewardRate` / `educationRewardHint`（zh + en）。

#### KTD-6：幂等查重用 entity_id + type
- Activity 无 ref 唯一约束（不像 CoinTransaction）。查重：`type='education_reward' AND entity_id=instance_id AND family_id=X`。entity_id 存 instance_id（str）。一个 instance 最多一条 education_reward Activity。
- 与 CoinTransaction 的 `UniqueConstraint(ref_id, transaction_type)` 语义对齐（ref_id=instance_id, type=chore_earn ↔ entity_id=instance_id, type=education_reward）。

### Sequencing
1. **后端 model + migration + schema**（KTD-1）：ChildEconomyConfig 2 列 + alembic + schema。
2. **后端 service**（KTD-2/3/6）：approve_instance_async 条件写 Activity + 幂等 + _auto_approve 跳过。
3. **后端 config API**：update endpoint 接受 2 新字段。
4. **后端测试**：开关 on/off、汇率换算、幂等、auto_approve 跳过、disabled 不写。
5. **前端配置 UI**（KTD-5）+ i18n。
6. **前端 Activity 列表**（KTD-4，最小改动）。

---

## Implementation Units

### 任务表

| ID | 任务 | 改动点 | Effort | 依赖 |
|----|------|--------|--------|------|
| B1-a | ChildEconomyConfig 2 列 + migration + schema | models/child_economy_config.py + alembic + schemas | small | 无 |
| B1-b | approve_instance_async 条件写 Activity + 幂等 + _auto_approve 跳过 | services/chores.py | small-medium | B1-a |
| B1-c | config update API 接受新字段 | routers/chores.py 或 family config router | trivial | B1-a |
| B1-d | 后端测试 | tests/backend/test_chores.py | small | B1-b |
| B1-e | 前端配置 UI + i18n | family/economy config page + zh-CN/en-US | small | B1-c |
| B1-f | 前端 Activity 列表 type label（最小） | Activity 列表组件 + i18n | trivial | B1-b |

---

## Verification Contract

### 测试基线
- 后端：`uv run pytest tests/backend/test_chores.py -v` + `test_child_economy_config.py`（若有）+ `ruff check` + `mypy`（touched files）。
- 前端：`pnpm typecheck` + `pnpm test:run` + `pnpm lint`（touched）。
- alembic：`uv run alembic upgrade head` 在 dev DB + fresh-DB guard 验证（memory fresh-DB 债务，用 has_table 短路）。

### grep 门槛
- `education_reward_enabled` + `coin_to_yuan_rate` 在 model + schema + 前端 config page。
- `record_activity(db, parent_user, 'education_reward'` 在 services/chores.py approve_instance_async。
- `_auto_approve` 无 `education_reward` 调用。

### 手动端到端
- family config 开启教育奖励 + 汇率=2 → 家长审批 10 星币家务 → Activity 列表新增"教育奖励金-「XX」" amount=20.0。
- 开关关 → 审批不写 Activity。
- 重复审批同一 instance（幂等）→ 不双写。
- auto_approve（超时）→ 不写 Activity。

---

## Definition of Done

- [x] B1-a：ChildEconomyConfig 加 education_reward_enabled(bool default False) + coin_to_yuan_rate(int default 1) + alembic migration e5d75abd9827（down_revision=6c8a42d83b59 实际 head，fresh-DB guard）+ schema（ChildEconomyConfigResponse/Update + FamilySettingsResponse/Update 两路径）。
- [x] B1-b：approve_instance_async 开关开时按汇率写 Activity（type=education_reward, entity_type=chore, entity_id=instance_id, amount=元值含 streak bonus）；_auto_approve 跳过（无 Activity 调用）；幂等查重（type+entity_id+family_id）。
- [x] B1-c：config update API 接受 2 新字段（PATCH /family/settings + PUT /economy-config 两路径）+ 校验（rate≥0）。
- [x] B1-d：5 测试覆盖开关 on/off、汇率换算含 streak×rate、幂等、auto_approve 跳过。test_chores 41 passed。
- [x] B1-e：前端配置 UI 开关 + 汇率输入 + 说明 + i18n 双 locale（CoinRatesPage + api/family.ts + stores/family.ts + zh-CN/en-US 6 keys）。
- [x] B1-f：no-op——无 Activity 列表前端组件，title 已自描述。
- [x] i18n 完整（zh + en，settings.* 6 keys + toast.educationRewardRateInvalid）。
- [x] `uv run pytest tests/backend/` 1246 passed/0 failed/1 skipped（1241 基线 + 5 新 B1）；`pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox TDZ suite failure；`ruff`/`mypy` 无新增错误（预存 E712/B904 stash 验证）。
- [x] 无 fake completion：无 test.skip/.only/TODO/stub。

---

## 实现备注（2026-07-22 执行期发现）

1. **alembic down_revision 修正**：plan 原写 `7e657997df69`（侦察时误判为最新），实际 alembic head 是 `6c8a42d83b59`（S1 theme_color）。executor 据实采用 `6c8a42d83b59`，避免 migration chain 分叉。migration `e5d75abd9827` 含 `_existing_columns` fresh-DB guard（has_table + get_columns 短路），dev DB 已验证 apply 成功。
2. **endpoint 接线修正（关键）**：plan 原按侦察结论把 B1 字段加到 `PUT /economy-config`（ChildEconomyConfigResponse/Update），但前端 CoinRatesPage 实际调用 `PATCH /family/settings`（FamilySettingsResponse/Update）—— 两者是不同 endpoint，`/economy-config` 前端无消费者。已修正：把 `education_reward_enabled` + `coin_to_yuan_rate` 同步加到 `FamilySettingsUpdate` + `FamilySettingsResponse` + 两个 `/settings` handler（PATCH :275 + GET :311），与 CoinRatesPage 实际调用路径一致。`/economy-config` 路径的字段保留（一致，不破坏）。验证：test_family_settings + test_family passed，ruff 无新增（8 预存 E712）。

## Deferred / Open Questions

- **真实资金扣款**（fork 2/3 完整版）：本批仅记录不扣款；若未来要真实扣家长资产，需选资金来源 Asset + 余额不足处理 + 进 dashboard，独立后续项。
- **per-template/per-child 粒度**（fork 6 扩展）：本批 family 级；若需某些家务给真实奖励某些不给，加 ChoreTemplate.real_reward_enabled 列 + form UI，独立后续。
- **冲正**（fork 7）：审批后无撤销路径故无需；若未来加审批后 void/reject，需补 -X 对冲 Activity。
- **进 dashboard**（fork 4）：本批仅活动流；若要进净资产，需 dashboard 聚合 education_reward，独立后续。

---

## 依赖与后续

- **前置**：P0-P3 其余项已完成（L7/D8/A6 done，W6b 已实现）。
- **解锁**：B1 完成后 spec §11 P3 全部 resolve（W6b/L7/D8/A6/B1 全 done）。
