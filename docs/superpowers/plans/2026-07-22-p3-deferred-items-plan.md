# P3 批次 — Implementation Plan

> **状态**：complete（4/5 项实现并验证，2026-07-22；B1 推迟需产品决策）
> **完成日期**：2026-07-22
> **日期**：2026-07-22
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md)（§3 需求总表 P3 项）+ [2026-07-19-p0-family-finance-core-design.md](../specs/2026-07-19-p0-family-finance-core-design.md) §11「P3：W6b、L7、D8、A6、B1」
> **范围**：P3 批 deferred 项——W6b（文档标注完成）/ L7 抵押物联动 / D8 保值率拆实物金融 / A6 报告图片导出。**B1 推迟**（spec 明确"需产品决策"，8 fork 未决，单独走决策流程）。
> **侦察依据**：[p3-scout-findings memory](../../../) — 5 项并行 scout（2026-07-22），已记录当前实现状态。

---

## Goal Capsule

**一句话**：完成 P3 批 4 项实质工作——W6b 文档标注（已实现）、L7 负债抵押物现值 vs 剩余贷款联动显示 + 表单资产选择器、D8 金融资产年化收益率（拆实物保值率 vs 金融期间收益率）、A6 AI 报告图片导出（html2canvas）。

**为什么**：P0/P1/P2 交付了功能闭环、finance hub 载体、i18n/a11y 合规。P3 收尾 spec §11 deferred 项中**无产品决策阻塞**的 4 项，补齐负债抵押物信息闭环（L7）、资产保值率分类型正确性（D8）、报告可分享性（A6）。B1 因 spec 明确要求产品决策且 8 fork 未决，单独推迟。

**完成标准**：4 项逐项落地，每项独立 commit + 验证；`pnpm typecheck` + `pnpm test:run` + `uv run pytest`（scope）不新增失败；grep 门槛达标。

---

## Product Contract

### Scope Boundaries
- **做**：W6b（文档标注）/ L7 / D8 / A6，共 4 项。
- **不做**：B1（推迟，spec"需产品决策"，8 fork 未决）；不重构 dashboard/analytics 架构。
- **跨层**：L7 可能需 detail 路由返回 linked asset current_value（后端 enrichment）；D8 后端 calc + schema + 前端；A6 纯前端。
- **无 migration**：L7 的 `linked_asset_id` 列在 initial_snowflake_schema 已存在；D8/A6 不动表结构。

---

## Planning Contract

### 侦察结论（scout 2026-07-22）

#### W6b（心愿→资产转化回链）— ✅ 已完整实现，仅文档标注
- `realize_wish`（`server/apps/backend/app/services/wish.py:128-181`）双向设 `wish.realized_asset_id`（:166）+ `asset.from_wish_id`（:168），gated on `converts_to_asset`（:134）。
- `WishDetailPage.vue:53-60` 已显示"已转化为资产"（i18n `wish.realizedAsset`）+ router-link `/assets/{id}`；reverse link `AssetDetailPage.vue:94-95`。
- i18n zh:1042/en:683；tests `test_wishes.py:105` + `test_child_wishes.py:285-306`。
- **结论**：NO WORK NEEDED，仅更新 spec/plan 文档标注为完成。

#### L7（linked_asset 抵押物现值 vs 剩余贷款）— greenfield 显示 + 缺 form picker
- `liability.linked_asset_id` FK **已存在**（`models/liability.py:40`，schema in/out `schemas/liability.py:41,61,108`，create service `services/liability.py:43` 存储，initial_snowflake_schema:226,233）。**无 migration**。
- 缺口 1：`LiabilityDetailPage.vue:69` 只有"关联资产"→`/assets/{id}` 跳转链接，**无"抵押物现值 vs 剩余贷款"对比**。
- 缺口 2：`LiabilityForm.vue`（314 行）**完全没有资产选择器**——FormState（:151-163）+ onSubmit payload（:248-260）均无 `linked_asset_id`，字段只能 DB 直填，UI 不可达。
- 缺口 3：后端 detail 路由（`routers/liabilities.py:90` GET /{id}）返回 bare `linked_asset_id`，**不返回 linked asset current_value/name**——前端需自取资产或后端 enrich。
- **结论**：form picker + 详情对比卡 + 后端 detail enrichment（返回 linked asset name+current_value）。

#### D8（保值率拆实物/金融）— greenfield calc + display，管道半 wired
- `asset_type` 字段存在（`models/asset.py:40`，flat string `physical`/`financial`，非独立表）。
- 后端已有两函数：`get_retention_rate`（实物，`services/dashboard.py:947-1020`，`current/bought` 比率）+ `get_investment_returns`（金融，`dashboard.py:334-380`，调 `compute_return_rate`）。
- **缺口 1（calc 错）**：`compute_return_rate`（`services/asset.py:91-99`）用 `(current-purchase)/purchase*100` 总比率——**不是 spec 要求的"期间收益率"**。决策采纳**年化收益率**：`(current-purchase)/purchase × 365/持有天数 × 100`，需 `purchase_date`。
- **缺口 2（display 死）**：金融路由 `/dashboard/investment-returns`（`routers/dashboard.py:79`）+ store/api（`stores/dashboard.ts:96`/`api/dashboard.ts:136`）已 wired，但 `investmentReturns` **无任何 .vue 消费**；`InsightsResponse`（`schemas/dashboard.py:234-241`）无金融字段；`InsightsTab.vue:277-365` 仅渲染实物 retention_rate + `physicalOnly` badge（:283）。
- **结论**：金融 calc 改年化 + `InsightsResponse` 加金融字段 + `InsightsTab` 加金融卡片（复用已 wired 的 store/api）。

#### A6（报告 PDF/图片导出）— greenfield，html2canvas 已装
- `AIReportPage.vue` 渲染结构化 Vue 组件（score ring SVG + indicator cards，CSS bars，无 ECharts），用 CSS 变量。
- 现有导出 = 仅 raw `.md` 源下载（`ReportMarkdownPreview.vue:67-75`，key `aiReport.downloadReport`）。**无 PDF/图片按钮**。
- `html2canvas@^1.4.1` **已是依赖**（`package.json:28`）；先例 `utils/shareImage.ts`（`generateAssetCard`/`generateSummaryCard`：off-screen DOM + `html2canvas({scale:2, backgroundColor:null})` → png blob + `downloadImage` helper）。
- 决策：**仅图片导出**（client-side html2canvas，镜像 shareImage.ts）。
- **caveat**：html2canvas 对 CSS `var()`/`oklch`/gradient 支持差——页面用 CSS 变量重度，需 themed snapshot 容器（硬编码颜色，仿 shareImage.ts）。
- **结论**：AIReportPage 加"导出图片"按钮 + 抽 `generateReportImage()` util（html2canvas）+ i18n。

### Key Technical Decisions (KTDs)

#### KTD-1：W6b 仅文档标注，不动代码
W6b 全链路已实现（见侦察结论）。本 plan 仅在 spec §3 表格 + p0-design §11 + 本 plan DoD 标注"已实现（侦察确认）"，不改任何源码、不加 commit（或仅 1 个 docs commit）。

#### KTD-2：L7 后端 detail enrichment — GET /{id} 返回 linked asset name + current_value
**决策**：不新增端点，扩展 `GET /liabilities/{id}` 的 `LiabilityResponse`（或新增 `linked_asset_summary` 嵌套对象）返回 linked asset 的 `name` + `current_value`（str 序列化，SnowflakeBase）。service `get_liability`（或 detail 路由）join 解析 `linked_asset` relationship（已存在）。
- **不**在列表端点 enrich（N+1 风险），仅 detail 端点。
- 前端 `Liability` type 加 `linked_asset?: { name: string; current_value: string }`。
- detail 卡显示"抵押物现值 ¥X vs 剩余贷款 ¥Y（覆盖率 Z%）"。

#### KTD-3：L7 form picker — Vant Picker 选 family assets
**决策**：`LiabilityForm.vue` 加"关联资产（抵押物）"可选字段。拉取 family assets 列表（已有 `/assets` 端点），用 Vant `<van-field readonly is-link>` + `<van-popup>` + `<van-picker>` 选 asset。`FormState` + `onSubmit` payload 加 `linked_asset_id`（nullable）。create/update schema 已支持。
- 可选字段（不强制）；选"无"清空。

#### KTD-4：D8 金融年化收益率公式
**决策**：金融资产 `compute_return_rate`（或新 `compute_annualized_return`）改年化：
```
rate = (current_value - purchase_price) / purchase_price × (365 / holding_days) × 100
holding_days = (today - purchase_date).days，purchase_date 缺失或 holding_days==0 → None
```
- **不动实物** `get_retention_rate`（保值率语义不同，保持 current/bought）。
- 金融 calc 独立函数（不改 `compute_return_rate` 签名以免影响其他调用方，或新加 `compute_annualized_return` 调用，`get_investment_returns` 改调新函数）。
- 侦察 `compute_return_rate` 调用方：仅 `get_investment_returns`（dashboard.py:352）——grep 确认无其他调用方后可原地改。

#### KTD-5：D8 InsightsResponse 加金融字段 + InsightsTab 加卡片
**决策**：
- `InsightsResponse`（`schemas/dashboard.py:234-241`）加 `investment_returns: InvestmentReturnSummary | None`（含年化收益率 + 资产数 + 说明）。
- `get_insights`（`services/dashboard.py:1023-1032`）调 `get_investment_returns` 填入。
- `InsightsTab.vue`（实物 retention 卡片后）加金融卡片，复用已 wired 的 `investmentReturns` store（或改从 `insights` response 取——决策：**从 `insights` response 取**，统一 insights 数据源，废弃独立 `/dashboard/investment-returns` 路由的消费？保留路由不删，避免破坏 API 契约，仅前端改从 insights 取）。
- 物理卡片 `physicalOnly` badge 调整：现在两卡片分别标"实物保值率"/"金融年化收益率"。

#### KTD-6：A6 仅图片导出，html2canvas themed snapshot 容器
**决策**：
- `AIReportPage.vue` 加"导出图片"按钮（顶部 actions）。
- 抽 `utils/reportImage.ts`（或扩展 `shareImage.ts`）`generateReportImage(reportEl)`：克隆 reportEl 到 off-screen 容器，**硬编码主题颜色**（深/浅色分支，仿 shareImage.ts 的 hardcoded color 模式），`html2canvas({scale:2, backgroundColor:'#fff'})` → png blob → `downloadImage`。
- i18n：`aiReport.exportImage` = "导出图片" / "Export Image"；loading toast（showLoadingToast）。
- **不**加 jspdf、**不**做服务端 PDF（KTD 决策）。
- caveat 处理：html2canvas 不捕获 CSS var()——snapshot 容器内联样式硬编码颜色（背景/文字/卡片背景）。

### Sequencing（按依赖 + effort 排序）

**第一批（trivial，无依赖）**：W6b（文档标注）
**第二批（small-medium，跨层后端+前端）**：L7（后端 enrich + form picker + detail 卡）
**第三批（small-medium，跨层后端+前端）**：D8（后端 calc + schema + insights + 前端卡片）
**第四批（small，纯前端）**：A6（按钮 + util + i18n）

4 项。L7/D8 跨层可串行（共享 dashboard/liability 上下文不冲突）；A6 独立前端。

---

## Implementation Units

### 任务表（4 项）

| ID | 任务 | 改动点 | Effort | 依赖 |
|----|------|--------|--------|------|
| W6b | 文档标注已实现 | spec §3 + p0-design §11 + 本 plan DoD | trivial | 无 |
| L7 | 抵押物现值 vs 剩余贷款联动 | 后端 detail enrich（KTD-2）+ LiabilityForm picker（KTD-3）+ LiabilityDetailPage 对比卡 | small-medium | 无 |
| D8 | 保值率拆实物/金融（金融年化） | 后端 `compute_annualized_return`（KTD-4）+ InsightsResponse 字段 + get_insights 填充（KTD-5）+ InsightsTab 金融卡片 | small-medium | 无 |
| A6 | 报告图片导出 | AIReportPage 按钮 + utils/reportImage.ts（KTD-6）+ i18n | small | 无 |

---

## Verification Contract

### 测试基线
- 前端：`pnpm typecheck` + `pnpm test:run`（touched files scope）+ `pnpm lint`。
- 后端：`uv run pytest tests/backend/test_liabilities.py tests/backend/test_dashboard.py`（L7/D8 scope）+ `uv run ruff check` + `uv run mypy`。

### grep 门槛
- L7 后：`LiabilityForm.vue` 含 `linked_asset_id`；`LiabilityDetailPage.vue` 含"覆盖率"/抵押物对比。
- D8 后：`compute_annualized_return` 存在；`InsightsResponse` 含 `investment_returns`；`InsightsTab.vue` 含金融卡片。
- A6 后：`AIReportPage.vue` 含"导出图片"按钮 + `reportImage.ts` 存在。

### 手动端到端
- L7：编辑负债选关联资产 → 详情页显示"抵押物现值 vs 剩余贷款（覆盖率）"。
- D8：有金融资产时 InsightsTab 显示金融年化收益率卡片；持有天数不足时 None 不报错。
- A6：报告页点"导出图片"→ 下载 PNG，图片含 score ring + indicator cards，颜色正确（非透明/非乱码）。

---

## Definition of Done

- [x] W6b 文档标注完成（spec §3 + p0-design §11 + 本 plan）。侦察确认全链路已实现（realize_wish 双向 FK + WishDetailPage.vue:53-60 回链 + i18n/tests）。
- [x] L7：后端 LiabilityDetailResponse 子类 enrich（linked_asset name+current_value，避免 list N+1）；LiabilityForm van-picker 资产选择器；LiabilityDetailPage 对比卡（覆盖率% + 色码）。7 i18n keys ×2 locale。backend test_liabilities 11 passed（+2）。
- [x] D8：compute_annualized_return（365/holding_days，compute_return_rate 保留因 5 其他调用方）；InsightsResponse 加 InvestmentReturnSummary；get_insights 填充；InsightsTab 金融年化卡片（rate null 显"持有天数不足"）。4 新 test，test_dashboard 41 passed（+4）。
- [x] A6：AIReportPage 导出图片按钮 + utils/reportImage.ts（html2canvas + getComputedStyle walk 内联 var()，比硬编码 palette 稳）+ 4 i18n keys ×2 locale。
- [x] i18n 完整（L7 抵押物/覆盖率、D8 金融年化/持有天数不足、A6 导出图片，zh+en）。
- [x] `pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox.test.ts TDZ suite failure（968 tests 本身全过，基线一致）；`uv run pytest tests/backend/` 1241 passed/0 failed/1 skipped（exit 0）；`ruff`/`mypy` 无新增错误（预存错误 stash 验证一致）。
- [x] 无 fake completion：无 test.skip/.only、无 TODO 占位、无未实现分支。

---

## Deferred / Open Questions

- **B1 推迟**：spec §11"需产品决策"，8 fork 未决（记账实体类型/真实资金 vs 星币兑换/谁出资/是否进 dashboard/触发点 mark_complete-vs-approve/粒度 family-vs-template-vs-child/可逆性 clawback/幂等）。单独走产品决策流程后再起 B1 plan。
- **A6 PDF**：本批仅图片；PDF（jspdf 多页 / 服务端 playwright）留后续。
- **D8 自定义区间收益率**：本批年化；若需用户选起止日期区间收益，需 AssetValuation 历史数据，留后续。
- **L7 列表端点 enrich**：仅 detail enrich，列表不 enrich（N+1）；若列表需显示抵押物概览，留后续。

---

## 依赖与后续

- **前置**：P0/P1/P2 已完成（数据基础 + finance hub + 合规）。
- **解锁**：B1 产品决策落地后可起 B1 plan。
