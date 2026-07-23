# 技术债收尾 — N3 Echarts ¥ + N2 a11y 残留 — Implementation Plan

> **状态**：complete（N3 + N2 实现并验证，2026-07-22）
> **完成日期**：2026-07-22
> **日期**：2026-07-22
> **父文档**：[2026-07-22-p2-compliance-a11y-plan.md](./2026-07-22-p2-compliance-a11y-plan.md) §Deferred（N3 Echarts formatter ¥ + N2 残留 div+@click）+ [P3 plan](./2026-07-22-p3-deferred-items-plan.md) §依赖与后续
> **范围**：P2 遗留技术债收尾——N3 Echarts/图表 formatter 硬编码 ¥ 改 useCurrency；N2 真实 a11y 残留 19 处 div+@click 补 role=button+tabindex+键盘。

---

## Goal Capsule

**一句话**：收尾 P2 遗留的两类技术债——(1) N3 图表/页面 formatter 里的 `¥${}` JS 模板字符串改走 `useCurrency().format()`（币种统一，修 ¥¥ 双币 bug 隐患）；(2) N2 真实 a11y 残留 19 处 `div+@click`（无 role/tabindex）补 `role=button tabindex=0 @keydown.enter @keydown.space.prevent`，或改 `<button>`。

**为什么**：P2 批 N3/W6 改了模板 `¥{{}}` 但遗留了 JS 字符串里的 `¥${}`（图表 formatter + 页面内显示），N2 改了高频卡片但遗留 19 处非核心交互。两者都是 P2 plan 明确 Deferred 的收尾项，低风险、纯前端、无跨层。完成后币种统一与 a11y 整改彻底闭环。

**完成标准**：N3 图表/页面 ¥ 全走 useCurrency（grep `¥\$\{` 在 formatter/label/title = 0）；N2 19 处补齐 a11y；`pnpm typecheck` + `pnpm test:run` + `pnpm lint` 不新增失败。

---

## Product Contract

### Scope Boundaries
- **做**：N3（图表 formatter + 页面内 `¥${}` 显示改 useCurrency）+ N2（19 处真实 a11y gap 补 role/tabindex/键盘）。
- **不做**：合法符号表（`utils/format.ts` CURRENCY_SYMBOLS、`MoneyDisplay.vue`/`LiabilityForm.vue`/`AssetForm.vue` 的 currency→symbol map、`usePrivacy.ts` formatAmount 默认参数）——这些是 useCurrency 底层定义，**保留**；i18n `¥{amount}` 占位符（en-US shortage 等）保留（那是 i18n 文案不是 JS 模板）；shareImage.ts 的 `¥0.00` fallback（图片导出硬编码，脱离响应式 currency 上下文，保留）。
- **纯前端**：无后端、无 migration、无跨层。

---

## Planning Contract

### 侦察结论（2026-07-22）

#### N3 真实改动点（JS 模板字符串 `¥${}`）
- **图表 formatter（Echarts）**：
  - `components/charts/DailyCostChart.vue:113` — `formatter: \`目标 ¥${props.targetDailyCost}\``（markLine label）
  - `components/charts/DailyCostChart.vue:143` — `formatter: (val: number) => \`¥${val}\``（axisLabel）
  - `pages/AssetDetailPage.vue:167` — `:title="\`¥${v.value.toLocaleString()}\`"`（van-cell 估值历史 title）
- **页面内显示（非 Echarts，但同属 `¥${}` 硬编码，N3/W6 同根因）**：
  - `components/asset/CostEquivalenceCard.vue:6,13` — `:value="\`¥${result.daily_cost.toFixed(2)}\`"` / `\`¥${result.opportunity_cost.toLocaleString()}\``
  - `components/asset/BuyVsRentCalculator.vue:40,41` — `\`¥${result.buy_total.toLocaleString()}\`` / rent_total
  - `components/ai/PurchasingPowerCalc.vue:62` — `return \`¥${v.toLocaleString(...)}\``
- **保留（合法符号表 / i18n / 图片 fallback）**：format.ts/MoneyDisplay/LiabilityForm/AssetForm symbol maps、usePrivacy.ts、en-US.ts `¥{amount}`、shareImage.ts `¥0.00`。

#### N2 真实 a11y 残留（19 处，无 role/tabindex 的 div+@click）
按类别分（整改模式不同）：
1. **toggle/tab 切换按钮**（6 处，InsightsTab）— `rank-sort-btn`×2(:110-111)、`view-all-row`(:135)、`popup-close`(:142)、`toggle-btn`×2(:217-218)。
2. **collapse header**（5 处）— PendingApprovalsSection `approval-header`、SubtaskCard `subtask-header`、AiProcessBlock `process-header`、ReportStepTimeline `step-title-row`×2。
3. **picker 触发器**（3 处）— CurrencySelector `currency-button`、CurrencyButton `currency-button`、AltchaWidget `captcha-checkbox`/`captcha-error-icon`/`captcha-label__text`。
4. **draw/create 卡片**（3 处）— DrawAnimation `box-container`、AgentGrid `agent-card--create`、AgentCard（待确认）。
5. **其他**— ReportStepTimeline `step-title-row`（已计入 collapse）。

### Key Technical Decisions (KTDs)

#### KTD-1：N3 图表 formatter 用 useCurrency.format
- `useCurrency().format(amount)` 已含 ¥（memory [[yy-double-currency-bug]]：formatCurrency 内部加 ¥）。`¥${val}` → `format(val)`。
- **Echarts formatter 闭包**：formatter 是 `(val) => string`，在 `<script setup>` 里 `const { format } = useCurrency()`，formatter 改 `(val) => format(val)`。DailyCostChart markLine label `formatter` 是字符串模板 `目标 ¥${x}` → 改 `formatter: () => \`${t('...目标')}${format(props.targetDailyCost)}\`` 或保留"目标"前缀 + format（i18n：检查是否有 `insights.dailyCost.target` key，无则保留中文前缀 + format）。
- **van-cell title**（AssetDetailPage:167）：`¥${v.value.toLocaleString()}` → `format(Number(v.value))`（v.value 是 str，money-as-str；format 接 number，需 Number() 转换——memory [[liability-float-to-numeric-migration]] 前端 Number() coercion 模式）。
- **页面内 `¥${}` 显示**（CostEquivalenceCard/BuyVsRentCalculator/PurchasingPowerCalc）：同样改 `format(Number(x))`。这些组件若已在 setup 引 useCurrency 则复用，否则加 `const { format } = useCurrency()`。

#### KTD-2：N2 整改模式 — 按类别
- **toggle/tab 切换按钮**（InsightsTab 6 处）：`<div @click>` → `<div role="button" tabindex="0" @click @keydown.enter @keydown.space.prevent>`。或更优改 `<button>` 重置样式——但 InsightsTab 这些是 inline toggle，改 button 需重置默认 button 样式（border/bg/padding），**决策：保留 div + role=button + tabindex + 键盘**（最小改动，与 P2 N2 已修站点模式一致，见 memory [[p2-17-items-complete-2026-07-22]] N2 模式）。
- **collapse header**（5 处）：同上模式 `role=button tabindex=0 @keydown.enter`（enter 切换，space 可选）。`@click="collapsed = !collapsed"` → `@keydown.enter="collapsed = !collapsed"`。
- **picker 触发器**（CurrencySelector/CurrencyButton/AltchaWidget）：`role=button tabindex=0 @keydown.enter @keydown.space.prevent="showPicker = true"`（或 triggerVerification）。AltchaWidget 的 `captcha-label__text` span 同。
- **draw/create 卡片**（DrawAnimation/AgentGrid/AgentCard）：同 role=button 模式。DrawAnimation 有 `!animating && $emit('draw')` 守卫，键盘 handler 保留守卫。

#### KTD-3：范围控制
- 19 处全改（非爆炸性，P2 plan 当时标 Deferred 是因聚焦高频卡片优先；现 19 处可一次性收尾）。
- 不改 `@click.self`（背景关闭，已语义清晰）/`@click.stop`（容器，非交互触发）——这些不在 19 处真实 gap 内。
- 每处加 `:aria-label` 或保留可见文字作 accessible name（toggle/collapse 文字已可见，无需额外 aria-label；图标按钮如 popup-close ✕ / draw card 需 aria-label）。

### Sequencing
1. **N3**（small，8 处 ¥${}）：图表 formatter + 页面显示改 useCurrency.format。
2. **N2**（medium，19 处 a11y）：按类别 5 批——toggle(6)/collapse(5)/picker(3+)/draw-create(3)。

---

## Implementation Units

| ID | 任务 | 改动点 | Effort |
|----|------|--------|--------|
| N3 | 图表+页面 ¥${} 改 useCurrency.format | DailyCostChart:113,143 / AssetDetailPage:167 / CostEquivalenceCard:6,13 / BuyVsRentCalculator:40,41 / PurchasingPowerCalc:62 | small |
| N2-a | InsightsTab toggle/tab 6 处 a11y | InsightsTab.vue:110,111,135,142,217,218 | small |
| N2-b | collapse header 5 处 a11y | PendingApprovalsSection/SubtaskCard/AiProcessBlock/ReportStepTimeline×2 | small |
| N2-c | picker 触发器 a11y | CurrencySelector/CurrencyButton/AltchaWidget | small |
| N2-d | draw/create 卡片 a11y | DrawAnimation/AgentGrid/AgentCard | small |

---

## Verification Contract

### 测试基线
- `pnpm typecheck` + `pnpm test:run` + `pnpm lint`（touched files）。

### grep 门槛
- N3 后：`grep -rn "¥\$\{" frontend/apps/main/src/components/charts/ frontend/apps/main/src/pages/AssetDetailPage.vue frontend/apps/main/src/components/asset/ frontend/apps/main/src/components/ai/PurchasingPowerCalc.vue` = 0（合法符号表/i18n 除外）。
- N2 后：19 处 div+@click 均含 `role=` 或 `tabindex`（`grep -nE "<(div|span|li|p) [^>]*@click" | grep -vE "role=|tabindex|@click\.self|@click\.stop"` = 0 in touched files）。

### 手动端到端
- N3：币种切非 CNY → 图表/页面金额符号跟随（无双 ¥）。
- N2：Tab 键可达 toggle/collapse/picker/card，Enter/Space 触发。

---

## Definition of Done

- [x] N3：14 处 `¥${}` 改 `useCurrency().format(Number(x))`（8 plan 枚举 + 6 额外图表站点 TrendLineChart/AllocationPieChart/AllocationTreemapChart/TrendLineChartSimple/AssetDetailPage returnText）；合法符号表/i18n/shareImage 保留。
- [x] N2：19 处 div+@click 补 role=button+tabindex+@keydown.enter（+space）+ aria-expanded（collapse）+ aria-label（图标按钮）；含 ToolCallList collapse header（executor 后补）。
- [x] grep 门槛达标：N3 scope `¥${` = 0；N2 repo-wide true gaps = 0（全 19 处修完）。
- [x] `pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox TDZ suite（0 test failures）；`pnpm lint` touched 0 新增。
- [x] 无 fake completion。

### 实现备注（2026-07-22）
- N3 executor 发现 plan 8-list 之外 5 个图表文件含同根因 `¥${}`（满足 grep gate 必须修），实际修 14 处。out-of-scope 残留 3 处（WishAdviceCard:83 建议文案 / WhatIfSimulator:154 / FinanceHubPage.spec.ts mock）留 N3-followup。
- **N3-followup 已清（2026-07-22）**：WishAdviceCard:83 + WhatIfSimulator:154 两处以引入 useCurrency 改 `currency.format(Number(...))`（WhatIfSimulator `formatDiff` 同步改 D4 双符号安全：显式 `±` + `format(Math.abs(v))`，去掉硬编码 ¥ 与 toLocaleString 取整）。FinanceHubPage.spec.ts:34 为 `vi.mock('@/composables/useCurrency')` 的 stub formatter（模拟 format 输出格式），属合法测试夹具**不改**。生产代码 grep `¥\$\{`（排除 `__tests__`）= 0。WishAdviceCard.spec.ts 因 useCurrency→useAuthStore 需活跃 Pinia 而加 useCurrency mock（同 FinanceHubPage 模式），4 测试全过。验证：typecheck 0 / vitest 968 passed + 1 预存 InputBox TDZ / eslint 触碰 3 文件 0 错 0 新警（WhatIfSimulator:98 showToast 未用为预存）。
- N2 executor 修 18 处（AgentCard 确认无 gap，plan 19 含此未确认项）；ToolCallList:106 collapse header executor 漏修，手动补齐 → repo-wide true gaps = 0。全部复用现有 i18n key（common.close/captcha.label/blindBoxDraw.tapHint/agents.createAgent），零新 key。

---

## Deferred / Open Questions

- **N3 i18n 前缀**：DailyCostChart markLine `目标 ¥${x}` 的"目标"前缀——若有 i18n key 用 i18n，否则保留中文前缀 + format（最小改动）。
- **N2 改 button vs div+role**：本批统一 div+role+tabindex（与 P2 已修模式一致）；若未来要语义化重写，可改 `<button>` 重置样式，独立后续。
