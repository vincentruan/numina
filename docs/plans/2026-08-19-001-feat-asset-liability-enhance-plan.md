---
title: Asset & Liability Management Enhancement - Plan
type: feat
date: 2026-08-19
topic: asset-liability-enhance
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** 增强资产和负债的录入与管理能力——日期选择器支持约 126年跨度（1950 ~ 当前+50年）和"无限期"、负债支持多种还款方式（等额本金/等额本息/先息后本/一次性还本）、负债支持回溯录入已存续的贷款并自动生成历史还款计划。
- **Product authority:** 负债侧完整增强（还款方式 + 回溯 + 历史记录），资产侧仅升级日期选择器。
- **Execution profile:** code — 涉及数据模型、计算逻辑、前端表单和详情页。

---

## Product Contract

### Summary

增强 Numina 的资产/负债管理能力，使其能准确表达真实世界的金融场景：100年日期跨度和"无限期"选项覆盖永久资产和长期负债；四种还款方式覆盖房贷、车贷、经营贷、短期借贷；混合模式回溯录入让用户快速还原已存续负债的历史状态和当前余额。

### Problem Frame

当前系统的资产/负债录入假设"即时录入"——用户在购买或贷款发生的当下记录。但现实中：

- 用户可能在购房3年后才使用 Numina，无法准确还原历史还款进度和当前余额。
- `PaymentRecord.paid_at` 写死为服务器当前时间，无法录入过去已发生的还款。
- 日期选择器仅覆盖当前 ±10年，无法表达20年房贷、30年土地等长周期资产。
- 还款计算仅支持等额本息和最低还款，缺少等额本金（月供递减）等常见模式。
- 没有"无限期"概念——土地等永久资产、循环信用等无固定期限负债无法准确表达。

这些限制导致用户要么无法录入、要么录入不准确，财务全景图的可信度受损。

### Key Decisions

- **混合模式回溯 (session-settled: user-directed — chose C over A/B):** 系统根据参数自动生成历史还款计划并默认标记为已还，用户仅需纠正异常期。全自动回溯（方案 A）操作成本高，快照式录入（方案 B）丢失历史。混合模式兼顾精度和便捷。
- **四种主流还款方式 (session-settled: user-directed — chose B over A/C):** 等额本息、等额本金、先息后本、一次性还本，保留现有最低还款模式。覆盖房贷/车贷/经营贷/短期借贷场景。
- **"无限期"= 无到期日 (session-settled: user-directed — chose A):** 资产侧指无报废/到期日期（如土地）；负债侧指无固定到期日（如循环信用）。实现为 `end_date = null`。现有 null 记录通过一次性迁移设为哨兵值（如 2100-01-01），null 专属"无限期"语义。
- **务实折中方案 (session-settled: user-approved — chose option 3):** 负债侧做完整增强（还款方式 + 回溯 + 历史记录），资产侧仅升级日期选择器。资产估值是独立维度的问题，不适合套还款计划思路。
- **余额调整独立于还款记录 (review-applied):** 余额调整（实际 ≠ 理论时的对齐）使用独立的 balance_correction 机制，不复用 PaymentRecord 表，避免下游"已还总额"聚合误算。

### Requirements

**Date picker upgrade (shared)**

- R1. 所有 `van-date-picker` 实例的可选年跨度扩展至约 126年（1950 ~ 当前+50年）（`min-date` 设为 `1950-01-01`，`max-date` 设为当前日期 +50年）。影响：`LiabilityForm`（start_date, end_date）和 `AssetForm`（purchase_date, maturity_date, warranty_expiry_date）。
- R2. 日期字段新增"无限期"开关，复用 `AssetForm` 已有的"不限"按钮模式（`expected_lifespan_years` 的实现方式）。勾选后清空对应日期字段（设为 null）。取消勾选时，日期选择器恢复为空（需用户重新选择），不自动恢复旧值。
- R3. "无限期"适用范围：负债 `end_date`（无固定到期日）、资产 `maturity_date` 和 `warranty_expiry_date`（无到期/保修截止日）。负债 `start_date` 和资产 `purchase_date` 不适用——它们必须有值。

**Repayment method extension (liability)**

- R4. Liability 新增 `repayment_method` 字段，支持以下还款方式：
  - `equal_payment`（等额本息）— 月供固定，现有逻辑
  - `equal_principal`（等额本金）— 每月还本固定，月供递减
  - `interest_only`（先息后本）— 定期付息，到期一次性还本
  - `bullet`（一次性还本）— 到期一次性还清本息
  - `minimum_payment`（最低还款）— 现有信用卡模式
- R5. `calc_amortization` 计算器扩展：根据 `repayment_method` 分支计算逻辑。等额本金需计算每期递减的月供；先息后本需分离付息期和本金偿还期。
- R5b. InterestForecast 组件适配至少两种还款方式的展示：等额本息（固定月供预测线）和等额本金（递减趋势线）。其余 3 种方式（interest_only / bullet / minimum_payment）降级为总额/摘要展示（如"每月付息 X，到期还本 Y"）。
- R6. LiabilityForm 新增还款方式选择器（下拉或单选），默认值 `equal_payment`。

**Retroactive liability recording (liability)**

- R7. 当用户录入负债且 `start_date` 早于当前日期时，系统自动执行回溯（无需用户手动触发按钮，在表单其他必填字段就绪后自动计算）：
  1. 根据原始金额、利率、还款方式、开始日期、总期数，生成从 start_date 到今天的完整历史还款计划表。
  2. 历史期数默认标记为"已还"，计算理论当前余额。
  3. 展示理论余额，用户可确认或输入实际余额。
  4. 若实际余额 ≠ 理论余额，创建一条余额调整记录（balance_correction）对齐，与还款记录分离。
  5. 前置校验：利率为 0 时仍生成计划（无息分期）；start_date 晚于今天时禁用回溯流程；历史期数超过 120 期（10年）时提示用户确认。
- R8. 用户录入还款记录时，`paid_at` 改为用户可指定的日期字段（不再写死为服务器当前时间）。API 层 `paid_at` 为可选字段，缺省值为当前日期（保持向后兼容）。UI 层日期选择器默认今天，但允许选择过去的日期。
- R9. 回溯生成的还款记录在 UI 中标记为"系统计算"，与用户手动录入的记录区分。用户可编辑或删除个别历史记录以纠正偏差。

### Key Flows

- F1. 回溯录入已存续负债
  - **Trigger:** 用户在 LiabilityForm 中填写 start_date 为一个过去的日期。
  - **Steps:**
    1. 用户填写：原始金额、利率、还款方式、开始日期、总期数。
    2. 表单其他必填字段（原始金额、利率、还款方式、总期数）就绪后，系统自动触发回溯计算，生成历史还款计划表。
    3. 系统展示：理论当前余额、已还期数、剩余期数。
    4. 用户确认理论余额，或输入实际余额。
    5. 若用户输入了不同的实际余额，系统提示"实际余额与理论余额不一致，将创建余额调整记录"，用户确认。
    6. 提交后：历史还款记录批量创建（标记为"系统计算"），remaining_amount 设为用户确认/输入的值。
  - **Covered by:** R4, R5, R7, R9

- F2. 录入历史还款
  - **Trigger:** 用户在 LiabilityDetailPage 点击"记录还款"。
  - **Steps:**
    1. 还款对话框新增日期选择器，默认值为今天。
    2. 用户填写金额、选择实际还款日期（可以是过去的日期）。
    3. 提交后，PaymentRecord 的 paid_at 为用户选择的日期。
  - **Covered by:** R8

- F3. "无限期"切换
  - **Trigger:** 用户在日期字段旁点击"无限期"开关。
  - **Steps:**
    1. 勾选"无限期"→ 日期选择器隐藏/禁用，对应字段设为 null。
    2. 取消勾选 → 日期选择器恢复，用户可选择具体日期。
    3. 对负债 end_date：保存后，该负债无固定到期日（InterestForecast 按永续计算）。
  - **Covered by:** R2, R3

### Acceptance Examples

- AE1. 回溯录入3年前房贷
  - **Covers R7, R9.**
  - **Given:** 用户3年前贷款100万，年利率4.9%，等额本息，30年（360期）。
  - **When:** 用户今天录入该负债，填写 start_date = 3年前。
  - **Then:** 系统生成36期历史还款记录（标记为"系统计算"），展示理论剩余余额约94万，用户确认或修正。

- AE2. 等额本金录入
  - **Covers R4, R5.**
  - **Given:** 用户选择还款方式 = 等额本金，贷款50万，年利率3.5%，20年。
  - **When:** 系统计算还款计划。
  - **Then:** 第1期月供最高（本金2083 + 利息1458 = 3541），之后每月递减约6元，最后一期最低。

- AE3. 永久资产录入
  - **Covers R2, R3.**
  - **Given:** 用户录入一块土地（无到期日）。
  - **When:** 用户在 maturity_date 字段勾选"无限期"。
  - **Then:** 日期选择器隐藏，maturity_date 保存为 null，详情页显示"无限期"。

### Scope Boundaries

**Deferred for later:**
- 资产历史估值追踪（资产估值是独立维度，不在此次范围）
- 还款计划的日历视图（已在 `2026-04-10-004-ai-liability-advisor-requirements.md` 中明确推迟）
- 额外还款模拟器的独立 UI（同上，已在 advisor brainstorm 中推迟）

**Outside this product's identity:**
- 实际还款执行（不集成银行支付）
- 利率变动自动追踪（LPR 调整等）
- 多币种还款计划的汇率换算

### Dependencies / Assumptions

- **Dependencies:**
  - Vant 4 `van-date-picker` 的 `min-date`/`max-date` props 行为需验证（当前所有实例均未使用这些 props）。
  - 现有 `calc_amortization`（`server/packages/domain/liability_calculator.py`）的扩展需保持向后兼容——等额本息和最低还款的现有调用方不受影响。
  - 回溯生成的历史记录需要 alembic migration 支持（PaymentRecord.paid_at 从 `server_default=func.now()` 改为 `nullable=False, default=datetime.utcnow` — Python 层默认，详见 KTD4）。

- **Assumptions:**
  - "无限期"在所有上下文中都意味着 `date = null`，不需要单独的 flag 字段。现有 null 记录通过 alembic migration 一次性设为哨兵值（如 2100-01-01）。
  - 余额调整使用独立的 balance_correction 机制（不复用 PaymentRecord 表），避免下游还款聚合查询误算。
  - 用户录入的 `start_date` 不会早于 1950-01-01，由日期选择器 min-date 约束。

---

## Planning Contract

Product Contract unchanged from brainstorm — no scope changes.

### Key Technical Decisions

KTD1. **日期范围：固定 1950 下限 + 当前 +50年上限** — Vant `van-date-picker` 默认 `maxDate` 是今天（会阻断未来日期选择），必须显式设置 `max-date`。`min-date` 设为 `new Date(1950, 0, 1)` 覆盖 R1 和 Assumptions 的一致性。Governs R1。

KTD2. **`repayment_method` 存储为 string enum** — 使用 `String` 列（非 integer），值为 `equal_payment` / `equal_principal` / `interest_only` / `bullet` / `minimum_payment`。默认值 `equal_payment`。与项目现有 enum 模式一致（如 `category` 字段）。Governs R4, R6。

KTD3. **前端计算理论余额，后端执行创建** — 回溯录入时，前端先调用 `POST /liabilities/simulate`（扩展 `repayment_method` 参数）获取理论余额，展示给用户确认/修正。确认后前端提交 `LiabilityCreate`，携带用户确认的 `remaining_amount` 和可选的 `generate_history: true` 标志。后端在 `create_liability` 中根据标志生成历史 PaymentRecord，但不创建 BalanceCorrection（余额调整仅用于创建后的独立调整操作，不在创建流程中触发）。这避免了新增 API 端点，复用现有 simulate 接口。Governs R7, F1。

KTD4. **`paid_at` 移除 `server_default`，API schema 设默认值** — PaymentRecord 模型层 `paid_at` 改为 `nullable=False, default=datetime.utcnow`（Python 层默认），API schema `PaymentRequest` 中 `paid_at` 为 `Optional[datetime] = None`，service 层 `if paid_at is None: paid_at = datetime.utcnow()`。保持向后兼容——不传 `paid_at` 的调用方行为不变。Governs R8。

KTD5. **`BalanceCorrection` 独立模型** — 新建 `balance_corrections` 表（不复用 `payment_records`），字段：`id`, `liability_id`, `amount`（有符号：正=增加余额，负=减少）, `reason`, `created_at`。下游聚合"已还总额"查询 `payment_records` 不受影响。Governs R7, F1。

KTD6. **PaymentRecord 新增 `source` 字段** — `source: String = "manual"`（默认），回溯生成的记录设为 `"system"`。UI 据此标记"系统计算"。不影响 `paid_at` 或 `amount` 语义。Governs R9。

KTD7. **现有 null 日期迁移为哨兵值 2100-01-01** — 一次性 alembic migration，将 `liabilities.end_date`、`assets.maturity_date`、`assets.warranty_expiry_date` 的现有 NULL 更新为 `2100-01-01`。之后 NULL 专属"无限期"语义。Governs R2, R3。

---

## Implementation Units

### U1. Date picker upgrade + "无限期" toggle

- **Goal:** 所有资产/负债表单的日期选择器支持 100年跨度，关键字段支持"无限期"开关。包含现有 null 日期的哨兵值迁移。
- **Requirements:** R1, R2, R3, F3
- **Dependencies:** none
- **Files:**
  - `frontend/apps/main/src/components/liability/LiabilityForm.vue` — 修改
  - `frontend/apps/main/src/components/asset/AssetForm.vue` — 修改
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 i18n keys
  - `frontend/apps/main/src/i18n/locales/en-US.ts` — 新增 i18n keys
  - `server/apps/backend/alembic/versions/<new>_migrate_null_dates_to_sentinel.py` — 新建
- **Approach:**
  1. 定义日期常量：`MIN_DATE = new Date(1950, 0, 1)`，`MAX_DATE = new Date(new Date().getFullYear() + 50, 11, 31)`。在两个表单中各定义（无共享组件）。
  2. LiabilityForm：为 start_date 和 end_date 的 `van-date-picker` 添加 `:min-date` 和 `:max-date` props。
  3. LiabilityForm：end_date 字段旁添加"无限期"按钮（复用 AssetForm `#right-icon` slot 的 `van-button` 模式）。`isEndInfinite` boolean ref 控制：勾选时清空 end_date、禁用 picker；取消时恢复空 picker。
  4. AssetForm：为 maturity_date 和 warranty_expiry_date 的 picker 添加 min/max-date。为这两个字段各添加"无限期"按钮（同 end_date 模式）。purchase_date 不加（必须有值）。
  5. **Vant 注意事项：** `van-field` 使用 `:model-value`（非 `:value`）确保响应式更新。
  6. Alembic migration：将 `liabilities.end_date`、`assets.maturity_date`、`assets.warranty_expiry_date` 现有 NULL 更新为 `2100-01-01`。使用 `batch_alter_table` 兼容 SQLite。添加 fresh-DB guard（检查列是否存在）。
- **Patterns to follow:**
  - AssetForm "不限" 按钮：`frontend/apps/main/src/components/asset/AssetForm.vue` L192-212（`#right-icon` slot + `@click.stop` 清空值）
  - Vant 日期选择器 popup 模式：`van-popup` + `van-date-picker`（非 inline）
  - Alembic fresh-DB guard：参考 `server/apps/backend/alembic/versions/` 中现有 migration 的 `has_column` 检查模式
- **Test scenarios:**
  - LiabilityForm start_date picker 可选择 1950-01-01 到 2076-12-31 范围内的任意日期
  - LiabilityForm end_date 点击"无限期"后 end_date 清空、picker 禁用
  - LiabilityForm end_date 取消"无限期"后 picker 恢复为空状态
  - AssetForm maturity_date 和 warranty_expiry_date 各有"无限期"按钮
  - AssetForm purchase_date 无"无限期"按钮（保持必填）
  - Alembic migration 后现有 NULL end_date 变为 2100-01-01
  - Alembic migration 在全新 DB 上运行不报错（fresh-DB guard）
- **Verification:** 启动 dev server，手动验证 LiabilityForm 和 AssetForm 的日期选择范围和"无限期"切换行为。运行 `alembic upgrade head` 验证迁移。

---

### U2. Repayment method — model, schemas, calculator, simulate

- **Goal:** Liability 支持 5 种还款方式，`calc_amortization` 按方式分支计算，`/simulate` 端点接受 `repayment_method` 参数。
- **Requirements:** R4, R5
- **Dependencies:** none
- **Files:**
  - `server/packages/db/models/liability.py` — 添加 `repayment_method` 列
  - `server/packages/domain/liability_calculator.py` — 扩展 calc_amortization
  - `server/apps/backend/app/schemas/liability.py` — LiabilityCreate/Update/Response 添加字段
  - `server/apps/backend/app/schemas/liability_simulate.py` — SimulateRequest 添加参数
  - `server/apps/backend/app/routers/liabilities.py` — simulate endpoint 传递新参数
  - `server/apps/backend/alembic/versions/<new>_add_repayment_method_to_liability.py` — 新建
  - `server/packages/domain/tests/test_liability_calculator.py` — 新建或扩展
- **Approach:**
  1. Liability model 添加 `repayment_method: Mapped[str] = mapped_column(String(30), default="equal_payment")`。
  2. Alembic migration：`op.add_column('liabilities', sa.Column('repayment_method', sa.String(30), server_default='equal_payment'))`。Fresh-DB guard。
  3. `calc_amortization` 签名扩展：添加 `repayment_method: str = "equal_payment"` 参数。按方法分支：
     - `equal_payment`：现有逻辑不变
     - `equal_principal`：月本金 = remaining / total_periods，月利息 = balance × 月利率，月供 = 本金 + 利息（逐月递减）。利用现有 `schedule` 字段输出每期明细。
     - `interest_only`：每期 = balance × 月利率（仅付息），最后一期归还全部本金。
     - `bullet`：仅一期，到期还 remaining × (1 + rate × months)。
     - `minimum_payment`：现有逻辑不变
  4. 所有计算使用 `Decimal`，每期结果用 `_q()` 量化（遵循 money convention）。
  5. `SimulateRequest` 添加 `repayment_method: str = "equal_payment"` 和 `total_periods: int | None = None`。simulate router 传递给 `calc_amortization`。
  6. Pydantic schemas：`LiabilityCreate`、`LiabilityUpdate`、`LiabilityResponse` 均添加 `repayment_method: str = "equal_payment"`。
- **Patterns to follow:**
  - Money convention: `server/packages/domain/liability_calculator.py` 中的 `TWO_PLACES` + `_q()` + `ROUND_HALF_UP`
  - String enum 列模式：参考 `Liability.category` 字段的 `String` 定义
  - Alembic `add_column` + `server_default`：参考现有 migration
- **Test scenarios:**
  - Covers AE2. `calc_amortization(equal_principal, 500000, 3.5%, 240期)` 第1期月供 = 3541（本金2083 + 利息1458），第2期递减约6元
  - `calc_amortization(interest_only, 100000, 6%, 12期)` 每期付息500，最后一期还本100000
  - `calc_amortization(bullet, 50000, 5%, 12期)` 一期还本52500（50000 + 2500利息）
  - `calc_amortization(equal_payment, ...)` 与现有结果一致（回归测试）
  - `calc_amortization(minimum_payment, ...)` 与现有结果一致（回归测试）
  - `/simulate` 传入 `repayment_method=equal_principal` 返回递减计划
  - `LiabilityCreate` 不传 `repayment_method` 默认 `equal_payment`
- **Verification:** ✅ COMPLETE. 27/27 liability tests pass (12 calculator + 4 simulate + 11 CRUD). Alembic head = `r1e2p3a4y5m6`.

---

### U3. Retroactive liability backend — history generation + balance correction

- **Goal:** 创建负债时若 start_date 在过去，后端自动生成历史 PaymentRecord（标记为 system）；余额调整通过独立的 BalanceCorrection 模型记录。
- **Requirements:** R7, R9
- **Dependencies:** U2（repayment_method 字段和 calculator 扩展）
- **Files:**
  - `server/apps/backend/app/models/balance_correction.py` — 新建
  - `server/apps/backend/app/models/__init__.py` — 注册新模型
  - `server/apps/backend/app/models/payment_record.py` — 添加 `source` 列
  - `server/apps/backend/app/schemas/liability.py` — LiabilityCreate 添加 `generate_history`, `total_periods`
  - `server/apps/backend/app/services/liability.py` — 扩展 create_liability
  - `server/apps/backend/app/services/balance_correction.py` — 新建
  - `server/apps/backend/app/schemas/balance_correction.py` — 新建
  - `server/apps/backend/app/routers/liabilities.py` — 添加 balance_correction endpoint
  - `server/apps/backend/alembic/versions/<new>_add_source_to_payment_records.py` — 新建
  - `server/apps/backend/alembic/versions/<new>_create_balance_corrections.py` — 新建
  - `server/apps/backend/tests/test_retroactive_liability.py` — 新建
- **Approach:**
  1. `PaymentRecord` 添加 `source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")`。Alembic migration add_column。
  2. 新建 `BalanceCorrection` 模型：`id`, `liability_id` (FK), `amount` (Numeric(18,2), 有符号), `reason` (Text, nullable), `created_at` (DateTime)。Alembic migration create_table。
  3. 注册 `BalanceCorrection` 到 `models/__init__.py`。
  4. `LiabilityCreate` 添加可选字段：`total_periods: int | None = None`, `generate_history: bool = False`。
  5. `create_liability` service 扩展：当 `generate_history=True` 且 `start_date < today` 时：
     a. 调用 `calc_amortization` 的 schedule 生成功能，获取每期还款明细。
     b. 过滤出 `paid_at <= today` 的期数，批量创建 `PaymentRecord`（`source="system"`, `paid_at` = 每期到期日）。
     c. 不修改 `remaining_amount`——它已经是用户确认/输入的值。
  6. Balance correction service（仅用于创建后调整，不在 `create_liability` 中调用）：`create_correction(db, user, liability_id, amount, reason)` — 创建 BalanceCorrection 记录，同时更新 `liability.remaining_amount += amount`。
  7. 新增 API：`POST /liabilities/{id}/balance-correction`（201），接受 `amount` 和 `reason`。
- **Patterns to follow:**
  - PaymentRecord 创建模式：`server/apps/backend/app/services/liability.py:76-88`
  - Money convention: Decimal 计算，Numeric(18,2) 存储
  - Alembic fresh-DB guard pattern
- **Test scenarios:**
  - Covers AE1. 创建负债 start_date=3年前, generate_history=True → 生成36条 PaymentRecord（source="system"）
  - 创建负债 start_date=今天, generate_history=True → 不生成历史记录（start_date 不在过去）
  - 创建负债 start_date=3年前, generate_history=False → 不生成历史记录
  - BalanceCorrection 创建后 liability.remaining_amount 正确更新（正数增加，负数减少）
  - PaymentRecord source 默认 "manual"，不影响现有 record_payment 行为
  - 历史 PaymentRecord 的 paid_at 按月度递增（每期对应月份）
- **Verification:** ✅ COMPLETE. 35/35 liability tests pass (12 calculator + 4 simulate + 11 CRUD + 8 retroactive). Alembic head = `b1a2l3a4n5c6`. PaymentRecord source column + BalanceCorrection table created. Retroactive history generation + balance correction endpoint functional.

---

### U4. Retroactive UI + historical payment recording

- **Goal:** LiabilityForm 添加还款方式选择器 + 回溯余额确认 UI；LiabilityDetailPage 还款对话框添加日期选择器 + 还款历史区分系统/手动记录。
- **Requirements:** R6, R7, R8, R9, F1, F2
- **Dependencies:** U1, U2, U3
- **Files:**
  - `frontend/apps/main/src/components/liability/LiabilityForm.vue` — 修改
  - `frontend/apps/main/src/pages/LiabilityDetailPage.vue` — 修改
  - `frontend/apps/main/src/api/liabilities.ts` — 修改
  - `frontend/apps/main/src/types/index.ts` — 修改
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 i18n keys
  - `frontend/apps/main/src/i18n/locales/en-US.ts` — 新增 i18n keys
  - `frontend/apps/main/src/components/liability/__tests__/LiabilityForm.spec.ts` — 扩展
- **Approach:**
  1. **LiabilityForm 还款方式选择器：** 添加 `van-field` + `van-picker` 下拉，选项为 5 种还款方式的 i18n label。默认 `equal_payment`。
  2. **回溯余额确认：** 当 `start_date < today` 且必填字段就绪时：
     a. 自动调用 `simulateLiability` API（传入 `repayment_method` + `total_periods`）获取理论余额。
     b. 在表单下方展示确认区域：理论余额 + "确认" / "修改余额" 按钮。
     c. "修改余额" 展开输入框，用户输入实际余额。若与实际不一致，显示提示文案。
     d. 提交时：`remaining_amount` = 用户确认/输入的值，`generate_history: true`，`total_periods` = 用户填写的期数。
  3. **还款对话框（LiabilityDetailPage）：** 添加日期选择器（min-date=1950, max-date=today），默认今天。提交时传 `paid_at`。
  4. **还款历史列表：** 按 `source` 字段标记。`source="system"` 的记录显示"系统计算"tag。用户可编辑/删除 system 记录（R9）。
  5. **API 扩展：** `PaymentRequest` 添加 `paid_at?: string`。`LiabilityCreate` 添加 `generate_history?: boolean`, `total_periods?: number`, `repayment_method?: string`。
- **Patterns to follow:**
  - Vant `van-field` + popup picker 模式：LiabilityForm 现有的 start_date/end_date picker
  - Payment dialog：`LiabilityDetailPage.vue` L116-144 的现有还款对话框
  - 还款记录列表：`LiabilityDetailPage.vue` 中的现有 payment history 展示
- **Test scenarios:**
  - LiabilityForm 选择 start_date=过去 → 触发 simulate 调用，展示理论余额
  - LiabilityForm 确认理论余额后提交 → payload 包含 `generate_history: true`
  - LiabilityForm 修改余额后提交 → payload 包含修改后的 `remaining_amount`
  - LiabilityForm 还款方式选择器默认 equal_payment
  - 还款对话框提交时 paid_at 默认为今天
  - 还款对话框选择过去日期后 paid_at 为用户选择的日期
  - 还款历史列表中 source="system" 记录显示"系统计算"标记
- **Verification:** ✅ COMPLETE. Frontend typecheck 0 errors, 1228/1228 tests pass. Backend 31/31 liability tests pass. LiabilityForm repayment method picker, LiabilityDetailPage payment date picker + payment history with source tags, all wired through API layer.

---

### U5. InterestForecast multi-method display

- **Goal:** InterestForecast 组件适配多种还款方式的展示，至少支持等额本息和等额本金的差异化展示。
- **Requirements:** R5b
- **Dependencies:** U2, U4
- **Files:**
  - `frontend/apps/main/src/components/liability/InterestForecast.vue` — 修改
  - `frontend/apps/main/src/api/liabilities.ts` — 修改（simulate 请求携带 repayment_method）
- **Approach:**
  1. `simulateLiability` API 调用添加 `repayment_method` 参数（从 liability 对象读取）。
  2. InterestForecast 根据 `repayment_method` 分支展示：
     - `equal_payment`：现有逻辑不变（3个场景：extra=0/500/1000）
     - `equal_principal`：展示首/末期月供范围 + 总利息
     - `interest_only`：展示"每月付息 X，到期还本 Y"
     - `bullet`：展示"到期一次性还 X（含利息 Y）"
     - `minimum_payment`：现有逻辑不变
  3. `shouldRender()` 逻辑保持不变（interest_rate 为 null/0 时隐藏）。
- **Patterns to follow:**
  - InterestForecast 现有 3-scenario 展示模式：`frontend/apps/main/src/components/liability/InterestForecast.vue`
- **Test scenarios:**
  - InterestForecast 在 equal_payment 模式下展示不变（回归）
  - InterestForecast 在 equal_principal 模式下展示首/末期月供
  - InterestForecast 在 interest_only 模式下展示月付息 + 到期还本
  - InterestForecast 在 bullet 模式下展示一次性还款总额
  - InterestForecast 在 minimum_payment 模式下展示不变（回归）
- **Verification:** ✅ COMPLETE. Frontend typecheck 0 errors, 1228/1228 tests pass. InterestForecast branches by repayment_method: equal_payment/minimum_payment keep 3-scenario display; equal_principal shows payment range; interest_only shows monthly interest + bullet principal; bullet shows lump sum total. SimulateExtraDialog only rendered for methods that support extra payment scenarios.

---

## Verification Contract

| Gate | Command | Expected |
|------|---------|----------|
| Backend tests | `cd server && uv run pytest apps/backend/tests/ packages/domain/tests/ -x` | All pass |
| Frontend typecheck | `cd frontend && pnpm typecheck` | 0 errors |
| Frontend tests | `cd frontend && pnpm vitest run` | All pass |
| Alembic fresh DB | `cd server/apps/backend && rm -f test.db && uv run alembic upgrade head` | All migrations pass on fresh DB |
| Alembic existing DB | `cd server/apps/backend && uv run alembic upgrade head` | New migrations apply cleanly |

---

## Definition of Done

- All 5 implementation units merged to main
- All verification gates pass
- R1-R9, R5b all satisfied (every requirement has at least one unit covering it)
- F1, F2, F3 flows work end-to-end in dev server
- AE1, AE2, AE3 acceptance examples verified manually
- No regressions in existing liability CRUD, simulate, or payment recording
- i18n keys added for both zh-CN and en-US
