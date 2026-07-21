# N1 财务 hub 落地 — Implementation Plan

> **状态**：draft，待实现
> **日期**：2026-07-21
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../../specs/2026-07-19-family-finance-optimization-requirements.md)（决策 ②B + ⑥C + §域7 N1）
> **范围**：新建 `FinanceHubPage` + `/finance` 路由 + TabBar 6→5（合并资产/负债/心愿为单入口）
> **来源**：spec §2「P1 含 N1(财务 hub 落地) … 单独成子计划」、§5 待办「[ ] P1 批次（含 N1 财务 hub，单独子计划）」

---

## Goal Capsule

**一句话**：把资产/负债/心愿统一为 `/finance` 一个入口，首屏财务概览卡（净资产 + 月还 + 心愿进度 + 跨模块决策链提示）+ 三 sub-tab 下钻；owner TabBar 从 6 降到 5（assets 首次获得 tab 入口，此前仅 dashboard 可达）。

**为什么**：当前六个模块是六个独立工具而非一条财务决策链（spec §1）。N1 通过统一入口 + 概览首屏收敛实体管理，并在概览卡补一条 W5 式跨模块联动提示（高息负债延迟心愿），让 hub 不止是三个孤立数字，而是触及"决策链"语义。完整决策链流转（花销控制/财富增值阶段）仍靠 D3/AI 教练等后续 P1 项。N1 是 P1 里改动最大的单项，也是 D3 前置依赖。

**完成标准**：
- `/finance` 路由 + `FinanceHubPage.vue` 上线，首屏概览卡（净资产 + 月还 + 心愿进度 + W5 联动提示）+ 资产/负债/心愿三 tab。
- TabBar 统一入口：owner `dashboard / finance / ai / baby / settings` = 5（移除 wishes/liabilities，加 finance；assets 首获 tab 入口）；**非 owner 非对称**（KTD-4）保留 `wishes` 直达 tab = 5 项（减 liabilities 加 finance，保留 wishes）。
- 原有 `/assets`、`/liabilities`、`/wishes` 顶级路由**全部保留可达**（deep-link + 已有 cachedTabs 不破坏）。
- finance tab active 态覆盖三组路由（访问 `/assets`、`/liabilities`、`/wishes` 及其子路由时 TabBar finance 高亮）。
- i18n：新增 `nav.finance` key（zh-CN + en-US）。

---

## Product Contract

### Summary
P1 N1。新建财务 hub 页作为资产/负债/心愿的统一入口，TabBar 收敛入口数。不删任何现有页面，只重组导航 + 加聚合首屏。

### Scope Boundaries
- **做**：新建 `FinanceHubPage.vue` + `/finance` 路由；TabBar 合并入口；activeTab 映射扩展；i18n。
- **不做**：
  - 不迁移 `assets/*`、`liabilities/*`、`wishes/*` 子路由到 `/finance` 下（KTD-1，保留顶级，见下）。
  - 不做 D3（NetWorthCard 下钻）——那是独立 P1 项，依赖本 plan 的 `/finance` 路由存在。
  - 不做真实家庭聚合日历（那是 B4）。
  - 不改三组 list/detail/form 页内部实现。

---

## Planning Contract

### Key Technical Decisions (KTDs)

#### KTD-1：三组路由保留顶级，不迁入 `/finance` 子路由
**决策**：`/assets`、`/liabilities`、`/wishes` 及其子路由（new/edit/detail/sell）**保持现有顶级路径不变**。`/finance` 是新建的聚合页，三 sub-tab 通过 `router.push` 跳到对应顶级路由，而非嵌套 `children`。

**理由**：
1. **deep-link 不破坏**：外部书签 / 历史 URL 仍可用。
2. **`cachedTabs` name 匹配不破坏**：`MainLayout.vue:28-36` 用组件 `name` 做 KeepAlive include，`AssetList`/`WishList`/`LiabilityList` 的 name 匹配依赖路由不变。
3. **改动面最小**：迁子路由要改 router + 所有 `router.push('/assets/...')` 调用点 + 测试，风险远大于收益。
4. **sub-tab 即"快捷跳转"**：finance 页的三 tab 本质是三个入口按钮 + 概览首屏，不是真正的嵌套视图切换（避免 `<router-view>` 嵌套 + KeepAlive 复杂度）。

**代价**：从 `/assets` 深层页返回时不会自动回到 `/finance?tab=assets`，而是回到 `/assets` list。可接受——list 页本身就是 finance 的子 tab 目标。

**`?tab=` 契约（D3 联动，review 修正）**：finance 页 onMounted 读 `route.query.tab`（`assets`|`liabilities`|`wishes`）并 `setActiveTab`。即使 D3 后落地，N1 交付时即 honor `?tab=`，消除 D3 下钻（`/finance?tab=liabilities`）与 U6 入口（`/finance?tab=assets`）的耦合空悬。若 `?tab=` 非法或缺失，默认首个 sub-tab。

#### KTD-2：finance tab active 映射覆盖三组路由
**决策**：`AppTabBar.vue` 的 `activeTab` computed 扩展——`/assets`、`/liabilities`、`/wishes` 及其所有子路径前缀均映射到 `finance`。

**匹配策略（review 修正，避免漏深层子路由）**：用**路径前缀匹配** `route.path.startsWith('/assets') || startsWith('/liabilities') || startsWith('/wishes')`，覆盖三组全部子路由（list/new/:id/:id/edit/:id/sell 等，含 params）。不逐条枚举路由名，避免遗漏 `:id/edit`、`:id/sell` 变体导致深层页 finance tab 失高亮。`/liabilities?focus=liability_strategy` 的 query 不影响 path 前缀匹配，active 仍归 finance。

**行为变更（review 提示，需 DoD 验证）**：当前 `/assets*` 路径在 `activeTab` 无分支，fallthrough 到 `dashboard` 高亮；本 KTD 后改为高亮 `finance`。这是有意的导航态修正（用户在资产页时高亮 finance 而非 dashboard），DoD 须验证此变更。

**理由**：用户在三组任意页面时，TabBar 应高亮 finance（而非 dashboard），否则导航态失真。

#### KTD-3：概览卡数据复用现有 dashboard overview，不新建后端端点
**决策**：`FinanceHubPage` 首屏概览卡（净资产 + 月还 + 心愿进度）的数据分两类（review 修正：原"复用 overview"措辞掩盖了 2/4 字段是新建客户端 computed）：

**A. 复用字段（直接读 `dashboardStore.overview`，`DashboardOverview` 已含）**：
- 净资产（`net_worth`）/ 总负债（`total_liabilities`）。

**B. 新建客户端 computed（`DashboardOverview` 无此字段，recon 深化点 3）**：
- **月还总额**：sum 各 liability `monthly_payment`。**准确性修正（review P1）**：`monthly_payment` 为 null 时，fallback `remaining × rate/100/12` 是**纯利息估算不含本金**（`LiabilityStrategyCard.vue:18-21` 的 `monthlyInterest`），作首屏 headline「月还总额」会误导（用户当作真实月供，而等额本息真实月供 = 本金+利息，可能远高）。修正：(1) 优先 sum 非空 `monthly_payment` 的负债；(2) 对 null 项在 UI 标注「估算」或改用 T4 已实现的 `calc_amortization` 算真实月供；(3) 或只统计有 `monthly_payment` 的负债并注明覆盖率。**不把利息估算当月供 headline**。
- **心愿进度**：`useAffordBar` 是 **per-wish** composable（接单个 wish，`useAffordBar.ts:17`），无法直接复用做聚合。**聚合格式（review P1，须实现期定）**：采用组合进度条 = `sum(saved_amount) / sum(expected_price)`，附「N 个心愿」副标题。若需更细，备选堆叠计数「X 达成 / Y 进行中 / Z 暂停」。`useAffordBar` 仅在改用迷你心愿列表方案时有用，组合进度条方案直接从 `wishStore.wishes` 算。

**数据强转与过滤（review P2）**：`monthly_payment`/`saved_amount`/`expected_price` 是 string（SnowflakeBase money-as-str），computed 内须 `Number(x) ?? 0` 强转（沿用 `LiabilityStrategyCard` 模式），否则拼串或 NaN。月还 computed 须过滤 `is_active === true`（`fetchLiabilities` 默认含 inactive，不过滤会虚高）。

**后端聚合端点 build-vs-use（review 提示）**：客户端跨三 store 聚合的代价（请求数、新鲜度对齐、月还估算精度）已显式接受；若实现期发现一致性/精度问题，再评估后端一次查询返回四字段的端点。当前默认客户端聚合。

**理由**：避免新建后端端点；dashboard overview 已在多个页面复用，数据源一致。月还与心愿进度都是客户端可算（L3、W2 已验证模式），但须显式区分复用 vs 新建 computed，且月还须用真实月供非利息估算。

**刷新契约（review P2，KeepAlive 返回不陈旧）**：hub 是主落地页，`onMounted` 因 KeepAlive 不在返回时重触发。须二选一：(a) `onActivated` 重 fetch（KeepAlive 返回时刷新），或 (b) 加 Vant `PullRefresh`（三 list 页已用该模式）手动刷新。原 Assumptions「不要求实时性」不足以覆盖主落地页的陈旧风险。

#### KTD-4：TabBar 入口顺序与非对称 owner/非 owner（review #3 修正）
**决策**：
- **owner**：`dashboard / finance / ai / baby / settings` = 5 项（移除 wishes/liabilities，加 finance；assets 首获 tab 入口）。
- **非 owner（adult）**：`dashboard / finance / ai / settings` = 4 项？——**修正为非对称保留 `wishes`**：`dashboard / wishes / finance / ai / settings` = 5 项（减 liabilities 加 finance，**保留 wishes 直达**）。`baby` 仅 owner 可见（`v-if="isOwner"`）。

**理由（review #3）**：child app 独立、不走 main app 的 /finance，故 main app 的"非 owner"实际是 adult。adult 最常见任务是心愿管理（查看/管理自己的心愿），把 wishes 塌进 hub 会让其从 1 tap 变 3-4 tap（finance→sub-tab→查看全部→list）。非对称 tab bar 用现有 `v-if="isOwner"` 机制：owner 用合并 hub 管全局，adult 保留 wishes 直达 + finance 入口管理资产/负债。captive 产品里切换成本 > 广度。

**实现**：`AppTabBar.vue` 的 `wishes` tab 改 `v-if="!isOwner"`（仅非 owner 显），`liabilities` tab 移除（所有人走 finance），`finance` tab 始终显，`baby` 保持 `v-if="isOwner"`。`activeTab` 映射不变（KTD-2 路径前缀覆盖三组）。

#### KTD-5：合并后 DashboardPage 的内嵌资产列表如何处置（⚠️ 实现期确认）
**背景**：recon 发现 DashboardPage 的资产列表（`DashboardPage.vue:108-137`，走 `dashboardStore.fetchAssetsPage` 分页 + `filteredByCategoryAssets` + `RecycleScroller`）与 `/assets`（`AssetListPage.vue`，走 `assetStore.fetchAssets` 全量 + 类型 tab + 搜索/批量删除）是**两套独立的数据源和渲染**，本就并存。N1 合并的是**导航入口**，不直接碰这两套。但合并后 dashboard 和 `/finance?tab=assets` 会出现资产信息重复铺陈，需决策 dashboard 内嵌资产列表的去留。

**推荐方案 A（总览瘦身）**：DashboardPage 移除内嵌资产列表（line 108-137），折叠为"查看全部资产 → `/finance?tab=assets`"入口；dashboard 保留净资产卡 / AI 教练卡 / 状态摘要 / idle·expiring 提醒卡。`/finance` 资产 sub-tab 承接完整资产管理。
- 理由：合并后 `/finance` 是财务实体之家，dashboard 回归"总览/诊断"定位（spec §1 闭环：总览诊断 → 财务 hub 管实体 → AI 教练），避免两处铺资产列表的冗余。

**备选方案 B（最小改动）**：DashboardPage 资产列表不动；`/finance?tab=assets` 只放摘要 + 跳转 `/assets`。
- 理由：改动最小；但 dashboard 与 finance 资产信息重复，与"合并减冗余"初衷相悖。

**不推荐方案 C**：dashboard 内嵌列表换成 `<AssetListPage>` 组件直接渲染——`AssetListPage` 依赖 `assetStore` + 路由 query + 批量模式，内嵌耦合 + keep-alive 复杂（recon 深化点 4 已警告）。

**默认采用方案 A**，但「可逆」措辞修正（review P1）：原称"可逆到方案 B"，但 U6 若删除 store 分页状态，回退 B 需重建 store 代码——非平凡。修正后：**U6 暂不删 store 分页状态**（仅停用 DashboardPage 的列表渲染 + 相关模板/computed），保留 `fetchAssetsPage`/`assetListFinished`/`filteredByCategoryAssets`/`categoriesWithAssetCount` 代码，确保回退 B 真正可逆（恢复渲染即可）。store 清理延后到方案 A 验证稳定后单独处理。

**方案 A 证据门槛（review P1）**：U6 前确认 dashboard 资产列表非高频路径（埋点或确认 `/assets` 从 finance tab 一 tap 可达使 dashboard 列表冗余）。若无证据，默认方案 B（保留列表，finance tab 只摘要+跳转），更低风险且仍达成入口收敛目标。

**方案 A 移除范围（review P1，须列举非"line 108-137"一笔带过）**：实际移除/迁移的 DashboardPage 资产区超出 line 108-137，含：
1. 资产 section header + 视图模式切换（卡片/列表，`:89-103`）——偏好迁移到 `/assets` 列表页或 localStorage。
2. `van-list` 无限滚动 + `filteredByCategoryAssets` 渲染（`:109-134`）——确认 `/assets` 列表页已具备无限滚动。
3. 空状态（`:137`）——随列表移除。
4. selection-mode 批量选择/删除块（`:140+`，独立于 108-137）——明确消失还是迁移到 `AssetListPage`。
5. 粘性 filter bar + 分类导航 `van-tabs` + `StatusSummaryGrid`（`:41-87`）——移除还是保留在 dashboard（StatusSummaryGrid 是诊断卡，倾向保留；filter bar 随列表移除）。
折叠为"查看全部资产 → `/finance?tab=assets`"入口卡片。**留 U6 单元承接**。

---

### Assumptions
- `dashboardStore.overview` 在 `/finance` 页 onMounted 时可用（若未加载则触发 `fetchAll`，沿用 DashboardPage 模式）。
- `liabilityStore.liabilities` 与 `wishStore` 数据可在 `/finance` 加载时拉取（已有 fetch action）。
- 概览卡不要求实时性，沿用 dashboard 的缓存新鲜度即可。

### Sequencing
U1（路由+页骨架）→ U2（概览卡）→ U3（三 sub-tab）→ U4（TabBar 合并 + active 映射）→ U5（i18n + 验证）→ U6（dashboard 瘦身，KTD-5 方案 A）。
U4 依赖 U1 的 `/finance` 路由存在。U2/U3 依赖 U1 骨架。可 U1 后 U2/U3 并行。U6 依赖 U4（TabBar finance 入口就位后 dashboard 瘦身才有承接去向）。

---

## Implementation Units

### U1 — 阶段0：`/finance` 路由 + FinanceHubPage 骨架
- 新建 `frontend/apps/main/src/pages/FinanceHubPage.vue`：空骨架 + `defineOptions({ name: 'FinanceHub' })`（为 KeepAlive name 匹配）。
- `router/index.ts`：在 MainLayout（`path: '/'`）的 **children 数组**（flat list，`router/index.ts:53-331`）加 `{ path: 'finance', name: 'FinanceHub', component: () => import('@/pages/FinanceHubPage.vue') }`，与 `assets`/`liabilities`/`wishes` 同级（review P1：必须作为 MainLayout children 而非独立顶级路由，否则脱离 TabBar + KeepAlive 布局）。
- **验证**：`/finance` 200 可达且 TabBar 渲染（证明在 MainLayout 内）；`pnpm typecheck` 过。

### U2 — 阶段1：首屏财务概览卡
- `FinanceHubPage.vue` 内新建概览卡区块：净资产（`MoneyDisplay`）+ 总负债（`MoneyDisplay`）+ 月还总额（computed）+ 心愿进度聚合（**四项：净资产/总负债/月还/心愿进度**，review P3 措辞对齐）。
- 数据源：`onMounted` 调 `dashboardStore.fetchAll()` + `liabilityStore.fetchLiabilities()` + `wishStore.fetchWishes()`（按需，沿用现有 store action）。
- 月还 computed 沿用 `LiabilityStrategyCard.vue:18-21` 的 `monthlyInterest` fallback 逻辑，**但须按 KTD-3 准确性修正**：优先 sum 非空 `monthly_payment`，null 项标注「估算」或用 `calc_amortization`，不把利息估算当月供 headline。
- 心愿进度：聚合 `wishStore.wishes` 的 `saved_amount`/`expected_price`（W1 已加字段），**按 KTD-3 聚合格式**：组合进度条 `sum(saved)/sum(expected)` + 「N 个心愿」副标题（`useAffordBar` per-wish 不复用）。
- **数据强转与过滤（review P2）**：`Number(x) ?? 0` 强转 string money 字段；月还 computed 过滤 `is_active === true`。
- **加载/空/错态（review P1）**：三 store 仅暴露 `loading` 无 `error` 标志，`MoneyDisplay` 只渲染数值无加载/空态。每卡片须明确：(1) 加载骨架屏（复用 `DashboardSkeleton` 模式或每指标占位）；(2) 空状态（如无资产/负债/心愿时「尚未记录」+ CTA 跳 `/assets/new` 等）；(3) 错误状态——store 无 error 标志则卡片级捕获 fetch 拒绝渲染带重试的占位符，**不静默显示 0**（否则用户误以为净资产 ¥0）。
- **W5 跨模块决策链提示（review #1，让 hub 触及 spec §1 决策链目标）**：概览卡除四项数字外，补一条联动提示——复用 `useDebtWarning` composable（W5 已实现，`useDebtWarning.ts` 暴露 `highInterestLiabilities` 含 `monthly_interest` + `shouldWarnForWish`）。逻辑：若 `hasHighInterestDebt` 且存在未 `ignore_debt_warning` 且 `monthly_saving>0` 的心愿，显示「高息负债每月利息 ¥X，相当于延迟心愿 Y 约 N 个月」（N = X / wish.monthly_saving，取最临近 `target_date` 的心愿作 Y）。数据全现成（FamilyDebtThresholds + wish monthly_saving/target_date），无后端改动。这让概览卡从"三个孤立数字"变成"三个数字 + 一个跨模块洞察"，触及决策链语义。无高息负债或无符合条件心愿时该提示隐藏（不占位）。
- **验证**：四项数字（净资产/总负债/月还/心愿进度）与 dashboard / 对应 list 页一致；`MoneyDisplay` 币种正确；**三 store 分别模拟 fetch 失败时概览卡降级为 error 占位符而非 0**（FinanceHubPage.spec.ts 的「空数据态」扩展为「部分失败态」）；**W5 联动提示在有高息负债+符合心愿时显示，N 计算正确，无符合条件时隐藏**。

### U3 — 阶段2：资产/负债/心愿三 sub-tab
- `FinanceHubPage.vue` 加 `<van-tabs>` 三 tab：资产 / 负债 / 心愿。
- **`?tab=` 契约（review P2，KTD-1 联动）**：onMounted 读 `route.query.tab`（`assets`|`liabilities`|`wishes`）`setActiveTab`，非法/缺失默认首个 tab。D3/U6 入口的 `?tab=` 由此消费。
- 每个 tab 内容：简短摘要 + "查看全部" 按钮 `router.push('/assets' | '/liabilities' | '/wishes')`。
- **摘要内容（review P2，须定义非"TBD"）**：每 tab 一致形式——资产 =「N 项资产 · 总额 ¥X」；负债 =「N 项负债 · 月还 ¥X」（复用 U2 月还 computed）；心愿 =「N 个心愿 · X 个进行中」。不展示 top 项（避免三 tab 排序依据不一致）；若后续要展示前 N 项，定义 N 与每 tab 排序（资产按价值、负债按到期、心愿按 ETA）。
- **验证**：三 tab 切换正常；"查看全部"跳转正确；**KeepAlive 范围澄清（review P2）**：仅保活 FinanceHubPage 的活跃 sub-tab 选择（返回 `/finance` 恢复选中 tab），**不**保活目标 list 页滚动/筛选状态（那些页面通过自身 `cachedTabs` 条目处理；从 `/assets/:id` 深层返回到 `/assets` list 而非 `/finance?tab=assets`，此为 KTD-1 已认代价）。原验证措辞「返回不丢状态（KeepAlive）」修正为「返回 `/finance` 恢复 sub-tab 选中态」。

### U4 — 阶段3：TabBar 合并 + active 映射 + cachedTabs
- `AppTabBar.vue`：
  - 移除 `liabilities` `<van-tabbar-item>`（所有人走 finance）。
  - `wishes` `<van-tabbar-item>` 改 `v-if="!isOwner"`（非对称，KTD-4：非 owner 保留 wishes 直达，owner 走 finance）。
  - 新增 `<van-tabbar-item name="finance" icon="...">`（icon 选 Vant 图标，如 `balance-o` 或 `chart-trending-o`，避开与 dashboard 重复；始终显示）。
  - `activeTab` computed：用**路径前缀匹配**（KTD-2）`route.path.startsWith('/assets') || startsWith('/liabilities') || startsWith('/wishes')` → `finance`，覆盖三组全部子路由含 params。`?focus=liability_strategy` 等 query 不影响匹配。
  - `tabToRoute` 加 `finance: '/finance'`，移除 `liabilities`（`wishes` 保留供非 owner）。
- `MainLayout.vue:28-36` `cachedTabs`：加 `'FinanceHub'`（配合 U1 的 `defineOptions name`）。
- **验证**：
  - **非对称 TabBar（review #3）**：owner 5 项（dashboard/finance/ai/baby/settings，无 wishes/liabilities）；非 owner 5 项（dashboard/wishes/finance/ai/settings，无 liabilities/baby）。
  - **active 映射覆盖深层子路由（review P2）**：finance tab 在 `/assets`、`/assets/:id`、`/assets/:id/edit`、`/assets/:id/sell`、`/liabilities/:id`、`/wishes/:id` 等全部高亮——加测试用例断言（注意：非 owner 访问 `/wishes/:id` 时 finance 高亮而非 wishes，因 active 映射按路径而非 tab 存在性；可接受，或实现期决定非 owner 下 /wishes 路径高亮 wishes tab）。
  - **`?focus=liability_strategy` deep-link（review P2）**：`/liabilities?focus=liability_strategy` 时 finance tab 高亮 + LiabilityListPage 滚动定位正常。
  - **`/assets` 高亮行为变更（review P2）**：当前 `/assets*` fallthrough 到 dashboard 高亮，本 U4 后改高亮 finance——验证此变更符合预期。
  - 从 `/assets` 返回 `/finance` 恢复 sub-tab 选中态（KeepAlive，见 U3 澄清）。
  - `pnpm typecheck` + `pnpm test:run` 过。

### U5 — 阶段4：i18n + 端到端验证
- `i18n/locales/zh-CN.ts` + `en-US.ts`：`nav` 下加 `finance: '财务' / 'Finance'`。
- 若 U3 tab 标题、U2 概览卡标签有新文案，一并加 i18n key（CLAUDE.md §Cross-Cutting：禁止硬编码中文）。
- **验证**：
  - 中英 locale 切换正常。
  - `pnpm lint` + `pnpm typecheck` + `pnpm test:run` 全过。
  - 手动：从 dashboard → finance tab → 三 sub-tab → 各 list 页 → 返回 finance，全程导航态正确。

### U6 — 阶段5：DashboardPage 资产列表瘦身（KTD-5 方案 A）
- **证据门槛前置（review P1）**：先确认 dashboard 资产列表非高频路径（埋点或确认 `/assets` 从 finance tab 一 tap 可达使列表冗余）；无证据则默认方案 B，跳过本单元。
- `DashboardPage.vue`：移除内嵌资产列表区块，折叠为"查看全部资产 → `/finance?tab=assets`"入口卡片。**移除范围按 KTD-5 列举**（非仅 line 108-137）：资产 section header + 视图模式切换（`:89-103`，偏好迁移 /assets 或 localStorage）、`van-list` 无限滚动 + `filteredByCategoryAssets` 渲染（`:109-134`，确认 /assets 已具备）、空状态（`:137`）、selection-mode 批量选择/删除块（`:140+`，明确消失或迁移 AssetListPage）、粘性 filter bar + 分类 van-tabs（`:41-87`，随列表移除；StatusSummaryGrid 诊断卡保留）。
- 保留 dashboard 的：净资产卡、AI 教练卡（FinanceCoachCard）、状态摘要（StatusSummaryGrid）、idle·expiring 提醒卡（`lowUsageAssets`/`expiringSoonAssets`，`line 34-35`）。
- **store 状态保留（review P1，保真正可逆）**：**暂不删** `dashboardStore.fetchAssetsPage` / `assetListFinished` / `filteredByCategoryAssets` / `categoriesWithAssetCount`——仅停用 DashboardPage 的列表渲染与相关模板/computed，保留 store 代码以便回退方案 B（恢复渲染即可）。store 清理延后到方案 A 验证稳定后单独处理。
- **验证**：dashboard 不再渲染资产流列表，但净资产卡 + 提醒卡 + AI 教练卡正常；"查看全部资产"入口跳 `/finance?tab=assets` 正确；`pnpm typecheck` + `pnpm test:run` 不新增失败（注意 DashboardPage 现有 spec 若断言资产列表渲染，需同步更新）；回退预案：若发现 dashboard 资产列表是高频入口，恢复渲染（store 代码未删，可逆）回退方案 B。
- **验证**：
  - dashboard 不再渲染资产流列表，但净资产卡 + 提醒卡 + AI 教练卡正常。
  - "查看全部资产"入口跳 `/finance?tab=assets` 正确。
  - `pnpm typecheck` + `pnpm test:run` 不新增失败（注意 DashboardPage 现有 spec 若断言资产列表渲染，需同步更新）。
  - 回退预案：若实现期发现 dashboard 资产列表是高频入口，回退到 KTD-5 方案 B（保留列表，finance tab 只跳转）。

---

## Verification Contract

### 测试基线
- `pnpm typecheck`（vue-tsc）。
- `pnpm test:run`（vitest）。
- 若新增 `FinanceHubPage.spec.ts`：覆盖概览卡渲染 + 三 tab 跳转 + 空数据态。

### grep 门槛
- 合并后 `AppTabBar.vue` 中 `<van-tabbar-item name="liabilities">` 应**消失**；`name="wishes"` 保留但改 `v-if="!isOwner"`（非对称，KTD-4）。
- `nav.wishes` / `nav.liabilities` i18n key 可保留（其他地方可能用），不强制删。

### 手动端到端
- owner 账号：6→5 入口（移除 wishes/liabilities 加 finance，assets 首获 tab）；finance tab 全链路；W5 联动提示在有高息负债+符合心愿时显示。
- 非 owner（adult）账号：非对称 5 项（保留 wishes 直达，减 liabilities 加 finance）；wishes tab 1 tap 到达 list；finance tab 可达资产/负债。
- deep-link `/assets`、`/liabilities`、`/wishes` 仍 200。

---

## Definition of Done

- [ ] U1-U6 全部完成，每阶段独立 commit、独立验证通过。
- [ ] `/finance` 路由 + `FinanceHubPage.vue` 上线，首屏概览卡（净资产+月还+心愿进度+W5 联动提示）+ 三 sub-tab。
- [ ] TabBar 统一入口：owner 5 项（移除 wishes/liabilities 加 finance，assets 首获 tab）；非 owner 非对称 5 项（保留 wishes 直达，减 liabilities 加 finance）。
- [ ] `/assets`、`/liabilities`、`/wishes` 顶级路由保留可达（deep-link 不破坏，含 `/liabilities?focus=liability_strategy`）。
- [ ] finance tab active 态覆盖三组路由及子路径。
- [ ] dashboard 内嵌资产列表按 KTD-5 方案 A 瘦身（或实现期确认回退方案 B），不与 `/finance?tab=assets` 重复铺陈。
- [ ] i18n 完整（`nav.finance` + 任何新文案，zh-CN + en-US）。
- [ ] `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 失败数 = 0（相对基线不新增失败）。
- [ ] 无 fake completion：无 `test.skip`/`.only`、无 TODO 占位、无未实现分支。

---

## Deferred / Open Questions

- **D3 联动**：D3（NetWorthCard 净资产/总负债可点下钻）依赖本 plan 的 `/finance` 路由。D3 在 P1 其余 12 项计划中，应在 N1 之后实现，下钻目标 `/finance?tab=liabilities`。**`?tab=` 契约已由 KTD-1/U3 落地**（finance 页 onMounted 读 `route.query.tab` setActiveTab），D3 可直接用 `/finance?tab=liabilities` 下钻，无空悬。
- **finance 页是否展示 FinanceCoachCard**：recon 深化点 2 已澄清——`FinanceCoachCard`（AI suggestions top 3）与概览卡（净资产+月还+心愿进度）是**两个不同组件**，概览卡是 U2 新建。FinanceCoachCard 可选地在 hub 页再放一份，但**默认不在本 plan 做**（U6 方案 A 后 dashboard 已保留 FinanceCoachCard，hub 再放会重复）；若需 hub 也展示 AI 教练建议，作为 P1 增强另起。
- **三 sub-tab 是否内嵌 list 预览**：U3 当前设计为"摘要 + 查看全部跳转"。若要内嵌完整 list（`<AssetListPage>` 等组件直接渲染），需评估组件耦合（list 页依赖路由 params / store 当前项）。**默认跳转模式，内嵌留作 P2 增强**。

### From 2026-07-21 ce-doc-review（已处理，2026-07-21 用户确认方向）

- **[P1] Hub 合并导航 ≠ spec 的「财务决策链」目标（premise 根）** — **已处理（选 B：补 W5 联动提示）**：U2 概览卡补一条 `useDebtWarning` 联动提示（高息负债每月利息 ¥X 相当于延迟心愿 Y N 个月），让 hub 触及决策链语义；Goal Capsule 显式声明完整决策链流转仍靠 D3/AI 教练等后续 P1 项。
- **[P2] 「6→5」实际净减 1，与「改动最大单项」投入产出不匹配** — **已处理（跟随 #1 改措辞）**：Goal/DoD 措辞从「TabBar 6→5」改为「统一三组为单 /finance 入口（owner 5 项，assets 首获 tab）」，价值定位为概览首屏+入口收敛非入口数减少。
- **[P2] 非 owner 工作流成本未评估** — **已处理（选 B：非对称 tab bar）**：KTD-4 改为非对称——非 owner（adult）保留 wishes 直达 tab（最常见任务 1 tap），owner 用合并 hub；child app 独立不走 main app /finance。

---

## 现状锚点（recon 证据）

| 锚点 | 位置 | 现状 |
|------|------|------|
| TabBar 当前 6 入口 | `AppTabBar.vue:3-12` | dashboard/wishes/ai/liabilities/baby(owner)/settings |
| `/finance` 路由 | `router/index.ts` | **不存在**（grep `finance` = 0） |
| FinanceHubPage | — | **不存在** |
| assets/liabilities/wishes 路由组 | `router/index.ts:65-132` | 各 4-5 子路由（list/new/edit/detail/sell），保留顶级 |
| cachedTabs | `MainLayout.vue:28-36` | Dashboard/AssetList/WishList/LiabilityList/AIHub/Baby/Settings（7 项，无 Family/FinanceHub） |
| nav.* i18n | `zh-CN.ts:58-66` | 已有 assets/wishes/liabilities/stats/baby/family/settings，**无 finance** |
| 月还计算参考 | `LiabilityStrategyCard.vue:18-21` | `monthlyInterest(l) = remaining × rate/100/12`，fallback 模式已验证 |
| overview 数据源 | `dashboardStore.overview: DashboardOverview` | 已含 net_worth/total_liabilities/month_over_month_change |

### Recon 交叉验证（2026-07-21 独立勘察 agent，逐行核实代码）

独立 recon agent 对 N1 现状做了完整勘察，结论与本 plan 一致，并深化了以下几点（已回填到上方 KTD/任务，此处留档交叉验证）：

**核心判断印证**：
> N1 is a "wrap existing pages in a hub" job, not a deep refactor — 三 list 页（AssetListPage/LiabilityListPage/WishListPage）自包含、各自带 `PageHeader`/`van-nav-bar` + `:show-back="false"` + `van-pull-refresh`，天然适合作为 sub-tab 包装。**印证本 plan KTD-1（保留顶级路由）方向**。

**Critical caveat（6→5 的真实口径）**：
当前 TabBar 6 入口里**本来就没有 `assets`**（资产只能从 dashboard 进）。所以"6→5"实际 = 删 `wishes` + `liabilities`（2 个）+ 加 `finance`（1 个）= 净减 1。`baby` owner-gated 保留。**印证本 plan KTD-4**。

**深化点 1 — deep-link 必须保住**（recon 发现，KTD-1 理由强化）：
- `/liabilities?focus=liability_strategy`（`WishListPage.vue:272` `goToLiabilityStrategy` → `LiabilityListPage.vue:358-368` 滚动定位）是 W5/T8 联动的活 deep-link，嵌套路由会破坏。
- `FinanceCoachCard.vue:45-50` 的 CTA 用绝对路径 `/liabilities/:id`、`/assets/:id`、`/wishes/:id`。
- 嵌套（approach B）会 break 所有 `router.push('/liabilities/...')` 调用点；保留顶级（approach A，本 plan KTD-1）blast radius 最小。**这是 KTD-1 选 A 不选 B 的硬证据**。

**深化点 2 — 概览卡是新组件，非 FinanceCoachCard 复用**（recon 发现，修正 Deferred 措辞）：
- `FinanceCoachCard.vue` 无 props、自拉 `getFinanceCoach`，渲染的是 AI suggestions（top 3），**与 spec line 120/163 的"净资产+月还+心愿进度"概览卡是两个东西**。
- 概览卡 = 新组件（U2）；FinanceCoachCard 可选地在 hub 页再放一份，但它不是概览卡本身。**本 plan Deferred"finance 页是否展示 FinanceCoachCard"项已据此澄清**。

**深化点 3 — 心愿进度无聚合字段**（recon 发现，U2 数据缺口显式化）：
- `DashboardOverview`（`types/index.ts:136-143`）只有 total_assets/total_liabilities/net_worth/asset_count/month_over_month_change/total_daily_cost，**无月还、无心愿进度聚合**。
- 月还：客户端 sum `liabilityStore.liabilities[].monthly_payment`（mirror `LiabilityStrategyCard.vue:41`）—— 本 plan KTD-3 已采用。
- 心愿进度：`useAffordBar` 有 per-wish 进度（`WishListPage.vue:248-253`），但**无整体 saved-vs-target 聚合**。U2 需新建聚合 computed（sum saved_amount / sum expected_price），或后端加字段。**本 plan U2 默认走客户端聚合 computed**。

**深化点 4 — KeepAlive 双层语义**（recon 发现，U4 实现注意）：
- `MainLayout.vue:6-13` 的 `<KeepAlive :include="cachedTabs">` + `<component :is="Component" :key="route.path" />`——**key 在 route.path，include 匹配组件 name**。
- 若 U3 sub-tab 用 `<router-view>` 子路由：MainLayout 的 KeepAlive 只看到顶层 FinanceHubPage，内层子视图的 keep-alive 是独立问题。
- 若 U3 sub-tab 用 `v-if`/`<component:is>` 条件渲染：tab 切换状态在离开 hub 时丢失，除非 FinanceHubPage 进 `cachedTabs`（加 `'FinanceHub'`，本 plan U4 已要求）。
- `AssetList`/`WishList`/`LiabilityList` 当前在 `cachedTabs`——若它们变成 hub 内嵌组件（非子路由），其 keep-alive 可能不再触发，需评估是否从 cachedTabs 移除。**本 plan U4 默认走"摘要+跳转"模式（KTD-1），三 list 页仍是顶级路由、cachedTabs 不变**。

**i18n 细节**（recon 发现）：
- `zh-CN.ts:58-67` 与 `en-US.ts:21-30` 顶层 `nav:` 已有 `assets`/`wishes`/`liabilities`/`stats`（其中 assets/stats 当前 TabBar 未用，是历史残留）。`nav.finance` 需新增。
- 三 sub-tab 标签可复用现有 `nav.assets`/`nav.liabilities`/`nav.wishes`，无需新 key（或用更干净的 `finance.tabAssets` 等）。

**recon 完整 file:line 索引**（备查）：

| 项 | 路径 | 行 |
|----|------|-----|
| TabBar 入口 | `AppTabBar.vue` | 3-12 |
| TabBar activeTab 匹配 | 同上 | 30-41 |
| TabBar tabToRoute | 同上 | 43-50 |
| Router MainLayout children（flat） | `router/index.ts` | 53-331 |
| assets/liabilities/wishes 路由组 | 同上 | 65-132 |
| LiabilityListPage `?focus` deep-link | `LiabilityListPage.vue` | 358-368 |
| WishListPage `goToLiabilityStrategy` | `WishListPage.vue` | 271-273 |
| WishListPage afford bar（net_worth dep） | 同上 | 248-253 |
| NetWorthCard props（净值行无 click） | `NetWorthCard.vue` | 54-61, 29-41 |
| FinanceCoachCard（无 props，CTA 绝对路径） | `FinanceCoachCard.vue` | 1-53, 45-50 |
| MainLayout KeepAlive + route.path key | `MainLayout.vue` | 6-13 |
| MainLayout cachedTabs | 同上 | 28-36 |
| DashboardOverview type（无月还/心愿进度） | `types/index.ts` | 136-143 |
| Liability.monthly_payment | 同上 | 119, 355 |
| zh-CN 顶层 nav | `zh-CN.ts` | 58-67 |
| en-US 顶层 nav | `en-US.ts` | 21-30 |

> recon agent 在生成最终汇总报告时中断（未发完成通知），但上述发现已从其 transcript 完整提取并逐行核实，与本 plan KTD-1/3/4 + U2/U4 完全一致，无矛盾。

---

## 依赖与后续

- **前置**：无（W1 心愿字段、L1 负债策略已由 P0 完成，概览卡数据可复用）。
- **解锁**：D3（NetWorthCard 下钻）依赖本 plan `/finance` 路由。
- **关联**：L3（月还 banner）与本 plan U2 的月还 computed 逻辑相同，可抽公共 util（见 P1 其余 12 项计划 L3 条目）。
