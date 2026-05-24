# Analytics Page: Trend/Insight Tabs Redesign

**Date:** 2026-05-24  
**Branch:** optimize/asset-trend  
**Files touched:** `AssetAnalyticsPage.vue`, `dashboard.py` (service + router), `dashboard.ts` (store), `api/dashboard.ts`, `types/index.ts`, `zh-CN.ts`, `en-US.ts`

---

## Overview

Redesign `AssetAnalyticsPage.vue` to introduce a tab bar (趋势 / 洞悉) at the page header. The 趋势 tab replaces three existing cards with four redesigned sections and retains three existing cards that provide unique content. The 洞悉 tab is a placeholder empty state for now.

---

## Tab Bar

A `van-tabs` component at the top of the page (below `PageHeader`), replacing the flat card list. Two tabs:

- **趋势** (`trend`) — contains all statistics sections
- **洞悉** (`insight`) — empty state placeholder

Tab state is local (`ref<'trend' | 'insight'>('trend')`), not persisted. Use `van-tabs` with `type="line"` styled to match the design system (active tab uses `var(--van-primary-color)`, dark mode uses `var(--color-lavender)` per existing pattern).

i18n keys: `analyticsPage.tabTrend` / `analyticsPage.tabInsight`

---

## 趋势 Tab — Section Order

1. 资产总值 (Total Asset Value)
2. 资产状态 (Asset Status Distribution)
3. 新增资产 (Newly Added Assets)
4. 日均成本 (Daily Average Cost)
5. 资产分布 — `AllocationTreemapChart` (kept, unique content)
6. 分类占比 — `AllocationPieChart` (kept, unique content)
7. 低使用率资产 — `LowUsageCard` (kept, unique content)

**Removed cards:** `TrendLineChartSimple` card (replaced by 资产总值), `NetWorthChangeCard` (MoM % merged into 资产总值 header), old `DailyCostCard` (replaced by redesigned 日均成本 section).

---

## Section Specs

### 1. 资产总值

**Data:** `dashboardStore.overview` (total_assets, net_worth, month_over_month_change) + `dashboardStore.trend` (TrendPoint[])

**Layout:**
- Card header: section title + period selector tabs (月/季/年, `van-tabs type="card"`)
- Large net_worth value with currency symbol
- MoM % change badge inline below value (green ▲ / red ▼ / grey — using existing `.change-up`/`.change-down` CSS pattern)
- ECharts area chart (reuse `TrendLineChartSimple` component, height 160px) — shows net_worth as filled area, total_assets and total_liabilities as dashed lines
- Period selector drives `dashboardStore.fetchTrend(period)` (same as current behavior)

**i18n keys:** `analyticsPage.totalAssetsSection`, `analyticsPage.changeUp`, `analyticsPage.changeDown`, `analyticsPage.noChange`

---

### 2. 资产状态

**Data:** `dashboardStore.statesSummary` (already fetched in `fetchAll` phase 1)

**Layout:**
- Card with title
- 2×2 grid of status tiles, each showing count + label
- Status color mapping (CSS variables, dark-mode safe):
  - `in_use` → green tint: `rgba(5,150,105,0.08)` / text `#059669`; dark: `rgba(110,231,160,0.12)` / text `#6ee7a0`
  - `idle` → orange tint: `rgba(250,140,22,0.08)` / text `#fa8c16`; dark: `rgba(251,191,36,0.12)` / text `#fbbf24`
  - `sold` → blue tint: `rgba(59,130,246,0.08)` / text `#3b82f6`; dark: `rgba(147,197,253,0.12)` / text `#93c5fd`
  - `retired` → muted: `var(--bg-secondary)` / text `var(--text-secondary)`

**i18n keys:** reuse existing `statusGrid.inUse`, `statusGrid.idle`, `statusGrid.sold`, `statusGrid.retired`

No new data fetch needed — `statesSummary` is already loaded.

---

### 3. 新增资产

**Data:** New backend endpoint `GET /api/v1/dashboard/new-assets?period=month|quarter|year`

**Backend changes (dashboard.py service):**

```python
def get_new_assets(db: Session, user: User, period: str = "month") -> dict:
    today = date.today()
    if period == "year":
        start_date = today - timedelta(days=365)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:
        start_date = today - timedelta(days=30)

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.created_at >= start_date,
        )
        .order_by(Asset.created_at.desc())
        .all()
    )
    # returns: count of all matching assets + up to 5 most recent items for display
    items_for_display = assets[:5]
    return {
        "count": len(assets),
        "period": period,
        "items": [_to_new_asset_item(a, default_currency, db) for a in items_for_display],
    }
```

`icon` is sourced from `a.category.icon if a.category else ""` (same pattern as other dashboard services).

Returns:
```json
{
  "count": 4,
  "period": "month",
  "items": [
    {"id": "...", "name": "MacBook Pro", "icon": "💻", "category_name": "电子设备",
     "current_value": 18999, "currency": "CNY", "created_at": "2026-05-19T..."}
  ]
}
```

Values converted to `user.default_currency` (same pattern as other dashboard services).

**Router:** `GET /dashboard/new-assets?period=month` — added to `dashboard.py` router.

**Frontend type:** `NewAssetsResponse` in `types/index.ts`:
```typescript
interface NewAssetItem {
  id: string; name: string; icon: string; category_name: string;
  current_value: number; currency: string; created_at: string;
}
interface NewAssetsResponse {
  count: number; period: string; items: NewAssetItem[];
}
```

**Store:** `newAssets = ref<NewAssetsResponse | null>(null)` + `fetchNewAssets(period)` action. Called on mount and on period change (shares period selector state with 资产总值 section — both sections use the same `trendPeriod` ref).

**Layout:**
- Card with title + period selector (same `trendPeriod` ref as 资产总值 — single shared period selector drives both)
- Large count number + "件资产" label
- Mini list of up to 3 most recent assets: icon + name + relative time ("N天前") + value
- Relative time computed from `created_at` using date-fns or manual calculation (no new dep — simple `Math.floor((now - date) / 86400000)` days)
- Empty state via `van-empty` when count is 0

**i18n keys:** `analyticsPage.newAssetsSection`, `analyticsPage.newAssetsUnit` ("件资产"), `analyticsPage.daysAgo` ("{n}天前" / "{n} days ago")

---

### 4. 日均成本

**Data:** `dashboardStore.dailyCostRanking` (already fetched via `fetchDailyCostRanking()`)

**Layout:**
- Card with title
- Ranked list (top 5), each row: rank badge (1=red, 2=orange, 3=yellow, 4+=grey) + icon + name + daily cost right-aligned
- Tapping a row navigates to `/assets/:id`
- Empty state via `van-empty`

This replaces the old `DailyCostCard` with a redesigned ranked list. The underlying data fetch is unchanged.

**i18n keys:** reuse `analyticsPage.dailyCostCard`

---

## 洞悉 Tab

Empty state centered in the tab content area:
- Icon: 🔍 (or `van-icon name="search"`)
- Title: `analyticsPage.insightTitle` ("智能洞悉" / "Smart Insights")
- Subtitle: `analyticsPage.insightPlaceholder` ("即将推出：基于你的资产数据，提供智能分析和建议" / "Coming soon: AI-powered analysis and suggestions")

No data fetching.

---

## i18n Changes

### zh-CN.ts — `analyticsPage` additions

```typescript
analyticsPage: {
  // existing keys preserved unchanged
  title: '资产分析',
  trendCard: '资产趋势',         // keep (used by treemap/pie cards still)
  allocationCard: '资产分布',
  pieCard: '分类占比',
  dailyCostCard: '日均成本排行',
  lowUsageCard: '低使用率资产',
  netWorthChangeCard: '净值变化', // keep (unused but don't delete)
  changeUp: '较上月上涨',
  changeDown: '较上月下跌',
  noChange: '持平',
  trendEntry: '趋势',
  // new keys
  tabTrend: '趋势',
  tabInsight: '洞悉',
  totalAssetsSection: '资产总值',
  assetStatusSection: '资产状态',
  newAssetsSection: '新增资产',
  newAssetsUnit: '件资产',
  daysAgo: '{n}天前',
  insightTitle: '智能洞悉',
  insightPlaceholder: '即将推出：基于你的资产数据，提供智能分析和建议',
}
```

### en-US.ts — mirror additions

```typescript
  tabTrend: 'Trend',
  tabInsight: 'Insights',
  totalAssetsSection: 'Total Assets',
  assetStatusSection: 'Asset Status',
  newAssetsSection: 'New Assets',
  newAssetsUnit: 'assets',
  daysAgo: '{n}d ago',
  insightTitle: 'Smart Insights',
  insightPlaceholder: 'Coming soon: AI-powered analysis and suggestions based on your assets',
```

---

## Dark Mode

All new sections must follow the existing pattern:
- Use CSS variables: `var(--card-bg)`, `var(--text-primary)`, `var(--text-secondary)`, `var(--bg-secondary)`, `var(--separator)`
- Status tile tints use explicit `[data-theme='dark']` overrides in `<style scoped>` (same pattern as existing `.change-indicator` rules in the current file)
- No hardcoded colors except explicit dark-mode overrides under `[data-theme='dark']`
- Tab active color: dark mode uses `var(--color-lavender)` per existing pattern

---

## Data Fetch Strategy

On `onMounted`:
1. `dashboardStore.fetchAll()` — covers overview, statesSummary, allocation, trend, lowUsageAssets (already includes everything except daily cost + new assets)
2. `dashboardStore.fetchDailyCostRanking()` — existing
3. `dashboardStore.fetchNewAssets(trendPeriod.value)` — new

On period change (`trendPeriod`):
- `dashboardStore.fetchTrend(period)`
- `dashboardStore.fetchNewAssets(period)`

Both driven by the same `trendPeriod` ref — the period selector in 资产总值 and 新增资产 sections are visually separate but share state.

---

## Component Structure

No new child components are extracted. All four new sections are implemented inline in `AssetAnalyticsPage.vue`. The existing `TrendLineChartSimple`, `AllocationTreemapChart`, `AllocationPieChart` components are reused as-is.

Rationale: the sections are page-specific, tightly coupled to `dashboardStore`, and not reused elsewhere. Extracting them adds indirection without benefit.

---

## Backend Schema

New Pydantic schemas in `app/schemas/dashboard.py`:

```python
class NewAssetItem(SnowflakeBase):
    id: int
    name: str
    icon: str
    category_name: str
    current_value: float
    currency: str
    created_at: str  # ISO format

class NewAssetsResponse(BaseModel):
    count: int
    period: str
    items: list[NewAssetItem]
```

---

## Out of Scope

- 洞悉 tab content implementation (placeholder only)
- Any changes to existing `AllocationTreemapChart`, `AllocationPieChart`, `LowUsageCard` internals
- Pagination for new assets list (top 3 display is sufficient)
- Investment returns section (not in reference design, not in current page)
