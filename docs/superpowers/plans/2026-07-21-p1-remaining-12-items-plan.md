# P1 批次（除 N1）— Implementation Plan

> **状态**：draft，待实现
> **日期**：2026-07-21
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md)（§3 需求总表 P1 项）
> **范围**：P1 批 15 项中除 N1（单独成计划，见 [2026-07-21-p1-n1-finance-hub-plan.md](./2026-07-21-p1-n1-finance-hub-plan.md)）外的 14 项
> **来源**：spec §2「P1 批（13 项）」+ §5 待办「[ ] P1 批次」

---

## Goal Capsule

**一句话**：完成 P1 批 14 项业务触点（spec P1 共 15 项，除 N1 单独成计划外）——Dashboard 清理与加载态（D1/D3/D4/D5/D6/D7）、负债还款增强（L3/L4/L5）、AI 死桩清理与管线统一（A2/A3）、Baby 日历提示（B4）、设置页 KeepAlive 与本孩子 pending 数（F3/F7）。

**为什么**：P0 已交付增量价值（各触点闭环本地循环），P1 补齐体验一致性与信息流连贯性（spec §2）。其中 D5/D6/A2 是删死代码降基线噪音（hygiene 轨），D3/D4/D7/A3/L3/L4 是信息密度与交互增强（决策链连贯轨），L5/B4/F3/F7 是语义修正与体验一致性。

**完成标准**：14 项逐项落地，每项独立 commit + 验证；`pnpm typecheck` + `pnpm test:run` + `uv run pytest` 不新增失败。

---

## Product Contract

### Scope Boundaries
- **做**：14 项 P1（spec P1 共 15 项除 N1，见下任务表）。
- **不做**：N1（单独 plan）；P2/P3（spec §11 推迟）；D3 的 `/finance?tab=` query 消费由 N1 落地（D3 须在 N1 后，KTD-1）。
- **跨层**：D4 需后端 schema + TS type + 前端三处协调；其余 13 项纯前端。

> 注：文件名为 `p1-remaining-12-items`，实际 14 项（spec P1 共 15 项含 N1）。文件名历史遗留，内容以 14 项为准。

---

## Planning Contract

### Key Technical Decisions (KTDs)

#### KTD-1：D3 下钻目标统一为 `/finance?tab=`，必须在 N1 之后实现
**决策**：D3 NetWorthCard 净资产/总负债可点 → 下钻 `/finance?tab=assets|liabilities`，由 N1 的 finance 页消费 query（N1 plan KTD-1/U3 已落地 `?tab=` 契约）。**D3 必须在 N1 之后实现**——与 N1 plan 的 prerequisite 表述对齐（N1 plan line 226："D3 应在 N1 之后实现，下钻目标 /finance?tab=liabilities，?tab= 契约已由 KTD-1/U3 落地"）。

**理由（review 修正，原 KTD-1 的"D3 可先于 N1 打 /assets"分支删除）**：若 D3 先于 N1 打 `/assets`/`/liabilities`，N1 落地后（nav 6→5，这些路由失 TabBar 入口）D3 下钻目标变成 finance hub 之外的裸 list，破坏决策链流，且需二次改动 re-point。两 sibling plan 对 D3 依赖此前表述冲突（本 plan "optional" vs N1 plan "prerequisite"）——统一为 prerequisite，消除跨计划不一致。

**映射**：净资产 → `/finance?tab=assets`；总负债 → `/finance?tab=liabilities`（详见 D3 验收点 a11y 修正）。

**若需 D3 不被 N1 阻塞**：显式接受 re-point 作为 deferred cost 记录到 Open Questions，而非在本 KTD 呈现等价分支。

#### KTD-2：D4 后端提取绝对 delta 为独立变量并序列化
**决策**：D4 后端在 `dashboard.py:121` 的 `mom_change = round((current_net - snapshot_net) / abs(snapshot_net) * 100, 2)` 中，`(current_net - snapshot_net)` 是百分比的子表达式，**从未作为独立值存在**（review 修正：原称"已算绝对 delta 但丢弃"不准确）。D4 改为：在 line 121 前提取 `month_over_month_change_amount = current_net - snapshot_net` 为独立变量，处理 `last_snapshot` 为 None 时的 null 语义，加入 `OverviewResponse` schema 序列化；前端 `DashboardOverview` type + `NetWorthCard` 同步加字段渲染 `+¥X`。

**理由**：改动面是"造数据出口"而非"序列化已有值"——schema + service 提取变量 + None 边界 + TS type + 前端 prop/template 四处同步。effort small-medium 的后端部分非零成本（原"序列化即可"低估）。

**D4 符号/零值/格式/展示位置（review P1 修正）**：符号沿用现有 `changeClass`（涨绿跌红）+ 绝对金额带正负号（如 `↑ 3.2% +¥1,200` / `↓ 1.1% -¥500`）；零值隐藏绝对金额只显百分比；格式用 `useCurrency`；展示位置在百分比同行右侧。

#### KTD-3：L3 月还总额 = sum(monthly_payment)，null fallback 到 remaining×rate/100/12
**决策**：L3 banner "本月待还总额" = `liabilityStore.liabilities.reduce((s,l) => s + Number(l.monthly_payment ?? monthlyInterest(l)), 0)`，沿用 `LiabilityStrategyCard.vue:18-21` 的 fallback。

**理由**：`monthly_payment` 对 min-payment 信用卡可能为 null，fallback 保证非零。语义=本金月供（非含利息），与 L1/L2 的月供口径一致。

#### KTD-4：L4 在详情页对话框补快捷按钮行（含一次性还清），列表页已有不重做
**决策**：recon 确认列表页对话框已有 25%/50%/100%（`payFull`）快捷按钮（`LiabilityListPage.vue:136-143`）。L4 只在**详情页**对话框（`LiabilityDetailPage.vue:96-115`，当前无快捷按钮）补同样的 `pay-quick-btns` 行 + "一次性还清"按钮。

**交互模型（review P1 修正，须定义）**：快捷按钮**仅填充 `paymentAmount`，不自动提交**——用户仍需点确认（沿用详情页 `before-close`→`onPaymentConfirm` 流程防误操作）。详情页对话框用 `before-close`（`onPaymentConfirm`）而非列表页的 `@confirm`，`setPayPercent` 设置 `paymentAmount` 后由 `onPaymentConfirm` 处理提交（与列表页 `setPayPercent` 仅填充语义一致）。"一次性还清"= 100% 按钮，填 `remaining_amount` 后待确认。

**理由**：避免列表页重复造轮子；详情页是真正的缺口。"一次性还清"语义=一键填满 `remaining_amount`（不绕过确认，防误操作）。

#### KTD-5：L5 走 trivial 路径——重命名 prop + 标注，不加持久化字段
**决策**：L5 `PaymentCountdown` 当前已从 `start_date.day` 推导"下次还款日"（`getNextPaymentDate`），**行为正确**（前提见下方验证），只是 prop 命名 `startDate` 误导。L5 改为：重命名 prop `startDate`→`nextPaymentDate`（语义化）+ 在 UI 标注"下次还款日"文案。**不**新增后端 `next_payment_date` 持久化字段（那是 medium 改动）。

**start_date 语义验证（review P2 修正，实现期须做）**：`getNextPaymentDate` 从 `start_date.day` 推导下次还款日，**只有当 `start_date` 的 day-of-month == 合同还款日时才正确**。实现期须确认 `liability.start_date` 的语义（是放款日还是首个还款日），并抽样检查现有数据中 `start_date.day` 是否与实际还款日一致。若一致，trivial 路径成立；**若不一致（start_date 是放款日，day 与账单日不同），L5 应升级为真实计算修正而非重命名**（否则重命名会把错误固化）。

**理由**：recon 确认行为本身无误（待 start_date 语义验证），spec 的"语义修正"主要指命名/展示误导。加持久化字段是 P3 级增强，不在 P1 范围。

#### KTD-6：A3 删 legacy + narrative 分支前，确认后端不再吐 legacy shape（已验证）
**决策**：A3 删除 `isLegacyFormat`（`AIReportPage.vue:374-383` + `:153-232` 模板，review 修正行号：原写 152-242 偏移）+ `isNarrativeFormat`（`:385-389` + `:137-150`），统一到 indicators 管线。`hasMarkdownFallback`（`:362-365`，elastic-fallback flag，**非格式分支**——review 修正：原 plan 把它混淆为格式分支）保留作为弹性兜底。

**health_report.py 非活跃已验证（review 修正：原 plan 现状锚点写既定事实、KTD-6/验收点又推实现期验证，表述矛盾——统一为已验证）**：验证子任务确认 `server/apps/agent/services/health_report.py` 的 `generate_health_report` **零调用**，`scheduler.py:97` 唯一引用已注释，`CLAUDE.md:166` 列为 legacy，被 `asset_report_middleware.py:parse_report_json`（`worker.py` 5 处调用）取代产 indicators 格式。实现期删除前再跑一次 `grep -rn "generate_health_report\|generate_monthly_reports" server/` 确认无新调用点即可。

**回退路径（review P1 修正，须明确）**：若实现期 grep 发现 `health_report.py` 有新调用点（如 scheduler 被重新启用），**保留 `isLegacyFormat` 分支不删**，仅删 `isNarrativeFormat`，避免旧报告渲染空白。A3 的 grep=0 门槛不可逆，删前确认。

#### KTD-7：B4 走 trivial 路径——加提示文案，不做真实聚合日历
**决策**：B4 "全部"日历模式当前静默显示第一个孩子数据（`BabyPage.vue:851` `// 全部视图时取第一个孩子`）。**B4 改为**（review 修正：原动作子句误写成"L5 改为"）：在 `ChildCalendar` header 加提示文案（如"当前展示：{name}"），明示是单孩子视图而非家庭聚合。**不**做真实家庭聚合日历（需后端 API 改动，留 P2）。

**spec §3 B4 原文确认（review P2 修正，须逐字引用确认 OR vs AND）**：实现期须引用 spec §3 B4 逐字原文，确认是"提示**或**聚合"（OR）还是"提示**与**聚合"（AND）。若是 OR，trivial 提示路径成立；若是 AND，B4 应升级或显式标部分实现。

**"全部" tab 名评估（review P2）**：即使 spec 是 OR，"全部" tab 名暗示聚合但只显一个孩子，提示文案可能读起来像道歉而非功能。实现期评估"全部" tab 名是否 P1 改（如改孩子名、或加多孩子 switcher）以避免设未满足期望。若保留"全部"，确保提示文案足够醒目。

**理由**：spec §3 B4 原文（待逐字确认）倾向"提示展示哪个孩子或聚合视图"——提示即可满足，聚合是可选增强。

#### KTD-8：F7 双改——defineOptions name + cachedTabs
**决策**：F7 `FamilyPage.vue` 缺 `defineOptions({ name: 'Family' })`，光加 `cachedTabs` 不匹配（KeepAlive 按组件 name 匹配，非路由 name）。两处都要改：加 `defineOptions` + `cachedTabs` 数组加 `'Family'`。

**理由**：recon 确认这是隐性陷阱，`SettingsPage.vue:228` 已有正确范例可镜像。

---

### Sequencing（按依赖 + effort 排序）

**第一批（trivial，无依赖，可并行）**：D1、D5、D6、A2、B4、F3、F7、L3
**第二批（small，依赖少）**：D7、L4、L5、A3
**第三批（small-medium，有跨层或依赖）**：D4（后端+前端）、D3（须在 N1 后，KTD-1）

三批合计 14 项（8+4+2）。D3 须在 N1 之后实现（KTD-1 已统一为 prerequisite，下钻 `/finance?tab=`）。

---

## Implementation Units

### 任务表（14 项，spec P1 共 15 项除 N1）

| ID | 任务 | 改动点（file:line） | Effort | 依赖 |
|----|------|---------------------|--------|------|
| D1 | Dashboard 渲染 PendingApprovalsSection | `DashboardPage.vue`（import PendingApprovalsSection + 模板渲染 owner gate；fetch 已在 `:607` 无需改） | trivial | 无 |
| D5 | 删 /stats 死页 | 删 `DataStatsPage.vue` + `router/index.ts:301-305` | trivial | 无 |
| D6 | 删 2 孤儿组件 | 删 `AlertCards.vue` + `UpcomingPaymentsCard.vue`（0 引用确认） | trivial | 无 |
| A2 | 删 AIHub 上传死桩 | 删 `AIHubPage.vue:303-304,377-401,435-439`（InputBox 自管附件） | trivial | 无 |
| B4 | Baby "全部"日历加提示 | `ChildCalendar.vue` header + `BabyPage.vue` 传当前孩子名（KTD-7） | trivial | 无 |
| F3 | 子卡 pending 数改本孩子 | `FamilyPage.vue:125-134,407-418`（改 per-child computed，数据已拉） | trivial | 无 |
| F7 | Family 页 KeepAlive | `FamilyPage.vue` 加 `defineOptions({name:'Family'})` + `MainLayout.vue:28-36` cachedTabs 加 `'Family'`（KTD-8） | trivial | 无 |
| L3 | 负债列表月还 banner | `LiabilityListPage.vue` 加 computed + banner（KTD-3，沿用 `LiabilityStrategyCard` fallback） | trivial | 无 |
| D7 | Dashboard 加载态修正 | `DashboardPage.vue:137` van-empty 加 loading gate，消费已有 `assetListLoading` flag（store 无需改，flag 已在 `dashboard.ts:38`） | small | 无 |
| L4 | 详情页一次性还清按钮 | `LiabilityDetailPage.vue:96-115` 加 `pay-quick-btns` 行（KTD-4，仅填充不自动提交，接 before-close 流程） | small | 无 |
| L5 | PaymentCountdown 语义修正 | `PaymentCountdown.vue` prop 重命名 + UI 标注（KTD-5，不加后端字段，前置验证 start_date 语义） | trivial | start_date 语义验证 |
| A3 | AIReport 统一渲染管线 | 删 `AIReportPage.vue` legacy+narrative 分支（KTD-6，`health_report.py` 非活跃已验证，删前再 grep） | small | 删前 grep 确认 |
| D4 | 环比加绝对金额 | 后端 `schemas/dashboard.py` + `dashboard.py:121` 提取 delta 独立变量 + `types/index.ts` + `NetWorthCard.vue`（KTD-2） | small-medium | 后端+前端协调 |
| D3 | NetWorthCard 下钻 | `NetWorthCard.vue:28-42` 加 router-link/role=button + a11y + i18n（KTD-1，目标 `/finance?tab=assets|liabilities`） | small | N1（prerequisite） |

> 14 项（spec P1 共 15 项含 N1，本 plan 覆盖除 N1 外全部）。D3/D4 已含在 14 项内，非额外单列。

---

### 各任务详细验收点

**D1**：`DashboardPage.vue` import `PendingApprovalsSection` + 模板渲染（owner gate）；组件自 gate 非空列表。**状态处理（review）**：明确空状态（无待审批时不渲染，组件自 gate 已覆盖）+ owner gate 交互态（非 owner 不渲染）。验证：owner 有待审批时 dashboard 可见；非 owner 不见；空列表不占位。

**D5**：`/stats` 路由 404；`DataStatsPage.vue` 删除；无 dangling import。验证：grep `DataStatsPage` = 0（除 git 历史）。

**D6**：`AlertCards.vue`/`UpcomingPaymentsCard.vue` 删除；grep 确认 0 引用。注意：`DashboardPage.vue:314,611` 的 `upcomingPayments` 数据流（喂 `SmartRemindersCard`）**不触碰**。

**A2**：`AIHubPage.vue` 删 `fileInputRef`/`photoInputRef`/`triggerFileUpload`/`triggerPhotoUpload`/`handleFileSelect`/`handlePhotoSelect`/`onInputAction` + orphan i18n key。验证：grep `triggerFileUpload` = 0；InputBox 附件功能不受影响。

**B4**：`ChildCalendar.vue` header 显示"当前展示：{name}"（全部模式下）；非全部模式正常。验证：全部模式不再静默。

**F3**：`FamilyPage.vue` 两个 pending cell 绑 `childPendingChores[child.id]`/`childPendingWishes[child.id]`（镜像 `childWishCounts` 模式）。**状态处理（review）**：加载态（数据未就绪显占位/—）+ `has-pending` class 语义（按本孩子数>0 而非家庭级）。验证：每孩子卡显示本孩子数；加载中不显 0。

**F7**：`FamilyPage.vue` 加 `defineOptions({name:'Family'})`；`cachedTabs` 加 `'Family'`。**陈旧信号（review）**：KeepAlive 后返回不 refetch 可能显旧 pending 数——评估是否加用户可见陈旧提示（如"数据可能非最新，下拉刷新"）或 `onActivated` refresh（超 P1 最小范围，默认不做但记录）。验证：离开 `/family` 返回不重新 fetch（KeepAlive 生效）。

**L3**：`LiabilityListPage.vue` 加 `totalMonthlyPayment` computed + banner。**状态处理（review）**：明确加载态（liabilities 加载中 banner 显骨架/占位）+ 零值（月还=0 时显 ¥0 或隐藏 banner）+ error 态（fetch 失败不静默显 0）。验证：月还总额 = sum(monthly_payment)（`Number()??0` 强转，过滤 `is_active`），与各负债月供一致。

**D7**：`DashboardPage.vue:137` `van-empty` 加 loading gate（消费已有 `assetListLoading`，store 无需改——flag 已在 `dashboard.ts:38`）；解耦 line 137 内层 asset-list empty 与 loading（line 5/8 顶层已有 `!loading` 守卫不混）。**范围修正（review）**：原写 `:5,8,137` 但 line 5/8 顶层已有 `loading` 守卫不混淆，真正缺陷在 137 内层 `van-empty` 无 loading gate——聚焦 137。**分页 onLoadMore（review）**：分页加载中（`assetListLoading=true`）时 `filteredByCategoryAssets` 暂空会闪现"无资产"，gate 消费 `assetListLoading` 显加载态。验证：分页加载中不闪现"无资产"。

**L4**：`LiabilityDetailPage.vue` 对话框加 `pay-quick-btns`（25%/50%/100%）+ 一次性还清。**交互模型（KTD-4）**：快捷按钮仅填充 `paymentAmount` 不自动提交，由 `before-close`→`onPaymentConfirm` 处理提交（防误操作）。验证：详情页可快捷还款；填充后仍需确认。

**L5**：`PaymentCountdown.vue` prop `startDate`→`nextPaymentDate`；`LiabilityDetailPage.vue:29` 同步；UI 标注"下次还款日"。**前置验证（KTD-5）**：确认 `liability.start_date` 语义（放款日 vs 首还款日），抽样 `start_date.day` == 实际还款日；不一致则升级为真实计算修正。**状态处理（review）**：非月度/不规则还款日的显示逻辑明确。验证：倒计时行为不变（前提 start_date 语义验证通过），命名/文案正确。

**A3**：删前再 `grep -rn "generate_health_report\|generate_monthly_reports" server/` 确认无新调用（`health_report.py` 非活跃已验证，KTD-6）。删 `AIReportPage.vue` legacy（`:153-232`）+ narrative（`:137-150`）分支 + `ReportCard` import + `SECTION_LABELS`（若 narrative 删后无用）；统一 score 渲染/alloc bar/DOMPurify config。保留 `hasMarkdownFallback`（`:362-365`，elastic-fallback flag 非格式分支）。**状态处理（review）**：删 legacy/narrative 后 markdown fallback 路径的交互态（点击预览、加载、错误）明确。**回退（KTD-6）**：若 grep 发现新调用，保留 `isLegacyFormat` 不删。验证：现有 indicators 报告渲染正常；旧 legacy 报告走 markdown fallback。

**D4**：后端 `OverviewResponse` 加 `month_over_month_change_amount`（`dashboard.py:121` 提取 `(current_net - snapshot_net)` 为独立变量，处理 `last_snapshot` None 时返回 null——非"序列化已算值"，KTD-2）；`types/index.ts:136-143` 加字段；`NetWorthCard.vue` prop + `changeText` 渲染。**符号/格式（KTD-2）**：`↑ 3.2% +¥1,200` / `↓ 1.1% -¥500`（`useCurrency` 格式，零值隐藏绝对金额只显百分比，展示在百分比同行右侧）。验证：环比显示百分比 + 绝对金额；`last_snapshot=None` 时 amount=None。

**D3**：`NetWorthCard.vue:28-42` 净资产/总负债 `.ov-detail-item` 加下钻。**a11y（review P1）**：用 `<router-link>` 包裹（自动 a11y）或 div 加 `role=button`+`tabindex=0`+`@keydown.enter`；**映射（KTD-1）**：净资产→`/finance?tab=assets`，总负债→`/finance?tab=liabilities`（N1 后）；视觉 affordance（cursor/chevron）+ i18n aria-label。验证：可点击下钻 + 键盘可达 + 映射正确。

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

- [ ] 14 项全部完成，每项独立 commit、独立验证通过。
- [ ] 删除类（D5/D6/A2/A3 legacy）：grep 门槛 = 0（A3 删前 grep 确认 `health_report.py` 无新调用，KTD-6 回退）。
- [ ] D4 后端提取 delta 独立变量 + 前端 type 同步；环比显示百分比 + 绝对金额（符号/零值/格式依 KTD-2）。
- [ ] D3 下钻可用 + a11y（router-link/键盘）+ 映射（净资产→assets/总负债→liabilities，N1 后 `/finance?tab=`）。
- [ ] D3 在 N1 之后实现（KTD-1 prerequisite）。
- [ ] L4 交互模型：快捷按钮仅填充不自动提交（KTD-4）。
- [ ] L5 前置：`start_date` 语义验证通过（KTD-5），否则升级为计算修正。
- [ ] i18n 完整（所有新文案 zh-CN + en-US，无硬编码中文）。
- [ ] `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 不新增失败。
- [ ] `uv run pytest apps/backend/tests/`（D4 scope）不新增失败。
- [ ] 无 fake completion：无 `test.skip`/`.only`、无 TODO 占位、无未实现分支。

---

## Deferred / Open Questions

- **D3 与 N1 协调**：D3 须在 N1 之后实现（KTD-1 已统一 prerequisite），下钻 `/finance?tab=assets|liabilities`，`?tab=` 契约由 N1 KTD-1/U3 落地。若需 D3 不被 N1 阻塞，显式接受 re-point 作为 deferred cost。
- **L5 持久化 `next_payment_date`**：KTD-5 走 trivial 命名路径（前提 `start_date` 语义验证通过）；若后续要支持非等额本息的自定义还款日，需后端字段（P3 级）。
- **B4 真实聚合日历**：KTD-7 走提示路径（前提 spec §3 B4 原文确认是 OR）；真实家庭聚合需后端 `getFamilyChildCalendar` 改动（P2 级）。"全部" tab 名是否 P1 改留待实现期评估。
- **A3 后端 `health_report.py` 处置**：已验证非活跃（KTD-6）；是否一并删除后端 legacy 代码留待 A3 实现期决定（本 plan 只删前端分支）。
- **F7 stale data**：KeepAlive 后返回 `/family` 不重新 fetch，可能显示旧数据。若需新鲜数据，加 `onActivated` re-fetch（超出 P1 最小范围，默认不做）。
- **L3 月还 util 抽公共**：L3 与 N1 U2 都用 `monthlyInterest` fallback，可抽 `utils/liability.ts` 公共函数。实现期若两项同批做则抽取，否则各自内联。

### From 2026-07-21 ce-doc-review（需产品判断，未自动应用）

- **[P2] 排除 N1 使批次对 spec §1 决策链目标贡献变薄**：spec §1 目标是决策链，N1 是最大贡献者但被排除。14 项里 D5/D6/A2/L5 是纯 hygiene（无用户价值），Goal 把 hygiene 打包进"体验一致性"夸大对决策链进展。product-lens（anchor 75）。**需产品判断**：Goal"为什么"是否拆两轨——(a) hygiene/死代码减少（D5/D6/A2/L5）降维护噪音；(b) 决策链连贯（D3/D4/A3/L3/L4）推进 spec §1？还是维持"体验一致性"统一框架？

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
