# Analytics Trend/Insight Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `AssetAnalyticsPage.vue` with a 趋势/洞悉 tab bar, adding four new stat sections (资产总值, 资产状态, 新增资产, 日均成本 redesign) and a new backend `GET /dashboard/new-assets` endpoint.

**Architecture:** Add a new backend service function + Pydantic schema + router endpoint for "new assets"; add `NewAssetsResponse` TypeScript type, a `getNewAssets` API function, and a `fetchNewAssets` store action; then replace the flat card list in `AssetAnalyticsPage.vue` with a `van-tabs` layout containing the seven-section 趋势 tab and an 洞悉 empty-state tab.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy (backend); Vue 3 / TypeScript / Vant 4 / ECharts / Pinia (frontend); vitest (frontend tests); pytest (backend tests).

---

## File Map

| File | Change |
|------|--------|
| `server/apps/backend/app/schemas/dashboard.py` | Add `NewAssetItem`, `NewAssetsResponse` |
| `server/apps/backend/app/services/dashboard.py` | Add `get_new_assets()` |
| `server/apps/backend/app/routers/dashboard.py` | Add `GET /new-assets` endpoint |
| `server/tests/backend/test_dashboard.py` | Add `test_dashboard_new_assets_*` tests |
| `frontend/apps/main/src/types/index.ts` | Add `NewAssetItem`, `NewAssetsResponse` |
| `frontend/apps/main/src/api/dashboard.ts` | Add `getNewAssets()` |
| `frontend/apps/main/src/stores/dashboard.ts` | Add `newAssets` ref + `fetchNewAssets()` |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add 9 new `analyticsPage` keys |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | Mirror zh-CN additions |
| `frontend/apps/main/src/pages/AssetAnalyticsPage.vue` | Full page redesign |

---

## Task 1: Backend schemas — NewAssetItem + NewAssetsResponse

**Files:**
- Modify: `server/apps/backend/app/schemas/dashboard.py`

- [ ] **Step 1: Add the two new Pydantic schemas at the end of the file**

  Open `server/apps/backend/app/schemas/dashboard.py` and append after the last class:

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

- [ ] **Step 2: Verify schemas import cleanly**

  ```bash
  cd server/apps/backend
  uv run python -c "from app.schemas.dashboard import NewAssetItem, NewAssetsResponse; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 3: Commit**

  ```bash
  git add server/apps/backend/app/schemas/dashboard.py
  git commit -m "feat(backend/dashboard): add NewAssetItem + NewAssetsResponse schemas"
  ```

---

## Task 2: Backend service — get_new_assets()

**Files:**
- Modify: `server/apps/backend/app/services/dashboard.py`

- [ ] **Step 1: Add the import for `NewAssetsResponse` and `NewAssetItem` to the existing import block**

  In `server/apps/backend/app/services/dashboard.py`, the import from `app.schemas.dashboard` currently lists several names. Add `NewAssetItem` and `NewAssetsResponse` to it:

  ```python
  from apps.backend.app.schemas.dashboard import (
      AllocationItem,
      AllocationResponse,
      DailyCostItem,
      ExpiringSoonItem,
      InvestmentReturnItem,
      LowUsageItem,
      NewAssetItem,
      NewAssetsResponse,
      OverviewResponse,
      TopAssetItem,
      TrendPoint,
      TrendResponse,
  )
  ```

- [ ] **Step 2: Add `get_new_assets()` at the end of the file**

  ```python
  def get_new_assets(db: Session, user: User, period: str = "month") -> NewAssetsResponse:
      default_currency = user.default_currency or "CNY"
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

      items_for_display = assets[:5]
      return NewAssetsResponse(
          count=len(assets),
          period=period,
          items=[
              NewAssetItem(
                  id=a.id,
                  name=a.name,
                  icon=a.category.icon if a.category else "",
                  category_name=a.category.name if a.category else "",
                  current_value=round(
                      ExchangeRateService.convert(
                          a.current_value or 0, a.currency or "CNY", default_currency, db
                      ),
                      2,
                  ),
                  currency=default_currency,
                  created_at=a.created_at.isoformat() if a.created_at else "",
              )
              for a in items_for_display
          ],
      )
  ```

- [ ] **Step 3: Verify the service imports cleanly**

  ```bash
  cd server/apps/backend
  uv run python -c "from app.services.dashboard import get_new_assets; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 4: Commit**

  ```bash
  git add server/apps/backend/app/services/dashboard.py
  git commit -m "feat(backend/dashboard): add get_new_assets service"
  ```

---

## Task 3: Backend router — GET /dashboard/new-assets

**Files:**
- Modify: `server/apps/backend/app/routers/dashboard.py`

- [ ] **Step 1: Add `NewAssetsResponse` to the router's schema import**

  The import block in `server/apps/backend/app/routers/dashboard.py` currently reads:

  ```python
  from apps.backend.app.schemas.dashboard import (
      AllocationResponse,
      DailyCostItem,
      ExpiringSoonItem,
      InvestmentReturnItem,
      LowUsageItem,
      OverviewResponse,
      TopAssetItem,
      TrendResponse,
  )
  ```

  Add `NewAssetsResponse`:

  ```python
  from apps.backend.app.schemas.dashboard import (
      AllocationResponse,
      DailyCostItem,
      ExpiringSoonItem,
      InvestmentReturnItem,
      LowUsageItem,
      NewAssetsResponse,
      OverviewResponse,
      TopAssetItem,
      TrendResponse,
  )
  ```

- [ ] **Step 2: Add the endpoint before the expiring-soon endpoint (keep route specificity order — no path params before `/new-assets`)**

  Insert before `@router.get("/expiring-soon", ...)`:

  ```python
  @router.get("/new-assets", response_model=NewAssetsResponse)
  def get_new_assets(
      period: str = Query("month"),
      db: Session = Depends(get_db),
      user: User = Depends(require_adult),
  ):
      return dashboard_service.get_new_assets(db, user, period)
  ```

- [ ] **Step 3: Verify router loads cleanly**

  ```bash
  cd server/apps/backend
  uv run python -c "from app.routers.dashboard import router; print('ok')"
  ```
  Expected: `ok`

- [ ] **Step 4: Commit**

  ```bash
  git add server/apps/backend/app/routers/dashboard.py
  git commit -m "feat(backend/dashboard): add GET /dashboard/new-assets endpoint"
  ```

---

## Task 4: Backend tests — new-assets endpoint

**Files:**
- Modify: `server/tests/backend/test_dashboard.py`

- [ ] **Step 1: Write failing tests — add at the end of `test_dashboard.py`**

  ```python
  def test_dashboard_new_assets_default_period(client, auth_headers, setup_test_data):
      """新增资产 returns count and items for default month period"""
      response = client.get("/api/v1/dashboard/new-assets", headers=auth_headers)
      assert response.status_code == 200
      data = response.json()["data"]
      assert "count" in data
      assert "period" in data
      assert "items" in data
      assert data["period"] == "month"
      # setup_test_data creates 3 assets — all created just now, so all in last 30 days
      assert data["count"] == 3
      assert len(data["items"]) <= 5
      item = data["items"][0]
      assert "id" in item
      assert "name" in item
      assert "icon" in item
      assert "category_name" in item
      assert "current_value" in item
      assert "currency" in item
      assert "created_at" in item


  def test_dashboard_new_assets_quarter_period(client, auth_headers, setup_test_data):
      """period=quarter is accepted and returns same assets (all recent)"""
      response = client.get(
          "/api/v1/dashboard/new-assets", headers=auth_headers, params={"period": "quarter"}
      )
      assert response.status_code == 200
      data = response.json()["data"]
      assert data["period"] == "quarter"
      assert data["count"] == 3


  def test_dashboard_new_assets_year_period(client, auth_headers, setup_test_data):
      """period=year is accepted and returns same assets (all recent)"""
      response = client.get(
          "/api/v1/dashboard/new-assets", headers=auth_headers, params={"period": "year"}
      )
      assert response.status_code == 200
      data = response.json()["data"]
      assert data["period"] == "year"
      assert data["count"] == 3


  def test_dashboard_new_assets_empty(client, auth_headers):
      """Returns count=0 and empty items when no assets exist"""
      response = client.get("/api/v1/dashboard/new-assets", headers=auth_headers)
      assert response.status_code == 200
      data = response.json()["data"]
      assert data["count"] == 0
      assert data["items"] == []


  def test_dashboard_new_assets_requires_auth(client):
      """Endpoint rejects unauthenticated requests"""
      response = client.get("/api/v1/dashboard/new-assets")
      assert response.status_code == 401
  ```

- [ ] **Step 2: Run tests to verify they pass**

  ```bash
  cd server
  uv run pytest tests/backend/test_dashboard.py -v -k "new_assets"
  ```
  Expected: all 5 tests PASS

- [ ] **Step 3: Commit**

  ```bash
  git add server/tests/backend/test_dashboard.py
  git commit -m "test(backend/dashboard): add new-assets endpoint tests"
  ```

---

## Task 5: Frontend types

**Files:**
- Modify: `frontend/apps/main/src/types/index.ts`

- [ ] **Step 1: Add the two new interfaces after `StatesSummaryResponse`**

  Open `frontend/apps/main/src/types/index.ts`. After the `StatesSummaryResponse` interface (currently the last dashboard type), append:

  ```typescript
  export interface NewAssetItem {
    id: string
    name: string
    icon: string
    category_name: string
    current_value: number
    currency: string
    created_at: string
  }

  export interface NewAssetsResponse {
    count: number
    period: string
    items: NewAssetItem[]
  }
  ```

- [ ] **Step 2: Typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/apps/main/src/types/index.ts
  git commit -m "feat(frontend/types): add NewAssetItem + NewAssetsResponse"
  ```

---

## Task 6: Frontend API function

**Files:**
- Modify: `frontend/apps/main/src/api/dashboard.ts`

- [ ] **Step 1: Add `NewAssetsResponse` to the existing type import at the top of the file**

  The current import line reads:
  ```typescript
  import type { DashboardOverview, AllocationResponse, TrendResponse, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset, HomeAssetsPageResponse } from '@/types'
  ```

  Add `NewAssetsResponse`:
  ```typescript
  import type { DashboardOverview, AllocationResponse, TrendResponse, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset, HomeAssetsPageResponse, NewAssetsResponse } from '@/types'
  ```

- [ ] **Step 2: Add the API function at the end of the file (before the `ActivityItem` interface)**

  Insert before `export interface ActivityItem {`:

  ```typescript
  export function getNewAssets(period: 'month' | 'quarter' | 'year' = 'month') {
    return http.get<NewAssetsResponse>('/dashboard/new-assets', { params: { period } })
  }
  ```

- [ ] **Step 3: Typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/apps/main/src/api/dashboard.ts
  git commit -m "feat(frontend/api): add getNewAssets"
  ```

---

## Task 7: Pinia store — newAssets ref + fetchNewAssets action

**Files:**
- Modify: `frontend/apps/main/src/stores/dashboard.ts`

- [ ] **Step 1: Add `NewAssetsResponse` to the type import**

  The current import line reads:
  ```typescript
  import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset } from '@/types'
  ```

  Add `NewAssetsResponse`:
  ```typescript
  import type { DashboardOverview, AllocationItem, TrendPoint, DailyCostItem, InvestmentReturnItem, TopAssetItem, LowUsageItem, StatesSummaryResponse, Asset, NewAssetsResponse } from '@/types'
  ```

- [ ] **Step 2: Add the `newAssets` ref alongside the other refs (after `statesSummary`)**

  Find the line `const statesSummary = ref<StatesSummaryResponse | null>(null)` and add after it:

  ```typescript
  const newAssets = ref<NewAssetsResponse | null>(null)
  ```

- [ ] **Step 3: Add `fetchNewAssets` action after `fetchStatesSummary`**

  Find `async function fetchStatesSummary()` and add after its closing brace:

  ```typescript
  async function fetchNewAssets(period: 'month' | 'quarter' | 'year' = 'month') {
    const res = await dashboardApi.getNewAssets(period)
    newAssets.value = res.data
  }
  ```

- [ ] **Step 4: Add `newAssets` and `fetchNewAssets` to the return object**

  Find the `return {` block. Add `newAssets` to the state section and `fetchNewAssets` to the action section:

  ```typescript
  return {
    overview, allocation, allocationTotal, trend, topAssets, dailyCostRanking,
    lowUsageAssets, expiringSoonAssets, investmentReturns, recentActivities, statesSummary,
    newAssets,   // ← add
    homeAssets, loading,
    // ... rest unchanged ...
    fetchOverview, fetchAllocation, fetchTrend, fetchTopAssets,
    fetchDailyCostRanking, fetchLowUsageAssets, fetchExpiringSoonAssets, fetchInvestmentReturns,
    fetchRecentActivities, fetchStatesSummary,
    fetchNewAssets,   // ← add
    fetchHomeAssets, fetchAll,
    // ... rest unchanged ...
  }
  ```

- [ ] **Step 5: Add `newAssets` to `invalidateDashboard`**

  Find the `invalidateDashboard()` function body and add:
  ```typescript
  newAssets.value = null
  ```
  alongside the other null-resets.

- [ ] **Step 6: Typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 7: Commit**

  ```bash
  git add frontend/apps/main/src/stores/dashboard.ts
  git commit -m "feat(frontend/store): add newAssets ref + fetchNewAssets action"
  ```

---

## Task 8: i18n — zh-CN additions

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

- [ ] **Step 1: Add 9 new keys to the `analyticsPage` section**

  The current `analyticsPage` section ends at:
  ```typescript
    trendEntry: '趋势',
  },
  ```

  Replace that closing with:
  ```typescript
    trendEntry: '趋势',
    tabTrend: '趋势',
    tabInsight: '洞悉',
    totalAssetsSection: '资产总值',
    assetStatusSection: '资产状态',
    newAssetsSection: '新增资产',
    newAssetsUnit: '件资产',
    daysAgo: '{n}天前',
    insightTitle: '智能洞悉',
    insightPlaceholder: '即将推出：基于你的资产数据，提供智能分析和建议',
  },
  ```

- [ ] **Step 2: Typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/apps/main/src/i18n/locales/zh-CN.ts
  git commit -m "feat(i18n/zh-CN): add analyticsPage tab/section keys"
  ```

---

## Task 9: i18n — en-US additions

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Add the same 9 keys in English**

  The current `analyticsPage` section ends at:
  ```typescript
    trendEntry: 'Trend',
  },
  ```

  Replace that closing with:
  ```typescript
    trendEntry: 'Trend',
    tabTrend: 'Trend',
    tabInsight: 'Insights',
    totalAssetsSection: 'Total Assets',
    assetStatusSection: 'Asset Status',
    newAssetsSection: 'New Assets',
    newAssetsUnit: 'assets',
    daysAgo: '{n}d ago',
    insightTitle: 'Smart Insights',
    insightPlaceholder: 'Coming soon: AI-powered analysis and suggestions based on your assets',
  },
  ```

- [ ] **Step 2: Typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/apps/main/src/i18n/locales/en-US.ts
  git commit -m "feat(i18n/en-US): add analyticsPage tab/section keys"
  ```

---

## Task 10: AssetAnalyticsPage.vue — full redesign

**Files:**
- Modify: `frontend/apps/main/src/pages/AssetAnalyticsPage.vue`

This task replaces the entire file. The new file content is given in full below.

- [ ] **Step 1: Replace the full content of `AssetAnalyticsPage.vue`**

  ```vue
  <template>
    <div class="analytics-page">
      <PageHeader :title="t('analyticsPage.title')" />

      <van-tabs
        v-model:active="activeTab"
        type="line"
        class="page-tabs"
        :color="tabActiveColor"
        title-active-color="var(--text-primary)"
        title-inactive-color="var(--text-secondary)"
      >
        <!-- ── 趋势 tab ── -->
        <van-tab :title="t('analyticsPage.tabTrend')" name="trend">
          <div class="tab-content">

            <!-- Section 1: 资产总值 -->
            <div class="section-card">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.totalAssetsSection') }}</span>
                <van-tabs
                  v-model:active="trendPeriod"
                  type="card"
                  shrink
                  @change="onPeriodChange"
                >
                  <van-tab title="月" name="month" />
                  <van-tab title="季" name="quarter" />
                  <van-tab title="年" name="year" />
                </van-tabs>
              </div>
              <div class="net-worth-value">
                {{ formatMoney(dashboardStore.overview?.net_worth) }}
              </div>
              <div
                v-if="monthOverMonthChange !== null"
                class="change-badge"
                :class="changeClass"
              >
                {{ changeArrow }} {{ Math.abs(monthOverMonthChange).toFixed(1) }}%
                {{ changeLabel }}
              </div>
              <div class="chart-area">
                <TrendLineChartSimple
                  v-if="dashboardStore.trend.length"
                  :data="dashboardStore.trend"
                />
                <van-empty v-else :description="t('common.noData')" image-size="60" />
              </div>
            </div>

            <!-- Section 2: 资产状态 -->
            <div class="section-card">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.assetStatusSection') }}</span>
              </div>
              <div v-if="dashboardStore.statesSummary" class="status-grid">
                <div class="status-tile status-tile--in-use">
                  <div class="status-count">
                    {{ dashboardStore.statesSummary.states['in_use']?.count ?? 0 }}
                  </div>
                  <div class="status-label">{{ t('statusGrid.inUse') }}</div>
                </div>
                <div class="status-tile status-tile--idle">
                  <div class="status-count">
                    {{ dashboardStore.statesSummary.states['idle']?.count ?? 0 }}
                  </div>
                  <div class="status-label">{{ t('statusGrid.idle') }}</div>
                </div>
                <div class="status-tile status-tile--sold">
                  <div class="status-count">
                    {{ dashboardStore.statesSummary.states['sold']?.count ?? 0 }}
                  </div>
                  <div class="status-label">{{ t('statusGrid.sold') }}</div>
                </div>
                <div class="status-tile status-tile--retired">
                  <div class="status-count">
                    {{ dashboardStore.statesSummary.states['retired']?.count ?? 0 }}
                  </div>
                  <div class="status-label">{{ t('statusGrid.retired') }}</div>
                </div>
              </div>
              <van-empty v-else :description="t('common.noData')" image-size="60" />
            </div>

            <!-- Section 3: 新增资产 -->
            <div class="section-card">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.newAssetsSection') }}</span>
              </div>
              <div class="new-assets-count">
                <span class="count-number">{{ dashboardStore.newAssets?.count ?? 0 }}</span>
                <span class="count-unit">{{ t('analyticsPage.newAssetsUnit') }}</span>
              </div>
              <template v-if="dashboardStore.newAssets && dashboardStore.newAssets.items.length">
                <div
                  v-for="item in dashboardStore.newAssets.items.slice(0, 3)"
                  :key="item.id"
                  class="new-asset-row"
                >
                  <div class="new-asset-left">
                    <span class="new-asset-icon">{{ item.icon || '📦' }}</span>
                    <div class="new-asset-info">
                      <div class="new-asset-name">{{ item.name }}</div>
                      <div class="new-asset-date">{{ daysAgo(item.created_at) }}</div>
                    </div>
                  </div>
                  <div class="new-asset-value">{{ formatMoney(item.current_value) }}</div>
                </div>
              </template>
              <van-empty
                v-else-if="dashboardStore.newAssets?.count === 0"
                :description="t('common.noData')"
                image-size="60"
              />
            </div>

            <!-- Section 4: 日均成本 -->
            <div class="section-card">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.dailyCostCard') }}</span>
              </div>
              <template v-if="dashboardStore.dailyCostRanking.length">
                <div
                  v-for="(item, index) in dashboardStore.dailyCostRanking.slice(0, 5)"
                  :key="item.id"
                  class="cost-row"
                  @click="router.push(`/assets/${item.id}`)"
                >
                  <div class="cost-row-left">
                    <span class="rank-badge" :class="rankClass(index)">{{ index + 1 }}</span>
                    <span class="cost-icon">{{ item.icon || '📦' }}</span>
                    <span class="cost-name">{{ item.name }}</span>
                  </div>
                  <span class="cost-value">{{ formatMoney(item.daily_cost) }}/天</span>
                </div>
              </template>
              <van-empty v-else :description="t('common.noData')" image-size="60" />
            </div>

            <!-- Section 5: 资产分布 (kept — unique content) -->
            <div class="section-card">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.allocationCard') }}</span>
              </div>
              <div class="card-content">
                <AllocationTreemapChart
                  v-if="dashboardStore.allocation.length"
                  :data="dashboardStore.allocation"
                />
                <van-empty v-else :description="t('common.noData')" image-size="60" />
              </div>
            </div>

            <!-- Section 6: 分类占比 (kept — unique content) -->
            <div class="section-card">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.pieCard') }}</span>
              </div>
              <div class="card-content pie-content">
                <AllocationPieChart
                  v-if="dashboardStore.allocation.length"
                  :data="dashboardStore.allocation"
                  class="pie-chart-embedded"
                />
                <van-empty v-else :description="t('common.noData')" image-size="60" />
              </div>
            </div>

            <!-- Section 7: 低使用率资产 (kept — unique content) -->
            <div class="section-card section-card--compact">
              <div class="card-header">
                <span class="card-title">{{ t('analyticsPage.lowUsageCard') }}</span>
              </div>
              <div class="card-content">
                <template v-if="lowUsageAssets.length">
                  <van-cell
                    v-for="item in lowUsageAssets.slice(0, 5)"
                    :key="item.id"
                    :title="item.name"
                    is-link
                    @click="router.push(`/assets/${item.id}`)"
                  >
                    <template #value>
                      <van-tag type="warning" size="medium">{{ usageLabel(item.usage_frequency) }}</van-tag>
                    </template>
                  </van-cell>
                </template>
                <van-empty v-else :description="t('common.noData')" image-size="60" />
              </div>
            </div>

          </div>
        </van-tab>

        <!-- ── 洞悉 tab ── -->
        <van-tab :title="t('analyticsPage.tabInsight')" name="insight">
          <div class="insight-empty">
            <div class="insight-icon">🔍</div>
            <div class="insight-title">{{ t('analyticsPage.insightTitle') }}</div>
            <div class="insight-subtitle">{{ t('analyticsPage.insightPlaceholder') }}</div>
          </div>
        </van-tab>
      </van-tabs>

      <div class="bottom-spacer" />
    </div>
  </template>

  <script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRouter } from 'vue-router'
  import { useDashboardStore } from '@/stores/dashboard'
  import PageHeader from '@/components/common/PageHeader.vue'
  import TrendLineChartSimple from '@/components/charts/TrendLineChartSimple.vue'
  import AllocationTreemapChart from '@/components/charts/AllocationTreemapChart.vue'
  import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'
  import { formatCurrency } from '@/utils/format'

  const { t } = useI18n()
  const router = useRouter()
  const dashboardStore = useDashboardStore()

  const activeTab = ref<'trend' | 'insight'>('trend')
  const trendPeriod = ref<'month' | 'quarter' | 'year'>('month')

  // dark-mode-aware tab active color
  const tabActiveColor = computed(() => {
    return document.documentElement.getAttribute('data-theme') === 'dark'
      ? 'var(--color-lavender)'
      : 'var(--van-primary-color)'
  })

  const monthOverMonthChange = computed(() => dashboardStore.overview?.month_over_month_change ?? null)
  const lowUsageAssets = computed(() =>
    dashboardStore.lowUsageAssets.filter((a) => a.usage_frequency === 'idle'),
  )

  const changeClass = computed(() => {
    const val = monthOverMonthChange.value
    if (val === null) return ''
    return val >= 0 ? 'change-up' : 'change-down'
  })

  const changeArrow = computed(() => {
    const val = monthOverMonthChange.value
    if (val === null) return ''
    return val >= 0 ? '▲' : '▼'
  })

  const changeLabel = computed(() => {
    const val = monthOverMonthChange.value
    if (val === null) return ''
    return val >= 0 ? t('analyticsPage.changeUp') : t('analyticsPage.changeDown')
  })

  function formatMoney(value: number | string | undefined | null): string {
    if (value === undefined || value === null) return '¥0'
    const num = typeof value === 'string' ? parseFloat(value) : value
    if (isNaN(num)) return '¥0'
    return formatCurrency(num)
  }

  function daysAgo(isoDate: string): string {
    const days = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000)
    return t('analyticsPage.daysAgo', { n: days })
  }

  function usageLabel(frequency: string): string {
    return frequency === 'idle' ? t('statusGrid.idle') : frequency
  }

  function rankClass(index: number): string {
    if (index === 0) return 'rank-badge--first'
    if (index === 1) return 'rank-badge--second'
    if (index === 2) return 'rank-badge--third'
    return 'rank-badge--rest'
  }

  function onPeriodChange(period: 'month' | 'quarter' | 'year') {
    trendPeriod.value = period
    dashboardStore.fetchTrend(period)
    dashboardStore.fetchNewAssets(period)
  }

  onMounted(async () => {
    await dashboardStore.fetchAll()
    dashboardStore.fetchDailyCostRanking()
    dashboardStore.fetchTrend(trendPeriod.value)
    dashboardStore.fetchNewAssets(trendPeriod.value)
  })
  </script>

  <style scoped>
  .analytics-page {
    background: var(--bg-secondary);
    min-height: 100vh;
  }

  /* ── Page-level tab bar ── */
  .page-tabs :deep(.van-tabs__wrap) {
    background: var(--card-bg);
    border-bottom: 1px solid var(--separator);
  }

  .page-tabs :deep(.van-tab) {
    font-size: 15px;
    font-weight: 500;
  }

  .page-tabs :deep(.van-tab--active) {
    font-weight: 600;
  }

  /* Tab active line inherits color from :color prop above */

  /* ── Shared card container ── */
  .tab-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }

  .section-card {
    background: var(--card-bg);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(1, 1, 32, 0.08);
    padding: 0 0 12px;
  }

  [data-theme='dark'] .section-card {
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px 10px;
  }

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .card-content {
    padding: 0 12px;
  }

  .pie-content .pie-chart-embedded :deep(.chart-title) {
    display: none;
  }
  .pie-content .pie-chart-embedded :deep(.allocation-chart) {
    padding: 0;
    margin: 0;
  }

  /* Period card-tabs inside card header — reuse existing pattern */
  .card-header :deep(.van-tabs--card) {
    .van-tabs__nav {
      height: 26px;
      background: var(--van-background-2);
      border-radius: 4px;
    }
    .van-tab {
      font-size: 11px;
      padding: 0 8px;
      line-height: 26px;
      border-radius: 4px;
    }
    .van-tab--active {
      background: var(--van-primary-color);
      color: var(--color-on-primary);
    }
  }

  [data-theme='dark'] .card-header :deep(.van-tabs--card) {
    .van-tabs__nav {
      background: rgba(255, 255, 255, 0.08);
    }
    .van-tab--active {
      background: var(--color-lavender);
      color: #010120;
    }
  }

  /* ── Section 1: 资产总值 ── */
  .net-worth-value {
    font-size: 26px;
    font-weight: 700;
    color: var(--text-primary);
    padding: 0 16px 4px;
    letter-spacing: -0.5px;
  }

  .change-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 4px;
    margin: 0 16px 10px;
  }

  .change-badge.change-up {
    background: rgba(5, 150, 105, 0.08);
    color: #059669;
  }

  [data-theme='dark'] .change-badge.change-up {
    background: rgba(110, 231, 160, 0.12);
    color: #6ee7a0;
  }

  .change-badge.change-down {
    background: rgba(220, 38, 38, 0.08);
    color: #dc2626;
  }

  [data-theme='dark'] .change-badge.change-down {
    background: rgba(252, 165, 165, 0.12);
    color: #fca5a5;
  }

  .chart-area {
    padding: 0 12px;
  }

  /* ── Section 2: 资产状态 ── */
  .status-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    padding: 0 12px;
  }

  .status-tile {
    border-radius: 8px;
    padding: 12px;
    text-align: center;
  }

  .status-count {
    font-size: 22px;
    font-weight: 700;
    line-height: 1.2;
  }

  .status-label {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 4px;
  }

  .status-tile--in-use {
    background: rgba(5, 150, 105, 0.08);
  }
  .status-tile--in-use .status-count { color: #059669; }

  [data-theme='dark'] .status-tile--in-use {
    background: rgba(110, 231, 160, 0.12);
  }
  [data-theme='dark'] .status-tile--in-use .status-count { color: #6ee7a0; }

  .status-tile--idle {
    background: rgba(250, 140, 22, 0.08);
  }
  .status-tile--idle .status-count { color: #fa8c16; }

  [data-theme='dark'] .status-tile--idle {
    background: rgba(251, 191, 36, 0.12);
  }
  [data-theme='dark'] .status-tile--idle .status-count { color: #fbbf24; }

  .status-tile--sold {
    background: rgba(59, 130, 246, 0.08);
  }
  .status-tile--sold .status-count { color: #3b82f6; }

  [data-theme='dark'] .status-tile--sold {
    background: rgba(147, 197, 253, 0.12);
  }
  [data-theme='dark'] .status-tile--sold .status-count { color: #93c5fd; }

  .status-tile--retired {
    background: var(--bg-secondary);
  }
  .status-tile--retired .status-count { color: var(--text-secondary); }

  /* ── Section 3: 新增资产 ── */
  .new-assets-count {
    display: flex;
    align-items: baseline;
    gap: 6px;
    padding: 0 16px 10px;
  }

  .count-number {
    font-size: 30px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -1px;
  }

  .count-unit {
    font-size: 13px;
    color: var(--text-secondary);
  }

  .new-asset-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    margin: 0 4px 4px;
    background: var(--bg-secondary);
    border-radius: 8px;
  }

  .new-asset-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .new-asset-icon {
    font-size: 18px;
    line-height: 1;
  }

  .new-asset-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .new-asset-date {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 2px;
  }

  .new-asset-value {
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 500;
  }

  /* ── Section 4: 日均成本 ── */
  .cost-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    cursor: pointer;
  }

  .cost-row:active {
    background: var(--bg-secondary);
  }

  .cost-row-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .rank-badge {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
  }

  .rank-badge--first  { background: #ff4d4f; }
  .rank-badge--second { background: #fa8c16; }
  .rank-badge--third  { background: #fadb14; color: #333; }
  .rank-badge--rest   { background: var(--text-secondary); }

  .cost-icon {
    font-size: 18px;
    line-height: 1;
  }

  .cost-name {
    font-size: 13px;
    color: var(--text-primary);
  }

  .cost-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }

  /* ── 洞悉 empty state ── */
  .insight-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 60vh;
    gap: 16px;
    padding: 24px;
    text-align: center;
  }

  .insight-icon {
    font-size: 48px;
    line-height: 1;
  }

  .insight-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .insight-subtitle {
    font-size: 14px;
    color: var(--text-secondary);
    max-width: 260px;
    line-height: 1.6;
  }

  /* ── Bottom spacer ── */
  .bottom-spacer {
    height: 60px;
  }

  /* ── Tablet 2-col layout ── */
  @media (min-width: 768px) {
    .tab-content {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }
    .section-card:first-child {
      grid-column: span 2;
    }
  }
  </style>
  ```

- [ ] **Step 2: Typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 3: Lint**

  ```bash
  cd frontend/apps/main
  npm run lint
  ```
  Expected: no errors (auto-fix trivial issues with `npm run lint:fix` if needed)

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/apps/main/src/pages/AssetAnalyticsPage.vue
  git commit -m "feat(analytics): redesign page with trend/insight tabs and 4 new sections"
  ```

---

## Task 11: Final verification

- [ ] **Step 1: Run all backend dashboard tests**

  ```bash
  cd server
  uv run pytest tests/backend/test_dashboard.py -v
  ```
  Expected: all tests PASS

- [ ] **Step 2: Run frontend typecheck**

  ```bash
  cd frontend/apps/main
  npm run typecheck
  ```
  Expected: no errors

- [ ] **Step 3: Run frontend tests**

  ```bash
  cd frontend/apps/main
  npm run test:run
  ```
  Expected: all tests PASS (existing tests unaffected)

- [ ] **Step 4: Commit if any fixups made**

  If any issues were fixed in steps 1-3, commit them now with an appropriate message.
