# P2 批次 — Implementation Plan

> **状态**：draft，待实现
> **日期**：2026-07-22
> **父文档**：[2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md)（§2 P2 批 + §3 需求总表 P2 项 + §5 待办「[ ] P2 批次」）
> **范围**：P2 批 17 项——i18n 合规、a11y 整改、币种统一、emoji 清理、语义修正、设置增强
> **来源**：spec §2「P2 批（10 项）— i18n 合规与可访问性」（实际总表数 17 项，spec "10 项" 为概数）

---

## Goal Capsule

**一句话**：完成 P2 批 17 项体验合规性整改——币种统一（W6/L6/N3 去 ¥ 硬编码）、a11y 整改（N2/D10/B5/F6 div+@click→button+role+键盘、heading 语义）、emoji 清理迁 i18n（B2/S3/F6）、AI 报告语义修正（A4 score-poor 绿改红、A5 SECTION_LABELS 已随 A3 清理、A7 AI tab 加文字标签）、Baby 分组修正（B3 fulfilled 移除 rejected）、设置增强（S1 主题色服务端持久化、S2 非 owner 隐藏 is-link 箭头、F2 clipboard util）、假 affordance 修正（D9）。

**为什么**：P0/P1 交付了功能闭环与决策链载体（finance hub），P2 补齐合规性与体验一致性（spec §2）。本批是支撑性整改，分三轨——(a) 合规性（i18n/a11y/币种统一 N3/W6/L6/N2/D10/B5/F6）消除硬编码与键盘不可达；(b) 语义修正（A4/A5/B3/D9）修正误导性视觉/分组；(c) 设置增强（S1/S2/S3/F2）持久化与权限感知。无直接功能增量，降维护噪音 + 提升可访问性。

**完成标准**：17 项逐项落地，每项独立 commit + 验证；`pnpm typecheck` + `pnpm test:run` + `uv run pytest`（S1 scope）不新增失败。

---

## Product Contract

### Scope Boundaries
- **做**：17 项 P2（见下任务表）。
- **不做**：P3（spec §11 推迟：W6b 回链/L7 联动/D8 拆分/A6 导出/B1 教育/S4+ 等）；S1 仅加主题色持久化，不重构整个 settings 系统。
- **跨层**：S1 需后端 user settings API + 前端同步；其余 16 项纯前端。

---

## Planning Contract

### Key Technical Decisions (KTDs)

#### KTD-1：N3/L6/W6 币种统一——区分"合法符号表"与"模板硬编码 ¥"
**决策**：44 处 `¥` 分两类：(a) **合法符号表**（`utils/format.ts`/`MoneyDisplay.vue`/`LiabilityForm.vue`/`AssetForm.vue` 的 currency→symbol map，`usePrivacy.ts` 的 `formatAmount` 默认参数）——**不删**，这些是 `useCurrency` 的底层定义；(b) **模板硬编码 `¥{{}}`**（AssetSellPage/AssetDetailPage/WishListPage/WishDetailPage/LiabilityDetailPage/SmartRemindersCard/DailyCostChart/CostEquivalenceCard 等 ~20 处）——**改用 `useCurrency().format()`**。

**¥¥ 双币 bug 关联**（memory [[yy-double-currency-bug]]）：`useCurrency().format()` 已含 ¥，模板 `¥{{ format() }}` 会双币。本次统一时须验证每处改动的 caller 是传 format() 输出还是 raw number——传 raw number 给 format() 才正确（format 内部加 ¥）。

**W6 特殊**：spec W6 是"心愿去 emoji 兜底 + 硬编码 ¥"。心愿页 emoji 兜底（如愿望图标）若用 emoji 作 fallback，改 SVG icon 或 Vant icon。

#### KTD-2：N2/D10/B5 a11y 整改——div+@click→button+role+键盘
**决策**：33 处 `div/span/li/p + @click` 无 role/tabindex。整改模式：
- **可交互卡片**（wish-card/chore-card/detail-item）：`<div @click>` → `<div role="button" tabindex="0" @click @keydown.enter @keydown.space>`，或更优改 `<button>` 重置样式。
- **D10 StatusSummaryGrid**：`<div @click="onSelect">` → `<button role="tab" :aria-selected="isActive" tabindex="0">`，加 `@keydown` 左右箭头切换（ARIA tabs pattern）。
- **B5 BabyPage 卡片**：wish-card/chore-card 的 `@click="openWishDetail"` 等加 role=button + 键盘。

**范围控制**：N2"跨模块"不逐个改 33 处（爆炸性），聚焦高频可交互卡片（wish/chore/asset/liability list item、dashboard status tabs、baby cards）。低频装饰性 div+@click（如 collapse header）若已有 cursor:pointer 且非核心交互，可标 Deferred。

#### KTD-3：A5 已无对象——A3 清理时一并删除 SECTION_LABELS
**决策**：A3（P1）删除 AIReportPage narrative 分支时已清掉 `SECTION_LABELS`（grep 确认 0 引用）。A5 "SECTION_LABELS 迁 i18n" **无对象**，标已完成（A3 副产品）。验证：`grep -rn "SECTION_LABELS" frontend/apps/main/src` = 0。

#### KTD-4：A4 score-poor 绿改红——仅 AIReportPage，不动其他 #4caf50
**决策**：`#4caf50` 在多处使用（DeploymentHeatmap/ChildCalendar/ReportStepTimeline/WishListPage priority-low/BabyDayDetailPage approved/AIReportPage score-poor+negative）。A4 仅指 **AIReportPage score-poor**（line 426/449，语义=评分差却显绿色，错误）。改为红/橙（如 `#ef4444` 红 或 `#f59e0b` 橙）。**不动**其他 #4caf50（priority-low 绿色正确、approved 绿色正确、negative 绿色=财务正向正确）。

#### KTD-5：S1 主题色服务端持久化——加 user.theme_color 字段
**决策**：当前主题色纯 `localStorage`（`SettingsPage.vue:276/333/407`）。S1 加：
- 后端：`User.theme_color` 字段（String，nullable）+ alembic migration + `PUT /auth/me` 或新 `PUT /users/settings` 端点更新 + `GET /auth/me` 返回含 theme_color。
- 前端：`onMounted` 从 `authStore.user.theme_color` 初始化（fallback localStorage），`selectThemeColor` 时同时写 localStorage + 调后端更新。
- **冲突处理**：多设备登录时，服务端值优先（onMounted 覆盖 localStorage）；离线时 fallback localStorage。

**effort medium**：跨层 alembic + schema + API + 前端同步。

#### KTD-6：S2 非 owner 隐藏 is-link 箭头——扩展到所有设置 cell
**决策**：`SettingsPage.vue:11` 已有 `:is-link="authStore.user?.role === 'owner'"`（family cell），但 line 35/40/45/50/64/70/77/78/79 等仍无条件 `is-link`。S2 统一：所有设置 cell 的 `is-link` 改 `:is-link="isOwner"`（非 owner 隐藏箭头，因非 owner 无编辑权限）。

**注意**：部分 cell（如 language/default_currency）非 owner 也可改自己的偏好——需逐 cell 判断权限语义，非一刀切。实现期确认每个 cell 的 owner-only 性质。

#### KTD-7：F2 clipboard 改 copyToClipboard util
**决策**：`FamilyPage.vue:388` 直接 `navigator.clipboard.writeText`。LAN HTTP 非安全上下文 `navigator.clipboard` 可能 undefined（memory [[ai-chat-copy-button-non-secure-context]]）。改用项目已有 `copyToClipboard` util（若 utils 无独立 util，从 ai-chat 的实现抽取到 `utils/clipboard.ts`，含 execCommand fallback）。

#### KTD-8：emoji 清理（B2/S3/F6）——Vant icon 或纯文字
**决策**：
- **B2**：BabyPage 优先级短标签 `🔥高` 等 → i18n key + Vant icon（`fire-o`）或纯文字"高"。
- **S3**：主题选项 `🌓/☀️/🌙` → Vant icon（`contrast-o`/`sunny-o`/`moon-o`）或纯文字。
- **F6**：section-heading `👥/👧` + `<p>` → `<h2>` 语义 + 去 emoji（或 Vant icon）。
- ⭐ emoji（star_coin）是产品符号（星星币），**保留**（非装饰 emoji，是货币单位）。

---

### Sequencing（按依赖 + effort 排序）

**第一批（trivial，无依赖，纯前端单文件）**：A4、A5（验证无对象）、A7、B3、F6、S3
**第二批（small，扫描型多文件）**：W6、L6、N3（合并推进，都是去 ¥）、B2、F2、S2、D9
**第三批（small-medium，a11y 扫描型）**：D10、B5、N2
**第四批（medium，跨层）**：S1（后端 + 前端）

四批合计 17 项。N3/L6/W6 合并推进（同根因：去 ¥ 硬编码）。

---

## Implementation Units

### 任务表（17 项）

| ID | 任务 | 改动点 | Effort | 依赖 |
|----|------|--------|--------|------|
| A4 | score-poor 绿改红 | `AIReportPage.vue:426,449` #4caf50→红/橙 | trivial | 无 |
| A5 | SECTION_LABELS 迁 i18n | **已无对象**（A3 清理），grep 验证 0 | trivial | 无 |
| A7 | AI tab 加可见文字标签 | `AppTabBar.vue:7-11` AI tab 加 `{{ t('nav.ai') }}` | trivial | 无 |
| B3 | fulfilled 组移除 rejected | `BabyPage.vue:175-180` fulfilledWishes 过滤确认无 rejected | trivial | 无 |
| F6 | section heading 去 emoji + h2 | `FamilyPage.vue:19,96` `<p>`→`<h2>` + 去 👥👧 | trivial | 无 |
| S3 | 主题选项去 emoji | `SettingsPage.vue:336-350` 🌓/☀️/🌙→Vant icon | trivial | 无 |
| W6 | 心愿去 emoji 兜底 + 硬编码 ¥ | `WishListPage.vue`/`WishDetailPage.vue` 去 ¥ + emoji→icon | small | 无 |
| L6 | 负债去 ¥ 硬编码 | `LiabilityDetailPage.vue:11` 等 → useCurrency | small | 无 |
| N3 | 币种统一（全走 useCurrency） | AssetSellPage/AssetDetailPage/DailyCostChart 等 ~20 处 | small-medium | 无 |
| B2 | 优先级短标签迁 i18n | BabyPage `🔥高` 等 → i18n + icon | small | 无 |
| F2 | clipboard 改 copyToClipboard util | `FamilyPage.vue:388` + 抽 utils/clipboard.ts | small | 无 |
| S2 | 非 owner 隐藏 is-link 箭头 | `SettingsPage.vue` 所有 cell `:is-link="isOwner"` | small | 无 |
| D9 | 修假 affordance | `SmartRemindersCard.vue:91` low-usage is-link 补 click / 领奖台 chip 去 pointer | small | 无 |
| D10 | StatusSummaryGrid a11y | `StatusSummaryGrid.vue:4-9` div→button role=tab aria-selected + 键盘 | small-medium | 无 |
| B5 | BabyPage 卡片补 a11y | `BabyPage.vue` wish-card/chore-card role=button + 键盘 | small-medium | 无 |
| N2 | 跨模块 a11y 整改 | 聚焦高频可交互卡片（asset/liability/wish list item）div→button+role+键盘 | medium | 无 |
| S1 | 主题色服务端持久化 | 后端 User.theme_color + alembic + API + 前端同步 | medium | 跨层 |

---

## Verification Contract

### 测试基线
- 前端：`pnpm typecheck` + `pnpm test:run` + `pnpm lint`（scope touched files）。
- 后端（仅 S1）：`uv run pytest tests/backend/`（user/auth scope）+ `uv run ruff check` + `uv run mypy`。

### grep 门槛
- A5 后：`grep -rn "SECTION_LABELS" frontend/apps/main/src` = 0（已随 A3 = 0）。
- N3/L6/W6 后：模板 `¥{{` 硬编码 = 0（合法符号表除外）。
- S3 后：`grep -rn "🌓\|☀️\|🌙" frontend/apps/main/src/pages/SettingsPage.vue` = 0。
- F6 后：`grep -n "👥\|👧" frontend/apps/main/src/pages/FamilyPage.vue` = 0。

### 手动端到端
- A4：score-poor 显红/橙非绿。
- D10：StatusSummaryGrid 键盘左右切换 + Tab 可达。
- S1：换设备登录主题色同步。
- N3：币种切换后金额符号正确（无双 ¥）。

---

## Definition of Done

- [ ] 17 项全部完成，每项独立 commit、独立验证通过。
- [ ] grep 门槛全部 = 0（A5/N3 模板/S3/F6）。
- [ ] S1 后端 User.theme_color + API + 前端同步；多设备主题色一致。
- [ ] i18n 完整（所有新文案 zh-CN + en-US，无硬编码中文）。
- [ ] `pnpm typecheck` + `pnpm test:run` + `pnpm lint` 不新增失败。
- [ ] `uv run pytest`（S1 scope）不新增失败。
- [ ] 无 fake completion：无 `test.skip`/`.only`、无 TODO 占位、无未实现分支。

---

## Deferred / Open Questions

- **N2 范围**：33 处 div+@click 全改爆炸性，聚焦高频可交互卡片；低频装饰性（collapse header 等）标 Deferred。
- **S2 权限语义**：非一刀切 `:is-link="isOwner"`，逐 cell 判断（language/currency 非 owner 可改）。
- **W6 心愿 emoji 兜底**：若 emoji 是产品设计的视觉占位，改 SVG icon 需选合适 icon set。
- **B2 ⭐ 货币符号**：star_coin 的 ⭐ 是货币单位非装饰 emoji，保留。

---

## 依赖与后续

- **前置**：P0/P1 已完成（数据基础 + finance hub 就绪）。
- **解锁**：P3（spec §11 推迟项）——P2 完成后可起 P3 计划。
