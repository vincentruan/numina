# P1 批次（除 N1）— Implementation Plan

> **状态**：draft，待实现
> **日期**：2026-07-21
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md)（§3 需求总表 P1 项）
> **范围**：P1 批 13 项中除 N1（单独成计划，见 [2026-07-21-p1-n1-finance-hub-plan.md](./2026-07-21-p1-n1-finance-hub-plan.md)）外的 12 项
> **来源**：spec §2「P1 批（13 项）」+ §5 待办「[ ] P1 批次」

---

## Goal Capsule

**一句话**：完成 P1 批 12 项业务触点——Dashboard 清理与加载态（D1/D3/D4/D5/D6/D7）、负债还款增强（L3/L4/L5）、AI 死桩清理与管线统一（A2/A3）、Baby 日历提示（B4）、设置页 KeepAlive 与本孩子 pending 数（F3/F7）。

**为什么**：P0 已交付增量价值（各触点闭环本地循环），P1 补齐体验一致性与信息流连贯性（spec §2）。其中 D5/D6 是删死代码降基线噪音，D3/D4 是 dashboard 信息密度增强，A3 是渲染管线收敛。

**完成标准**：12 项逐项落地，每项独立 commit + 验证；`pnpm typecheck` + `pnpm test:run` + `uv run pytest` 不新增失败。

---

## Product Contract

### Scope Boundaries
- **做**：12 项 P1（见下任务表）。
- **不做**：N1（单独 plan）；P2/P3（spec §11 推迟）；D3 的 `/finance?tab=` query 消费（留待 D3 实现期与 N1 协调，见各任务注）。
- **跨层**：D4 需后端 schema + TS type + 前端三处协调；其余 11 项纯前端。

---

## Planning Contract

### Key Technical Decisions (KTDs)

#### KTD-1：D3 下钻目标用现有顶级路由，不强依赖 N1 的 `/finance?tab=`
**决策**：D3 NetWorthCard 净资产/总负债可点 → 下钻 `/assets`（净资产/总资产）与 `/liabilities`（总负债）。若 N1 已落地 `/finance`，则下钻 `/finance?tab=assets|liabilities` 并由 finance 页消费 query（N1 plan Deferred 项）。

**理由**：recon 确认 `/finance` 路由当前不存在，真实路由是 `/liabilities`、`/assets`。D3 不应被 N1 阻塞——先指向现有路由，N1 落地后再升级到 `/finance?tab=`。

**实现期分支**：若 N1 先于 D3 完成 → 用 `/finance?tab=`；若 D3 先于 N1 → 用 `/assets`/`/liabilities`。

#### KTD-2：D4 后端复用已算的绝对 delta，不新建计算逻辑
**决策**：D4 后端在 `dashboard.py:121` 已计算 `current_net - snapshot_net`（绝对 delta）但丢弃。D4 改为：在 `OverviewResponse` schema 加 `month_over_month_change_amount` 字段，把已算的 delta 序列化出来，前端 `DashboardOverview` type + `NetWorthCard` 同步加字段渲染 `+¥X`。

**理由**：recon 确认数据已算，只需序列化，非"造数据"。改动面：schema + service return + TS type + 前端 prop/template。

#### KTD-3：L3 月还总额 = sum(monthly_payment)，null fallback 到 remaining×rate/100/12
**决策**：L3 banner "本月待还总额" = `liabilityStore.liabilities.reduce((s,l) => s + Number(l.monthly_payment ?? monthlyInterest(l)), 0)`，沿用 `LiabilityStrategyCard.vue:18-21` 的 fallback。

**理由**：`monthly_payment` 对 min-payment 信用卡可能为 null，fallback 保证非零。语义=本金月供（非含利息），与 L1/L2 的月供口径一致。

#### KTD-4：L4 在详情页对话框补快捷按钮行（含一次性还清），列表页已有不重做
**决策**：recon 确认列表页对话框已有 25%/50%/100%（`payFull`）快捷按钮（`LiabilityListPage.vue:136-143`）。L4 只在**详情页**对话框（`LiabilityDetailPage.vue:96-115`，当前无快捷按钮）补同样的 `pay-quick-btns` 行 + "一次性还清"按钮（填 `remaining_amount` 后提交）。

**理由**：避免列表页重复造轮子；详情页是真正的缺口。"一次性还清"语义=一键填满 `remaining_amount` 并提交（绕过手动输入，但保留确认步骤防误操作）。

#### KTD-5：L5 走 trivial 路径——重命名 prop + 标注，不加持久化字段
**决策**：L5 `PaymentCountdown` 当前已从 `start_date.day` 推导"下次还款日"（`getNextPaymentDate`），**行为正确**，只是 prop 命名 `startDate` 误导。L5 改为：重命名 prop `startDate`→`nextPaymentDate`（语义化）+ 在 UI 标注"下次还款日"文案。**不**新增后端 `next_payment_date` 持久化字段（那是 medium 改动，且现有推导对等额本息已正确）。

**理由**：recon 确认行为本身无误，spec 的"语义修正"主要指命名/展示误导。加持久化字段是 P3 级增强，不在 P1 范围。

#### KTD-6：A3 删 legacy + narrative 分支前，先确认后端不再吐 legacy shape
**决策**：A3 删除 `isLegacyFormat`（`AIReportPage.vue:374-383` + `:152-242` 模板）+ `isNarrativeFormat`（`:385-389` + `:136-150`），统一到 indicators 管线。**前置**：确认 `server/apps/agent/services/health_report.py`（legacy shape 来源）已不在活跃路径，被 `asset_report_middleware.py:parse_report_json`（indicators）取代。

**理由**：若后端仍可能吐 legacy shape，删前端分支会导致旧报告渲染空白。需先验证后端，再删前端。保留 `hasMarkdownFallback`（`:243-247`）作为弹性兜底。

#### KTD-7：B4 走 trivial 路径——加提示文案，不做真实聚合日历
**决策**：B4 "全部"日历模式当前静默显示第一个孩子数据（`BabyPage.vue:851` `// 全部视图时取第一个孩子`）。L5 改为：在 `ChildCalendar` header 加提示文案（如"当前展示：{name}"），明示是单孩子视图而非家庭聚合。**不**做真实家庭聚合日历（需后端 API 改动，small-large，留 P2）。

**理由**：spec §3 B4 原文是"提示展示哪个孩子或聚合视图"——提示即可满足，聚合是可选增强。

#### KTD-8：F7 双改——defineOptions name + cachedTabs
**决策**：F7 `FamilyPage.vue` 缺 `defineOptions({ name: 'Family' })`，光加 `cachedTabs` 不匹配（KeepAlive 按组件 name 匹配，非路由 name）。两处都要改：加 `defineOptions` + `cachedTabs` 数组加 `'Family'`。

**理由**：recon 确认这是隐性陷阱，`SettingsPage.vue:228` 已有正确范例可镜像。

---

### Sequencing（按依赖 + effort 排序）

**第一批（trivial，无依赖，可并行）**：D1、D5、D6、A2、B4、F3、F7、L3
**第二批（small，依赖少）**：D7、L4、L5、A3
**第三批（small-medium，有跨层或依赖）**：D4（后端+前端）、D3（依赖 N1 或用现有路由，KTD-1）

D3 与 N1 的顺序：若 N1 先完成，D3 用 `/finance?tab=`；否则用 `/assets`/`/liabilities`（KTD-1）。

---

## Implementation Units

### 任务表（12 项）

| ID | 任务 | 改动点（file:line） | Effort | 依赖 |
|----|------|---------------------|--------|------|
| D1 | Dashboard 渲染 PendingApprovalsSection | `DashboardPage.vue`（import + render，fetch 已在 `:607`） | trivial | 无 |
| D5 | 删 /stats 死页 | 删 `DataStatsPage.vue` + `router/index.ts:301-305` | trivial | 无 |
| D6 | 删 2 孤儿组件 | 删 `AlertCards.vue` + `UpcomingPaymentsCard.vue`（0 引用确认） | trivial | 无 |
| A2 | 删 AIHub 上传死桩 | 删 `AIHubPage.vue:303-304,377-401,435-439`（InputBox 自管附件） | trivial | 无 |
| B4 | Baby "全部"日历加提示 | `ChildCalendar.vue` header + `BabyPage.vue` 传当前孩子名（KTD-7） | trivial | 无 |
| F3 | 子卡 pending 数改本孩子 | `FamilyPage.vue:125-134,407-418`（改 per-child computed，数据已拉） | trivial | 无 |
| F7 | Family 页 KeepAlive | `FamilyPage.vue` 加 `defineOptions({name:'Family'})` + `MainLayout.vue:28-36` cachedTabs 加 `'Family'`（KTD-8） | trivial | 无 |
| L3 | 负债列表月还 banner | `LiabilityListPage.vue` 加 computed + banner（KTD-3，沿用 `LiabilityStrategyCard` fallback） | trivial | 无 |
| D7 | Dashboard 加载态修正 | `DashboardPage.vue:5,8,137` + store `assetListLoading` flag 解耦 loading/empty | small | 无 |
| L4 | 详情页一次性还清按钮 | `LiabilityDetailPage.vue:96-115` 加 `pay-quick-btns` 行（KTD-4） | small | 无 |
| L5 | PaymentCountdown 语义修正 | `PaymentCountdown.vue` prop 重命名 + UI 标注（KTD-5，不加后端字段） | trivial | 无 |
| A3 | AIReport 统一渲染管线 | 删 `AIReportPage.vue` legacy+narrative 分支（KTD-6，前置确认 `health_report.py` 非活跃） | small | 后端验证 |
| D4 | 环比加绝对金额 | 后端 `schemas/dashboard.py` + `dashboard.py:121` 序列化 delta + `types/index.ts` + `NetWorthCard.vue`（KTD-2） | small-medium | 后端+前端协调 |
| D3 | NetWorthCard 下钻 | `NetWorthCard.vue:28-42` 加 @click（KTD-1，目标 `/assets`/`/liabilities` 或 `/finance?tab=`） | small | N1（可选） |

> 12 项 + D3/D4 共 14 行（D3/D4 属 P1 但 recon 单列）；实际 P1 项数 13（含 N1），本 plan 覆盖除 N1 外 12 项 + D3/D4 是其中两项。

---

### 各任务详细验收点

**D1**：`DashboardPage.vue` import `PendingApprovalsSection` + 模板渲染（owner gate）；组件自 gate 非空列表。验证：owner 有待审批时 dashboard 可见。

**D5**：`/stats` 路由 404；`DataStatsPage.vue` 删除；无 dangling import。验证：grep `DataStatsPage` = 0（除 git 历史）。

**D6**：`AlertCards.vue`/`UpcomingPaymentsCard.vue` 删除；grep 确认 0 引用。注意：`DashboardPage.vue:314,611` 的 `upcomingPayments` 数据流（喂 `SmartRemindersCard`）**不触碰**。

**A2**：`AIHubPage.vue` 删 `fileInputRef`/`photoInputRef`/`triggerFileUpload`/`triggerPhotoUpload`/`handleFileSelect`/`handlePhotoSelect`/`onInputAction` + orphan i18n key。验证：grep `triggerFileUpload` = 0；InputBox 附件功能不受影响。

**B4**：`ChildCalendar.vue` header 显示"当前展示：{name}"（全部模式下）；非全部模式正常。验证：全部模式不再静默。

**F3**：`FamilyPage.vue` 两个 pending cell 绑 `childPendingChores[child.id]`/`childPendingWishes[child.id]`（镜像 `childWishCounts` 模式）。验证：每孩子卡显示本孩子数。

**F7**：`FamilyPage.vue` 加 `defineOptions({name:'Family'})`；`cachedTabs` 加 `'Family'`。验证：离开 `/family` 返回不重新 fetch（KeepAlive 生效）。

**L3**：`LiabilityListPage.vue` 加 `totalMonthlyPayment` computed + banner。验证：月还总额 = sum(monthly_payment)，与各负债月供一致。

**D7**：`DashboardPage.vue:137` `van-empty` 加 loading gate（`assetListLoading`）；解耦首屏 skeleton 与 empty。验证：分页加载中不闪现"无资产"。

**L4**：`LiabilityDetailPage.vue` 对话框加 `pay-quick-btns`（25%/50%/100%）+ 一次性还清（填 `remaining_amount` 提交）。验证：详情页可快捷还款。

**L5**：`PaymentCountdown.vue` prop `startDate`→`nextPaymentDate`；`LiabilityDetailPage.vue:29` 同步；UI 标注"下次还款日"。验证：倒计时行为不变，命名/文案正确。

**A3**：前置——确认 `health_report.py` 非活跃路径（grep 调用点；若被 `asset_report_middleware` 取代则安全）。删 `AIReportPage.vue` legacy+narrative 分支 + `ReportCard` import + `SECTION_LABELS`（若 narrative 删后无用）；统一 score 渲染/alloc bar/DOMPurify config。保留 `hasMarkdownFallback`。验证：现有 indicators 报告渲染正常；旧 legacy 报告走 markdown fallback。

**D4**：后端 `OverviewResponse` 加 `month_over_month_change_amount`（`dashboard.py:121` 已算 delta，序列化即可）；`types/index.ts:136-143` 加字段；`NetWorthCard.vue` prop + `changeText` 渲染 `+¥X`。验证：环比显示百分比 + 绝对金额。

**D3**：`NetWorthCard.vue:28-42` 净资产/总负债 `.ov-detail-item` 加 `@click` router.push（KTD-1 目标）+ 视觉 affordance（cursor/chevron）+ i18n aria-label。验证：可点击下钻。

---

## Verification Contract

### 测试基线
- 前端：`pnpm typecheck` + `pnpm test:run` + `pnpm lint`（scope 到 touched files）。
- 后端（仅 D4）：`uv run pytest apps/backend/tests/`（scope dashboard schema/service）+ `uv run ruff check` + `uv run mypy`。

### grep 门槛（删除类任务）
- D5 后：`grep -rn "DataStatsPage" frontend/apps/main/src` = 0。
- D6 后：`grep -rn "AlertCards\|UpcomingPaymentsCard" frontend/apps/main/src` = 0。
- A2 后：`grep -rn "triggerFileUpload\|onInputAction" frontend/apps/main/src` = 0。
- A3 后：`grep -n "isLegacyFormat\|isNarrativeFormat" frontend/apps/main/src/pages/AIReportPage.vue` = 0。

### 手动端到端
- D1：owner 待审批可见。
- D3：净资产/负债卡可点下钻。
- D4：环比百分比 + 绝对金额。
- L3/L4：负债列表月还 banner + 详情页一次性还清。
- F7：Family 页返回不重载。

---

## Definition of Done

- [ ] 12 项全部完成，每项独立 commit、独立验证通过。
- [ ] 删除类（D5/D6/A2/A3 legacy）：grep 门槛 = 0。
- [ ] D4 后端 schema + 前端 type 同步；环比显示绝对金额。
- [ ] D3 下钻可用（目标路由依 KTD-1）。
- [ ] i18n 完整（所有新文案 zh-CN + en-US，无硬编码中文）。
- [ ] `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 不新增失败。
- [ ] `uv run pytest apps/backend/tests/`（D4 scope）不新增失败。
- [ ] 无 fake completion：无 `test.skip`/`.only`、无 TODO 占位、无未实现分支。

---

## Deferred / Open Questions

- **D3 与 N1 协调**：D3 下钻目标若用 `/finance?tab=`，需 N1 的 finance 页消费 query 自动切 tab（N1 plan Deferred 项）。实现期定顺序。
- **L5 持久化 `next_payment_date`**：KTD-5 走 trivial 命名路径；若后续要支持非等额本息的自定义还款日，需后端字段（P3 级）。
- **B4 真实聚合日历**：KTD-7 走提示路径；真实家庭聚合需后端 `getFamilyChildCalendar` 改动（P2 级）。
- **A3 后端 `health_report.py` 处置**：若确认非活跃，是否一并删除后端 legacy 代码？留待 A3 实现期决定（本 plan 只删前端分支）。
- **F7 stale data**：KeepAlive 后返回 `/family` 不重新 fetch，可能显示旧数据。若需新鲜数据，加 `onActivated` re-fetch（超出 P1 最小范围，默认不做）。
- **L3 月还 util 抽公共**：L3 与 N1 U2 都用 `monthlyInterest` fallback，可抽 `utils/liability.ts` 公共函数。实现期若两项同批做则抽取，否则各自内联。

---

## 现状锚点（recon 证据汇总）

| 项 | file:line | 现状 | Effort |
|----|-----------|------|--------|
| D1 | `DashboardPage.vue:607`(fetch) / `:292-299`(import 缺) | fetch 已接，未渲染 | trivial |
| D3 | `NetWorthCard.vue:28-42`(无 @click) | 静态展示，无下钻 | small |
| D4 | `dashboard.py:121`(delta 已算丢弃) / `NetWorthCard.vue:23-25` | 仅百分比，绝对值未序列化 | small-medium |
| D5 | `router/index.ts:301-305` / `DataStatsPage.vue:62`(recentAssetsCount=ref(0)) | 死页，recentAssetsCount 永远 0 | trivial |
| D6 | `AlertCards.vue` / `UpcomingPaymentsCard.vue` | 0 引用确认 | trivial |
| D7 | `DashboardPage.vue:5,8,137` | loading/empty 经 `!asset_count` falsy 混淆 | small |
| L3 | `LiabilityListPage.vue:45-66`(banner 存在但无月还) | 无月还总额 | trivial |
| L4 | `LiabilityListPage.vue:136-143`(有快捷) / `LiabilityDetailPage.vue:96-115`(无) | 列表页有，详情页缺 | small |
| L5 | `PaymentCountdown.vue:21`(startDate prop) | 行为正确，命名误导 | trivial |
| A2 | `AIHubPage.vue:303-304,377-401,435-439` | 死桩，InputBox 自管附件 | trivial |
| A3 | `AIReportPage.vue:91-240,368-389` | 三格式分支，legacy 该删 | small |
| B4 | `BabyPage.vue:849-854`(//全部取第一个) / `ChildCalendar.vue:5-7` | 静默显示首孩子，无提示 | trivial |
| F3 | `FamilyPage.vue:125-134,407-418` | pending 用家庭级总数 | trivial |
| F7 | `FamilyPage.vue`(无 defineOptions) / `MainLayout.vue:28-36` | 缺 name，cachedTabs 无 Family | trivial |

---

## 依赖与后续

- **前置**：P0 已完成（W1/L1/L2 等数据基础就绪）。
- **与 N1 关系**：D3 可选依赖 N1（KTD-1）；L3 与 N1 U2 共享月还 util（Deferred）。
- **解锁**：P2（i18n 合规、a11y、币种统一）——P1 完成后可起 P2 计划。
