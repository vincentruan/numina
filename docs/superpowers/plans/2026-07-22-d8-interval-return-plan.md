# D8 区间收益率 — Implementation Plan

> **状态**：complete（2026-07-22 实现并验证）
> **日期**：2026-07-22
> **父文档**：[2026-07-22-p3-deferred-items-plan.md](./2026-07-22-p3-deferred-items-plan.md) §Deferred（D8 自定义区间收益率）+ [2026-07-19-family-finance-optimization-requirements.md](../specs/2026-07-19-family-finance-optimization-requirements.md) §3 D8
> **范围**：D8 区间收益率——AssetDetailPage 估值历史区加预设区间按钮（近 1 月/3 月/6 月/1 年），显示该区间收益率。纯前端（valuations + current_value 已加载）。
> **决策**：C 预设区间 / AssetDetailPage 单资产 / 与 D8 年化补充关系。
> **侦察依据**：D8 区间收益率 scout（2026-07-22）。

---

## Product Decision（已确认 2026-07-22）

| fork | 决策 |
|------|------|
| 交互形态 | **C 预设区间**（近 1 月/3 月/6 月/1 年按钮，自动取对应历史点）|
| 位置 | **AssetDetailPage 单资产**（估值历史区）|
| 与 D8 年化关系 | **补充**（年化=固定口径 InsightsTab 卡片；区间=用户自定义预设，AssetDetailPage）|

---

## Goal Capsule

**一句话**：AssetDetailPage 估值历史区加"区间收益率"卡——4 个预设区间按钮（近 1 月/3 月/6 月/1 年），选中后显示"自 X 日（¥A）至今（¥B）区间收益率 ±Y%"。

**为什么**：D8 已实现金融年化收益率（InsightsTab，固定口径）。区间收益率补齐用户自定义视角——看某资产近 N 月实际涨跌。复用现有 AssetValuation 历史（update_asset_value 已写历史）+ current_value，纯前端计算，无后端改动。

**完成标准**：4 预设区间按钮 + 区间收益率显示 + 数据不足态 + i18n；`pnpm typecheck` + `pnpm test:run` 不新增失败。

---

## Planning Contract

### 侦察结论
- `AssetDetailPage.vue:163-168` 估值历史区（`van-cell-group`，`valuations` 按 valued_at.desc 排序，最新在前）。`valuations = ref<AssetValuation[]>([])`（:237），`getValuations` 加载（:361）。
- `AssetValuation` 前端类型（types/index.ts:101）：`value: string` + `valued_at: string`。
- `asset.current_value` 已在 asset ref（money-as-str）。
- `currency.format(Number(x))` 已是 N3 修复后的正确模式（:166 用此）。
- 无 dayjs/date-fns——原生 `Date` 算 cutoff（utils/date.ts 已有原生 Date 模式）。
- 后端 `get_valuations`（services/asset.py:280）按 valued_at.desc 返回全部历史。

### KTD-1：区间收益率纯前端计算
- 对每个预设区间（1月=30天/3月=90天/6月=180天/1年=365天）：
  - cutoff = today - N 天。
  - 在 valuations（已 desc 排序）找**第一条 valued_at <= cutoff** 的历史点作 start（即 cutoff 之前最近的一次估值）。
  - end = `Number(asset.current_value)`。
  - 区间收益率 = `(end - start_value) / start_value × 100`，start_value = `Number(start.value)`。
  - start_value 为 0 或无该区间历史点 → "数据不足"。
- 原生 Date 算 cutoff：`new Date(Date.now() - N*24*3600*1000)`，比较 `new Date(v.valued_at) <= cutoff`。
- 显示：`自 {start_date}（{format(start_value)}）至今（{format(end)}）区间收益率 {±Y%}`，±显式符号（memory D4 双符号安全模式：format(abs)+手动±，因 format 已含¥）。

### KTD-2：UI — 估值历史区加区间收益率卡
- 在估值历史 `van-cell-group` 上方或下方加"区间收益率"区：
  - 4 个预设按钮（van-button size=small 或 van-tag，选中态高亮）：近 1 月/3 月/6 月/1 年。
  - 选中后显示区间收益率行（start 日期/金额 → end 金额 → ±Y%）。
  - 数据不足时显示"该区间暂无历史估值数据"。
  - 默认选中"近 1 月"或不选中（决策：默认不选中，点按钮才显示，避免无数据时默认报错）。
- 复用 `currency.format`（已在 AssetDetailPage setup，:166 用 `currency.format`）。

### KTD-3：i18n
- `assetDetail.intervalReturn` = "区间收益率"/"Interval Return"
- `assetDetail.interval1M/3M/6M/1Y` = "近1月"/"近3月"/"近6月"/"近1年" / "1M"/"3M"/"6M"/"1Y"
- `assetDetail.intervalReturnDetail` = "自 {date}（{start}）至今（{end}）收益率 {rate}"/EN
- `assetDetail.intervalNoData` = "该区间暂无历史估值数据"/"No valuation data in this period"
- 双 locale（zh-CN + en-US）。

### Sequencing
1. AssetDetailPage 加区间收益率卡（计算逻辑 + UI）。
2. i18n 双 locale。

---

## Implementation Units

| ID | 任务 | 改动点 | Effort |
|----|------|--------|--------|
| D8i-a | AssetDetailPage 区间收益率卡（计算 + UI） | AssetDetailPage.vue | small-medium |
| D8i-b | i18n 双 locale | zh-CN.ts + en-US.ts | trivial |

---

## Verification Contract

- `pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox TDZ；`pnpm lint` touched 0 新增。
- 手动：有多条估值历史的资产 → 4 区间按钮，选中显示区间收益率（±符号正确）；新区间无历史 → "数据不足"。
- 无 fake completion。

---

## Definition of Done

- [ ] D8i-a：AssetDetailPage 区间收益率卡——4 预设按钮 + 区间收益率计算（cutoff 前最近估值点 vs current_value）+ ±符号 + 数据不足态。
- [ ] D8i-b：i18n 双 locale（intervalReturn/interval1M-1Y/intervalReturnDetail/intervalNoData）。
- [ ] `pnpm typecheck` 0 错误；`pnpm test:run` 968 passed + 1 预存 InputBox TDZ；`pnpm lint` touched 0 新增。
- [ ] 无 fake completion。

---

## Deferred / Open Questions

- **双日期选择器**（决策 1 B）：本批预设区间；若需任意起止日期，加日期 picker + 查两个估值点，独立后续。
- **聚合多资产区间收益**：本批单资产；跨资产对齐日期聚合复杂，独立后续。
- **卡边界对齐/图表**：本批文字显示；若要区间收益曲线图，独立后续。

---

## 实现备注（2026-07-22 完成）

- **文件改动**：
  - `frontend/apps/main/src/pages/AssetDetailPage.vue`：模板 :162-186 新增「区间收益率」`van-cell-group`（与估值历史共用 `v-if="valuations.length"` guard，置于其上方）；脚本 :344-396 新增 `INTERVAL_DAYS` map / `intervalOptions` / `selectedInterval` ref / `intervalReturn` + `intervalReturnText` computed；样式 :737-763 `.interval-return/.interval-buttons/.interval-hint/.interval-detail`（light+dark）。
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` :883-891 + `en-US.ts` :574-582：`assetDetail.*` 下新增 8 key。
- **KTD-1 区间计算**：`cutoff = Date.now() - N*86400_000`（N∈{30,90,180,365}）；valuations 为 newest-first（后端 `valued_at DESC`），`.find(v => new Date(v.valued_at) <= cutoff)` 取 cutoff 之下最近点为 start；`startValue===0` 或无 qualifying 点 → null（数据不足）。`rate=(end-start)/start*100` 保留 2 位。
- **D4 双符号安全**：金额走 `currency.format()`（自带 ¥，不重复前缀）；rate 用显式 `±` + `Math.abs(rate).toFixed(2)%`。
- **UI 选型**：`van-button size="small"` + `:type="selected?'primary':'default'"` 高亮（页面现有交互控件均为 van-button，tag 留给只读状态）。默认未选 → `intervalSelectHint`；选中无数据 → `intervalNoData`；有数据 → 详情行。
- **验证**：`pnpm typecheck` 0 错；`pnpm lint`（3 个触碰文件）0 错 0 警；`pnpm test:run` 968 passed + 1 failed（`InputBox.test.ts` createI18n mock TDZ，预存基线，ai-chat 文件未触碰，与本改动无关）。
- **逻辑走查**：valuations=[今,40d前,100d前] → 近1月(30d cutoff)取 40d 前点；近3月(90d)取 100d 前点；近6月/近1年无 qualifying 点 → 数据不足。仅今日单点 → 全区间数据不足。逻辑正确。
