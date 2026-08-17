---
title: Rental Contract Management - Plan
type: feat
date: 2026-08-17
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

## Goal Capsule

- **Objective:** 为 Numina 家庭资产系统新增「租约管理」功能，支持房东收租、租客付租、以及同时两种角色的场景
- **Authority:** 用户确认的产品设计（方案 A 轻量扩展）+ 头脑风暴补充（6 项决策）
- **Stop conditions:** 所有 Implementation Units 完成并通过 Verification Contract；数据模型不需要时不做过度设计
- **Execution profile:** 全栈 — ORM model → API → frontend pages → tests
- **Tail ownership:** 实现者负责端到端交付

---

## Product Contract

### Summary

新增 `RentalContract` 模型和「租约」tab（财务页第 4 个 tab），覆盖房东出租收租、租客租房支出、以及同时两种角色三种场景。租约数据接入 AI context 供财务教练感知，Dashboard 增加可选的净租金现金流指标。

### Problem Frame

Numina 当前追踪资产（房产/车辆/金融）和负债（房贷/车贷/信用卡），但租房场景没有归属：房东的租金收入无处记录，租客的月租和押金无处追踪。对于同时是房东和租客的用户（比如出租一套、租住另一套），净现金流更无法一目了然。

### Requirements

**数据模型**

- R1. 新增 `RentalContract` 模型，字段：id (Snowflake), user_id, family_id, role (landlord/tenant), monthly_rent (Numeric 18,2), deposit (Numeric 18,2), start_date, end_date (nullable), linked_asset_id (nullable, FK → assets), counterparty (nullable), notes (nullable), currency (default CNY), is_active (default True), created_at, updated_at
- R2. role='landlord' 时 linked_asset_id 关联房产资产；role='tenant' 时 linked_asset_id 为 null
- R3. end_date 为 null 表示不定期租约

**API**

- R4. CRUD 端点：GET/POST /rental-contracts, GET/PATCH/DELETE /rental-contracts/{id}
- R5. POST 返回 201；DELETE 为软删除（is_active=False）
- R6. GET 列表支持 query params：role (landlord/tenant), active_only (bool)
- R7. GET /rental-contracts/summary 返回：月租金收入、月租金支出、净现金流、活跃押金总额
- R8. 遵循项目约定：SnowflakeBase ID str 序列化, redirect_slashes=False, Accept-Language 错误

**前端 — 租约 Tab**

- R9. FinanceHubPage 新增第 4 个 tab "租约"（与 assets/liabilities/wishes 同级）
- R10. 租约 tab 顶部概览卡片：月租金收入、月租金支出、净现金流、活跃押金总额
- R11. 角色筛选（全部/出租/承租）+ 状态筛选（进行中/已结束）
- R12. RentalCard 显示：角色标签、关联房产名（房东）或"承租"、月租、押金、租期、对方名称
- R13. RentalFormPage 支持新增和编辑；role 选择后动态显示/隐藏关联房产选择器
- R14. RentalDetailPage 显示完整合同信息 + 编辑/结束操作

**AI 集成**

- R15. ai_context_builder.py 增加租约摘要段落（活跃租约数量、月租金收入/支出/净值），供 AI 教练在对话中感知

**Dashboard 联动**

- R16. Dashboard API 可选返回 rental_summary 字段（月净现金流），前端在 overview 卡片中一行展示
- R17. 负债率计算排除押金（押金不是债务）

**i18n**

- R18. 所有用户可见文本走 i18n（zh-CN + en-US）

### Scope Boundaries

**Deferred for later:**
- 合同自动过期（end_date 触发状态变更）— 当前 is_active 手动管理，后续可升级为 status 字段
- 押金退还流程追踪 — 当前只存金额，关闭合同即视为押金已处理
- 租金调整历史 — 续约通过新建合同实现，旧合同自动成为历史
- 持有成本追踪（物业费/维修费/保险）— 属于"现金流"模块范畴
- 合同附件上传（照片/PDF）
- 主动到期提醒（需 scheduler + notification）
- 合租/转租/短租场景

**Outside this product's identity:**
- 不做周期性记账系统
- 不做现金流管理模块（那是独立功能）

---

## Planning Contract

### Key Technical Decisions

KTD1. **新模型而非复用 Liability** (session-settled: user-directed — chosen over Liability extension: 月租是支出非债务，押金是可回收资产非负债，房东收租无法用 Liability 表达)

KTD2. **简单 is_active 二态生命周期** (session-settled: user-approved — chosen over status 字段 + 自动过期: 系统定位是资产可视化非合同管理，is_active 足够，后续可升级)

KTD3. **续约 = 新建合同** (session-settled: user-approved — chosen over 合同内租金调整: 简单直观，历史合同自动成为记录，不需要额外"租金历史"表)

KTD4. **AI 集成只做 context 接入** (session-settled: user-approved — chosen over 主动提醒 + 独立 skill: 复杂度高收益低，context 接入足够让 AI 教练感知租房数据)

KTD5. **Dashboard 联动：tab 内概览 + 可选一行指标** (session-settled: user-approved — chosen over 完整 dashboard 集成: 负债率排除押金，不改动现有计算逻辑)

KTD6. **费用分摊 MVP 不做** (session-settled: user-approved — chosen over 加入持有成本: scope 膨胀风险，留给现金流模块)

### Assumptions

- 房东的房产已在 Asset 表中（category='房产'），linked_asset_id 指向已有资产
- 押金在合同期间始终视为"占用资金"，不做部分退还追踪
- 合同结束（is_active=False）后数据保留可查看，不物理删除
- 前端路由模式：/finance?tab=rentals 进入租约 tab

---

## Implementation Units

### U1. RentalContract ORM Model

- **Goal:** 创建 RentalContract 数据库模型
- **Requirements:** R1, R2, R3
- **Dependencies:** none
- **Files:**
  - `server/packages/db/models/rental_contract.py` (new)
  - `server/packages/db/models/__init__.py` (modify — register model)
- **Approach:**
  1. 新建 RentalContract 类，继承 Base，字段按 R1 定义
  2. Numeric(18,2) 用于 monthly_rent 和 deposit（与 Asset/Liability 一致）
  3. linked_asset_id 为 nullable ForeignKey → assets.id
  4. 在 `__init__.py` 中导入 RentalContract，确保 alembic 可见
- **Patterns to follow:** `server/packages/db/models/liability.py` (字段命名、Numeric 精度、relationship 定义)
- **Test scenarios:**
  - 创建 landlord 合同，验证 linked_asset_id 关联成功
  - 创建 tenant 合同，linked_asset_id 为 null
  - 创建不定期合同，end_date 为 null
  - 验证 user_id/family_id 外键约束
- **Verification:** model 可被 alembic 检测到；`from packages.db.models import RentalContract` 成功

---

### U2. Alembic Migration

- **Goal:** 创建 rental_contracts 表的数据库迁移
- **Requirements:** R1
- **Dependencies:** U1
- **Files:**
  - `server/apps/backend/alembic/versions/<timestamp>_add_rental_contracts.py` (new)
- **Approach:**
  1. `uv run alembic revision --autogenerate -m "add rental_contracts table"`
  2. 检查生成的 migration，确保索引合理（user_id, family_id, linked_asset_id, is_active）
  3. 验证 fresh-DB 兼容性（参考项目 fresh-DB alembic 修复经验）
- **Patterns to follow:** 最近一次 migration 文件的结构
- **Test scenarios:**
  - `alembic upgrade head` 在全新 SQLite DB 上成功
  - `alembic downgrade -1` + `upgrade head` round-trip 成功
- **Verification:** migration 执行无错误；rental_contracts 表创建正确

---

### U3. Pydantic Schemas

- **Goal:** 创建 RentalContract 的请求/响应 schema
- **Requirements:** R4, R5, R7, R8
- **Dependencies:** U1
- **Files:**
  - `server/apps/backend/app/schemas/rental_contract.py` (new)
- **Approach:**
  1. RentalContractCreate: role, monthly_rent, deposit, start_date, end_date?, linked_asset_id?, counterparty?, notes?, currency?
  2. RentalContractUpdate: 全部字段 optional
  3. RentalContractResponse: 继承 SnowflakeBase（ID 自动 str 序列化）, from_attributes=True
  4. RentalContractSummary: monthly_income, monthly_expense, net_cash_flow, total_deposit
- **Patterns to follow:** `server/apps/backend/app/schemas/liability.py` (SnowflakeBase 继承, money-as-str)
- **Test scenarios:**
  - RentalContractResponse 序列化时 id 输出为 str
  - RentalContractCreate 验证 role 必须为 landlord/tenant
  - RentalContractSummary 计算逻辑正确
- **Verification:** schema import 成功；pydantic validation 正确

---

### U4. API Router (CRUD + Summary)

- **Goal:** 实现租约的完整 CRUD API + summary 端点
- **Requirements:** R4, R5, R6, R7, R8
- **Dependencies:** U1, U3
- **Files:**
  - `server/apps/backend/app/routers/rental_contracts.py` (new)
  - `server/apps/backend/app/main.py` (modify — register router)
- **Approach:**
  1. GET "" — 列表，支持 ?role=&active_only= 筛选，按 created_at desc
  2. POST "" — 创建，status_code=201
  3. GET "/{id}" — 详情
  4. PATCH "/{id}" — 更新（部分更新）
  5. DELETE "/{id}" — 软删除（is_active=False）
  6. GET "/summary" — 聚合当前家庭的活跃租约：收入/支出/净值/押金
  7. 所有端点验证 family_id 权限（当前用户属于该家庭）
  8. 在 main.py 中 include_router，prefix="/rental-contracts"
- **Patterns to follow:** `server/apps/backend/app/routers/liabilities.py` (权限验证, 错误处理, HTTPException 中文 detail)
- **Test scenarios:**
  - 创建 landlord 合同 → 201
  - 创建 tenant 合同 → 201
  - 列表筛选 role=landlord 只返回房东合同
  - 列表筛选 active_only=true 只返回活跃合同
  - PATCH 更新 monthly_rent → 验证更新成功
  - DELETE → is_active 变为 False，列表不再返回（active_only=true 时）
  - summary 聚合：2 个 landlord (各 5000) + 1 个 tenant (3500) → income=10000, expense=3500, net=6500
  - 访问其他家庭的合同 → 404
  - 创建时 linked_asset_id 不属于当前家庭 → 400
- **Verification:** pytest 全部通过；curl 手动验证 CRUD + summary

---

### U5. Frontend TS Types + API Layer

- **Goal:** 定义 TypeScript 类型和 API 请求封装
- **Requirements:** R4, R5, R6, R7
- **Dependencies:** U4
- **Files:**
  - `frontend/apps/main/src/types/index.ts` (modify — add RentalContract types)
  - `frontend/apps/main/src/api/rental.ts` (new)
- **Approach:**
  1. types: RentalContract, RentalContractCreate, RentalContractUpdate, RentalContractSummary
  2. id 类型为 string（Snowflake ID）
  3. api/rental.ts: getRentalContracts, createRentalContract, getRentalContract, updateRentalContract, deleteRentalContract, getRentalSummary
  4. 使用项目 axios 封装（@/api/index.ts）
- **Patterns to follow:** `frontend/apps/main/src/api/liability.ts` + types 中的 Liability 定义
- **Test scenarios:**
  - Test expectation: none — 类型定义和 API 封装通过 typecheck 验证
- **Verification:** `pnpm typecheck` 0 errors

---

### U6. Pinia Store

- **Goal:** 创建租约状态管理 store
- **Requirements:** R9, R10, R11
- **Dependencies:** U5
- **Files:**
  - `frontend/apps/main/src/stores/rental.ts` (new)
- **Approach:**
  1. useRentalStore: contracts list, summary, loading state, filter state
  2. actions: fetchContracts, fetchSummary, createContract, updateContract, deleteContract
  3. getters: filteredContracts (按 role + active 筛选), landlordContracts, tenantContracts
- **Patterns to follow:** `frontend/apps/main/src/stores/liability.ts` (Pinia setup, fetch pattern, error handling)
- **Test scenarios:**
  - fetchContracts 成功后 contracts 列表更新
  - filteredContracts 按 role 筛选正确
  - fetchSummary 成功后 summary 数据可用
- **Verification:** `pnpm typecheck` 0 errors；vitest 通过

---

### U7. RentalListPanel + RentalCard Components

- **Goal:** 实现租约列表面板和卡片组件
- **Requirements:** R10, R11, R12
- **Dependencies:** U6
- **Files:**
  - `frontend/apps/main/src/components/rental/RentalListPanel.vue` (new)
  - `frontend/apps/main/src/components/rental/RentalCard.vue` (new)
- **Approach:**
  1. RentalListPanel: 顶部概览卡片（van-cell-group）+ 角色筛选 chips + 状态筛选 chips + 卡片列表
  2. RentalCard: 角色标签（出租/承租）、关联房产名或"承租"、月租、押金、租期、对方
  3. 空状态用 EmptyState 组件
  4. 列表用 van-list + van-pull-refresh
- **Patterns to follow:** `frontend/apps/main/src/components/liability/LiabilityListPanel.vue` + `LiabilityCard.vue`
- **Test scenarios:**
  - 有租约时渲染卡片列表
  - 筛选 role=landlord 只显示房东合同
  - 筛选 active 状态正确过滤
  - 空列表显示 EmptyState
  - 概览卡片显示正确的收入/支出/净值/押金汇总
- **Verification:** vitest 通过；页面渲染正确

---

### U8. RentalFormPage

- **Goal:** 实现租约新增/编辑表单页
- **Requirements:** R13
- **Dependencies:** U5, U6
- **Files:**
  - `frontend/apps/main/src/pages/RentalFormPage.vue` (new)
- **Approach:**
  1. 表单字段：角色选择 (van-radio-group)、关联房产 (van-picker, 仅 landlord)、月租、押金、起租日、到期日（可选）、对方名称、备注
  2. role 切换时动态显示/隐藏关联房产选择器
  3. 编辑模式：从路由 params 获取 id，加载现有数据
  4. 提交后导航到详情页或列表页
- **Patterns to follow:** `frontend/apps/main/src/pages/LiabilityFormPage.vue` (表单结构、验证、提交)
- **Test scenarios:**
  - 新增 landlord 合同：选择关联房产 → 提交成功
  - 新增 tenant 合同：不显示关联房产选择器 → 提交成功
  - 编辑合同：加载现有数据 → 修改月租 → 提交成功
  - 必填验证：月租为空时无法提交
- **Verification:** vitest 通过；表单交互正确

---

### U9. RentalDetailPage

- **Goal:** 实现租约详情页
- **Requirements:** R14
- **Dependencies:** U5, U6
- **Files:**
  - `frontend/apps/main/src/pages/RentalDetailPage.vue` (new)
- **Approach:**
  1. 展示完整合同信息（van-cell-group）
  2. 操作按钮：编辑、结束合同（confirm dialog → delete）
  3. 房东合同显示关联房产链接
  4. 租期可视化：start_date ~ end_date（或"不定期"）
- **Patterns to follow:** `frontend/apps/main/src/pages/LiabilityDetailPage.vue` (详情结构、操作按钮)
- **Test scenarios:**
  - 渲染 landlord 合同详情，显示关联房产
  - 渲染 tenant 合同详情
  - 点击"结束合同"弹出确认 dialog → 确认后 is_active=false
  - 点击"编辑"导航到表单页
- **Verification:** vitest 通过；详情页渲染正确

---

### U10. FinanceHubPage Tab Integration + Router

- **Goal:** 将租约 tab 集成到 FinanceHubPage，注册路由
- **Requirements:** R9, R16
- **Dependencies:** U7, U8, U9
- **Files:**
  - `frontend/apps/main/src/pages/FinanceHubPage.vue` (modify — add rental tab)
  - `frontend/apps/main/src/router/index.ts` (modify — add rental routes)
- **Approach:**
  1. FinanceHubPage: 在 van-tabs 中新增 `<van-tab name="rentals">` + icon + label
  2. tab 内容区渲染 RentalListPanel
  3. FAB 按钮：在 rentals tab 时导航到 RentalFormPage
  4. Router: /rental/new, /rental/:id, /rental/:id/edit 路由
  5. 可选：Dashboard overview 增加一行 rental_summary（如果 dashboard API 返回了该字段）
- **Patterns to follow:** FinanceHubPage 现有 tab 结构（assets/liabilities/wishes）
- **Test scenarios:**
  - 点击"租约" tab 切换成功
  - URL ?tab=rentals 直接打开租约 tab
  - FAB 点击导航到新增表单页
  - 路由 /rental/:id 渲染详情页
- **Verification:** typecheck 0 errors；页面切换正常

---

### U11. i18n Keys

- **Goal:** 添加租约相关的所有 i18n 文本
- **Requirements:** R18
- **Dependencies:** U7, U8, U9, U10
- **Files:**
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify)
  - `frontend/apps/main/src/i18n/locales/en-US.ts` (modify)
- **Approach:**
  1. 新增 rental namespace：title, role, landlord, tenant, monthlyRent, deposit, startDate, endDate, counterparty, summary, monthlyIncome, monthlyExpense, netCashFlow, totalDeposit, endContract, editContract, etc.
  2. 角色筛选/状态筛选文本
  3. 表单验证错误文本
  4. 空状态文本
- **Patterns to follow:** 现有 liability namespace 的 key 结构
- **Test scenarios:**
  - Test expectation: none — i18n key 通过 typecheck + 运行时验证
- **Verification:** `pnpm typecheck` 0 errors；页面文本全部通过 t() 引用

---

### U12. AI Context Integration

- **Goal:** 在 AI context builder 中增加租约摘要
- **Requirements:** R15
- **Dependencies:** U4
- **Files:**
  - `server/apps/backend/app/services/ai_context_builder.py` (modify)
- **Approach:**
  1. 新增 _build_rental_summary() 方法
  2. 查询活跃租约： landlord 数量/总收入, tenant 数量/总支出, 净值
  3. 输出段落示例："## Rental Contracts\n- Landlord: 1 contract, monthly income ¥5,000\n- Tenant: 1 contract, monthly expense ¥3,500\n- Net: +¥1,500/month"
  4. 在无活跃租约时跳过该段落
- **Patterns to follow:** ai_context_builder.py 中现有段落构建模式（_build_asset_summary, _build_liability_summary）
- **Test scenarios:**
  - 有 landlord + tenant 合同时生成正确摘要
  - 无活跃租约时不生成该段落
  - 只有 landlord 合同时只显示收入
- **Verification:** pytest 通过；AI 对话中能感知租房数据

---

### U13. Backend Tests

- **Goal:** 完整的后端测试覆盖
- **Requirements:** R1-R8, R15
- **Dependencies:** U1-U4, U12
- **Files:**
  - `server/tests/backend/test_rental_contracts.py` (new)
- **Approach:**
  1. Model 层：创建/查询/关系验证
  2. API 层：CRUD + summary + 权限验证 + 筛选
  3. AI context：摘要生成验证
  4. 使用项目测试 fixtures（client, db session）
- **Patterns to follow:** `server/tests/backend/test_liabilities.py`
- **Test scenarios:**
  - 完整 CRUD 流程
  - 跨家庭权限隔离
  - Summary 聚合正确性
  - 软删除后列表不返回
  - AI context 摘要格式
- **Verification:** `cd server && uv run pytest tests/backend/test_rental_contracts.py -v` 全部通过

---

### U14. Frontend Tests

- **Goal:** 前端组件和 store 测试
- **Requirements:** R9-R14, R18
- **Dependencies:** U5-U11
- **Files:**
  - `frontend/apps/main/src/components/rental/__tests__/RentalCard.spec.ts` (new)
  - `frontend/apps/main/src/components/rental/__tests__/RentalListPanel.spec.ts` (new)
  - `frontend/apps/main/src/stores/__tests__/rental.spec.ts` (new)
- **Approach:**
  1. RentalCard: 渲染 landlord/tenant 不同内容
  2. RentalListPanel: 筛选逻辑、空状态、概览卡片
  3. Store: fetch/filter/create/delete actions
- **Patterns to follow:** `frontend/apps/main/src/components/liability/__tests__/` 现有测试
- **Test scenarios:**
  - RentalCard 渲染房东合同包含房产名
  - RentalCard 渲染租客合同显示"承租"
  - RentalListPanel 筛选 role=landlord 过滤正确
  - Store fetchContracts mock API 调用
- **Verification:** `pnpm -r test:run` 新增测试全部通过

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Backend tests | `cd server && uv run pytest tests/backend/test_rental_contracts.py -v` | U13 |
| Backend full suite | `cd server && uv run pytest tests/backend/ -v` | Regression |
| Backend lint | `cd server && uv run ruff check apps/backend/app/routers/rental_contracts.py apps/backend/app/schemas/rental_contract.py` | U3, U4 |
| Backend typecheck | `cd server && uv run mypy apps/backend/app/routers/rental_contracts.py` | U3, U4 |
| Frontend typecheck | `cd frontend && pnpm -r typecheck` | U5-U11 |
| Frontend tests | `cd frontend && pnpm -r test:run` | U14 |
| Frontend lint | `cd frontend && pnpm -r lint` | U5-U11 |
| Alembic fresh DB | `cd server/apps/backend && uv run alembic upgrade head` (on fresh SQLite) | U2 |

---

## Definition of Done

- **Global:**
  - 所有 14 个 Implementation Units 完成
  - Verification Contract 全部 gate 通过
  - i18n 覆盖所有用户可见文本（zh-CN + en-US）
  - 无 `any` / `@ts-expect-error` / 硬编码中文字符串
  - ruff/mypy/typecheck/lint 0 errors

- **Per-unit:** 每个 U 的 Verification 条件满足

- **Cleanup:** 无实验性代码、无 TODO 注释、无死代码残留
