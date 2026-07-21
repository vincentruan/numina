# N1 财务 hub 落地 — Implementation Plan

> **状态**：draft，待实现
> **日期**：2026-07-21
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../../specs/2026-07-19-family-finance-optimization-requirements.md)（决策 ②B + ⑥C + §域7 N1）
> **范围**：新建 `FinanceHubPage` + `/finance` 路由 + TabBar 6→5（合并资产/负债/心愿为单入口）
> **来源**：spec §2「P1 含 N1(财务 hub 落地) … 单独成子计划」、§5 待办「[ ] P1 批次（含 N1 财务 hub，单独子计划）」

---

## Goal Capsule

**一句话**：把资产/负债/心愿从三个独立顶级 TabBar 入口合并为 `/finance` 一个入口，首屏财务概览卡（净资产 + 月还 + 心愿进度）+ 三 sub-tab 下钻，TabBar 从 6 降到 5。

**为什么**：当前六个模块是六个独立工具而非一条财务决策链（spec §1）。N1 是 P1 里改动最大的单项，也是后续 D3（净资产卡下钻）的前置依赖。

**完成标准**：
- `/finance` 路由 + `FinanceHubPage.vue` 上线，首屏概览卡 + 资产/负债/心愿三 tab。
- TabBar 移除 `wishes`、`liabilities` 两个独立项，新增单 `finance` 项；`dashboard / finance / ai / baby(owner) / settings` = 5（owner）/ 4（非 owner）。
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

#### KTD-2：finance tab active 映射覆盖三组路由
**决策**：`AppTabBar.vue` 的 `activeTab` computed 扩展——`/assets`、`/liabilities`、`/wishes` 及其所有子路径前缀均映射到 `finance`。

**理由**：用户在三组任意页面时，TabBar 应高亮 finance（而非 dashboard），否则导航态失真。

#### KTD-3：概览卡数据复用现有 dashboard overview，不新建后端端点
**决策**：`FinanceHubPage` 首屏概览卡（净资产 + 月还 + 心愿进度）的数据：
- 净资产 / 总负债：复用 `dashboardStore.overview`（`DashboardOverview` 类型，已含 `net_worth`/`total_liabilities`）。
- 月还总额：客户端 computed，sum 各 liability `monthly_payment`（沿用 L3 的计算方式，`monthly_payment` 为 null 时 fallback `remaining × rate/100/12`，见 `LiabilityStrategyCard.vue:18-21`）。
- 心愿进度：复用 `wishStore`（或 `useAffordBar` 已有的 per-wish 进度聚合）。

**理由**：避免新建后端端点；dashboard overview 已在多个页面复用，数据源一致。月还与心愿进度都是客户端可算（L3、W2 已验证模式）。

#### KTD-4：TabBar 入口顺序与 baby 条件项
**决策**：合并后 TabBar 顺序 `dashboard / finance / ai / baby(owner) / settings`。`baby` 仍保持 `v-if="isOwner"` 条件项。非 owner 用户为 4 项。

**理由**：owner 与非 owner 的入口数差异保持现状，只减少 owner 的心愿/负债两个独立项。

---

### Assumptions
- `dashboardStore.overview` 在 `/finance` 页 onMounted 时可用（若未加载则触发 `fetchAll`，沿用 DashboardPage 模式）。
- `liabilityStore.liabilities` 与 `wishStore` 数据可在 `/finance` 加载时拉取（已有 fetch action）。
- 概览卡不要求实时性，沿用 dashboard 的缓存新鲜度即可。

### Sequencing
U1（路由+页骨架）→ U2（概览卡）→ U3（三 sub-tab）→ U4（TabBar 合并 + active 映射）→ U5（i18n + 验证）。
U4 依赖 U1 的 `/finance` 路由存在。U2/U3 依赖 U1 骨架。可 U1 后 U2/U3 并行。

---

## Implementation Units

### U1 — 阶段0：`/finance` 路由 + FinanceHubPage 骨架
- 新建 `frontend/apps/main/src/pages/FinanceHubPage.vue`：空骨架 + `defineOptions({ name: 'FinanceHub' })`（为 KeepAlive name 匹配）。
- `router/index.ts`：在 MainLayout children 加 `{ path: 'finance', name: 'FinanceHub', component: () => import('@/pages/FinanceHubPage.vue') }`。
- **验证**：`/finance` 200 可达；`pnpm typecheck` 过。

### U2 — 阶段1：首屏财务概览卡
- `FinanceHubPage.vue` 内新建概览卡区块：净资产（`MoneyDisplay`）+ 总负债（`MoneyDisplay`）+ 月还总额（computed）+ 心愿进度聚合。
- 数据源：`onMounted` 调 `dashboardStore.fetchAll()` + `liabilityStore.fetchLiabilities()` + `wishStore.fetchWishes()`（按需，沿用现有 store action）。
- 月还 computed 沿用 `LiabilityStrategyCard.vue:18-21` 的 `monthlyInterest` fallback 逻辑。
- 心愿进度：聚合 `wishStore.wishes` 的 `saved_amount`/`expected_price`（W1 已加字段）。
- **验证**：概览卡四项数字与 dashboard / 对应 list 页一致；`MoneyDisplay` 币种正确。

### U3 — 阶段2：资产/负债/心愿三 sub-tab
- `FinanceHubPage.vue` 加 `<van-tabs>` 三 tab：资产 / 负债 / 心愿。
- 每个 tab 内容：简短摘要 + "查看全部" 按钮 `router.push('/assets' | '/liabilities' | '/wishes')`。
- 摘要可为各 list 的 count / top 项（轻量，不重渲染整页 list）。
- **验证**：三 tab 切换正常；"查看全部"跳转正确；返回 `/finance` 不丢状态（KeepAlive 生效，见 U4 的 cachedTabs）。

### U4 — 阶段3：TabBar 合并 + active 映射 + cachedTabs
- `AppTabBar.vue`：
  - 移除 `wishes`、`liabilities` 两个 `<van-tabbar-item>`。
  - 新增 `<van-tabbar-item name="finance" icon="...">`（icon 选 Vant 图标，如 `balance-o` 或 `chart-trending-o`，避开与 dashboard 重复）。
  - `activeTab` computed：`/assets`、`/liabilities`、`/wishes` 及子路径前缀 → `finance`（KTD-2）。
  - `tabToRoute` 加 `finance: '/finance'`，移除 `wishes`/`liabilities`。
- `MainLayout.vue:28-36` `cachedTabs`：加 `'FinanceHub'`（配合 U1 的 `defineOptions name`）。
- **验证**：
  - TabBar 5 项（owner）/ 4 项（非 owner）。
  - 访问 `/assets`、`/liabilities`、`/wishes` 及子页时 finance tab 高亮。
  - 从 `/assets` 返回 `/finance` 不重新 fetch（KeepAlive）。
  - `pnpm typecheck` + `pnpm test:run` 过。

### U5 — 阶段4：i18n + 端到端验证
- `i18n/locales/zh-CN.ts` + `en-US.ts`：`nav` 下加 `finance: '财务' / 'Finance'`。
- 若 U3 tab 标题、U2 概览卡标签有新文案，一并加 i18n key（CLAUDE.md §Cross-Cutting：禁止硬编码中文）。
- **验证**：
  - 中英 locale 切换正常。
  - `pnpm lint` + `pnpm typecheck` + `pnpm test:run` 全过。
  - 手动：从 dashboard → finance tab → 三 sub-tab → 各 list 页 → 返回 finance，全程导航态正确。

---

## Verification Contract

### 测试基线
- `pnpm typecheck`（vue-tsc）。
- `pnpm test:run`（vitest）。
- 若新增 `FinanceHubPage.spec.ts`：覆盖概览卡渲染 + 三 tab 跳转 + 空数据态。

### grep 门槛
- 合并后 `AppTabBar.vue` 中 `<van-tabbar-item name="wishes">` 与 `name="liabilities"` 应**消失**。
- `nav.wishes` / `nav.liabilities` i18n key 可保留（其他地方可能用），不强制删。

### 手动端到端
- owner 账号：6→5 入口；finance tab 全链路。
- 非 owner 账号：5→4 入口；finance tab 可用。
- deep-link `/assets`、`/liabilities`、`/wishes` 仍 200。

---

## Definition of Done

- [ ] U1-U5 全部完成，每阶段独立 commit、独立验证通过。
- [ ] `/finance` 路由 + `FinanceHubPage.vue` 上线，首屏概览卡（净资产+月还+心愿进度）+ 三 sub-tab。
- [ ] TabBar 6→5（owner），移除 wishes/liabilities 独立项，新增 finance 项。
- [ ] `/assets`、`/liabilities`、`/wishes` 顶级路由保留可达（deep-link 不破坏）。
- [ ] finance tab active 态覆盖三组路由及子路径。
- [ ] i18n 完整（`nav.finance` + 任何新文案，zh-CN + en-US）。
- [ ] `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 失败数 = 0（相对基线不新增失败）。
- [ ] 无 fake completion：无 `test.skip`/`.only`、无 TODO 占位、无未实现分支。

---

## Deferred / Open Questions

- **D3 联动**：D3（NetWorthCard 净资产/总负债可点下钻）依赖本 plan 的 `/finance` 路由。D3 在 P1 其余 12 项计划中，应在 N1 之后实现，下钻目标 `/finance?tab=liabilities`。但当前 `/finance` 三 sub-tab 是"查看全部"跳转模式（KTD-1），`?tab=` query 暂不消费——D3 实现时再决定是否让 finance 页读 `?tab=` 自动切 tab。**留待 D3 实现期定**。
- **finance 页是否展示 FinanceCoachCard**：`FinanceCoachCard.vue`（Plan A D2）当前在 DashboardPage。是否在 finance 概览卡也复用一份？**默认不在本 plan 做**，避免与 dashboard 重复；若需要作为 P1 增强另起。
- **三 sub-tab 是否内嵌 list 预览**：U3 当前设计为"摘要 + 查看全部跳转"。若要内嵌完整 list（`<AssetListPage>` 等组件直接渲染），需评估组件耦合（list 页依赖路由 params / store 当前项）。**默认跳转模式，内嵌留作 P2 增强**。

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

---

## 依赖与后续

- **前置**：无（W1 心愿字段、L1 负债策略已由 P0 完成，概览卡数据可复用）。
- **解锁**：D3（NetWorthCard 下钻）依赖本 plan `/finance` 路由。
- **关联**：L3（月还 banner）与本 plan U2 的月还 computed 逻辑相同，可抽公共 util（见 P1 其余 12 项计划 L3 条目）。
