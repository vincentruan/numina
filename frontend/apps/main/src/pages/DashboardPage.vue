<template>
  <div class="dashboard-page" role="main" aria-label="家庭资产总览">
    <!-- Skeleton Loading State -->
    <DashboardSkeleton v-if="dashboardStore.loading && !overview?.asset_count" />

    <van-pull-refresh v-else v-model="refreshing" @refresh="onRefresh">
      <!-- Empty State for new users -->
      <div v-if="!dashboardStore.loading && overview?.asset_count === 0" class="empty-dashboard">
        <van-empty description="开始记录你的第一项资产">
          <van-button type="primary" size="small" @click="$router.push('/assets/new')">
            添加资产
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <!-- Overview Card -->
        <NetWorthCard
          ref="overviewCardRef"
          :net-worth="overview?.net_worth || 0"
          :total-assets="overview?.total_assets || 0"
          :total-liabilities="overview?.total_liabilities || 0"
          :total-daily-cost="overview?.total_daily_cost || 0"
          :asset-count="overview?.asset_count || 0"
          :month-over-month-change="overview?.month_over_month_change"
        />

        <!-- Smart Reminders (includes expiring soon + idle + AI reminders) -->
        <SmartRemindersCard
          :idle-assets="dashboardStore.lowUsageAssets.filter(a => a.usage_frequency === 'idle')"
          :expiring-assets="dashboardStore.expiringSoonAssets"
          @select-status="onStatusSelect"
        />

        <!-- Trend Chart -->
        <van-cell-group inset class="chart-section">
          <van-collapse v-model="trendExpanded" @change="toggleTrend">
            <van-collapse-item title="资产趋势" name="trend">
              <TrendLineChart v-if="dashboardStore.trend.length" :data="dashboardStore.trend" @period-change="onTrendPeriodChange" />
              <van-empty v-else description="暂无数据" image-size="60" />
            </van-collapse-item>
          </van-collapse>
        </van-cell-group>

        <!-- Allocation Chart -->
        <van-cell-group inset class="chart-section">
          <van-collapse v-model="allocationExpanded" @change="toggleAllocation">
            <van-collapse-item title="资产分布" name="allocation">
              <AllocationPieChart v-if="dashboardStore.allocation.length" :data="dashboardStore.allocation" />
              <van-empty v-else description="暂无数据" image-size="60" />
            </van-collapse-item>
          </van-collapse>
        </van-cell-group>

        <!-- Status Summary Grid + Toolbar -->
        <StatusSummaryGrid
          :summary="dashboardStore.statesSummary"
          :active-status="activeStatus"
          @select="onStatusSelect"
        >
          <template #toolbar>
            <van-icon name="checked" @click="enterSelectionMode" />
          </template>
        </StatusSummaryGrid>

        <!-- Category Navigation (Sticky, shown when scrolled) -->
        <div v-if="showCategoryNav && categoriesWithAssetCount.length > 0" class="category-nav-sticky">
          <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
            <van-tab title="全部" />
            <van-tab
              v-for="cat in categoriesWithAssetCount"
              :key="cat.id"
              :title="`${cat.name} (${cat.count})`"
            />
          </van-tabs>
        </div>

        <!-- Asset List (Normal Mode) -->
        <div v-if="!selectionMode" class="asset-section">
          <div class="section-header">
            <span class="section-title">{{ sectionTitle }}</span>
          </div>

          <!-- Asset List -->
          <template v-if="filteredByCategoryAssets.length">
            <van-list
              v-model:loading="loadingMore"
              :finished="dashboardStore.assetListFinished"
              finished-text="没有更多了"
              @load="onLoadMore"
            >
              <div class="asset-list">
                <template v-if="viewMode === 'list'">
                  <AssetListItem
                    v-for="asset in filteredByCategoryAssets"
                    :key="asset.id"
                    :asset="asset"
                    @click="$router.push(`/assets/${asset.id}`)"
                  />
                </template>
                <template v-else>
                  <AssetCard
                    v-for="asset in filteredByCategoryAssets"
                    :key="asset.id"
                    :asset="asset"
                    @click="$router.push(`/assets/${asset.id}`)"
                  />
                </template>
              </div>
            </van-list>
          </template>

          <van-empty v-else description="暂无资产" image-size="60" />
        </div>

        <!-- Selection Mode -->
        <div v-else class="selection-mode">
          <div class="selection-header">
            <van-checkbox v-model="selectAll" @change="toggleSelectAll">全选</van-checkbox>
            <span class="selection-count">已选 {{ selectedIds.length }} 项</span>
            <van-button type="primary" size="small" @click="exitSelectionMode">完成</van-button>
          </div>
          <div class="selection-list-cards">
            <template v-if="viewMode === 'list'">
              <AssetListItem
                v-for="asset in dashboardStore.displayedAssets"
                :key="asset.id"
                :asset="asset"
                :selectable="true"
                :selected="selectedIds.includes(asset.id)"
                @click="toggleSelection(asset.id)"
              />
            </template>
            <template v-else>
              <AssetCard
                v-for="asset in dashboardStore.displayedAssets"
                :key="asset.id"
                :asset="asset"
                :selectable="true"
                :selected="selectedIds.includes(asset.id)"
                @click="toggleSelection(asset.id)"
              />
            </template>
          </div>
          <div class="selection-actions">
            <van-button icon="share-o" @click="handleBatchShare">分享</van-button>
            <van-button icon="delete-o" @click="handleBatchDelete">删除</van-button>
            <van-button icon="label-o" @click="handleBatchCategory">分类</van-button>
            <van-button icon="tag-o" @click="handleBatchTag">标签</van-button>
            <van-button icon="ellipsis" @click="showMoreActions = true">更多</van-button>
          </div>
        </div>
      </template>

      <div class="bottom-spacer" />
    </van-pull-refresh>

    <!-- FAB Menu -->
    <template v-if="!selectionMode">
      <!-- Backdrop -->
      <transition name="fab-backdrop">
        <div v-if="fabMenuOpen" class="fab-backdrop" aria-hidden="true" @click="fabMenuOpen = false" />
      </transition>
      <!-- Menu items -->
      <transition name="fab-menu">
        <div v-if="fabMenuOpen" class="fab-menu" role="menu" aria-label="快捷操作">
          <button
            class="fab-menu-item"
            role="menuitem"
            @click="onFabAction('import')"
          >
            <span class="fab-menu-label">{{ t('dashboard.fabImportBill') }}</span>
            <span class="fab-menu-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
            </span>
          </button>
          <button
            class="fab-menu-item"
            role="menuitem"
            @click="onFabAction('add')"
          >
            <span class="fab-menu-label">{{ t('dashboard.fabAddAsset') }}</span>
            <span class="fab-menu-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/><line x1="12" y1="12" x2="12" y2="17"/><line x1="9.5" y1="14.5" x2="14.5" y2="14.5"/></svg>
            </span>
          </button>
        </div>
      </transition>
      <!-- FAB button -->
      <button
        class="fab"
        :class="{ 'fab--open': fabMenuOpen }"
        :aria-label="fabMenuOpen ? t('common.close') : t('dashboard.fabAddAsset')"
        :aria-expanded="fabMenuOpen"
        aria-haspopup="menu"
        @click="fabMenuOpen = !fabMenuOpen"
      >
        <van-icon name="plus" size="22" class="fab-icon" />
      </button>
    </template>

    <!-- More Actions Sheet -->
    <van-action-sheet
      v-model:show="showMoreActions"
      :actions="moreActions"
      cancel-text="取消"
      @select="onMoreActionSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { showToast, showConfirmDialog, showLoadingToast, closeToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useChoreStore } from '@/stores/chore'
import { batchArchiveAssets, batchUpdateStatus, batchExportAssets } from '@/api/assets'
import { generateAssetCard, generateSummaryCard, downloadImage } from '@/utils/shareImage'
import NetWorthCard from '@/components/dashboard/NetWorthCard.vue'
import StatusSummaryGrid from '@/components/dashboard/StatusSummaryGrid.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'
import SmartRemindersCard from '@/components/dashboard/SmartRemindersCard.vue'

const { t } = useI18n()
const router = useRouter()

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const choreStore = useChoreStore()
const viewMode = computed(() => authStore.user?.view_mode || 'card')
const refreshing = ref(false)
const activeStatus = ref<string | null>(null)
const overviewCardRef = ref()

// Chart collapse state (van-collapse v-model expects array of active names)
const trendExpanded = ref<string[]>(localStorage.getItem('dashboard_trend_expanded') === 'false' ? [] : ['trend'])
const allocationExpanded = ref<string[]>(localStorage.getItem('dashboard_allocation_expanded') === 'true' ? ['allocation'] : [])

// Pagination state
const loadingMore = ref(false)

// Category view
const showCategoryNav = ref(false)
const activeCategoryIndex = ref(0)
const activeCategoryId = ref<string | null>(null)  // null = show all

// Selection mode
const selectionMode = ref(false)
const selectedIds = ref<string[]>([])
const selectAll = ref(false)

// Toolbar
const showMoreActions = ref(false)

// FAB menu
const fabMenuOpen = ref(false)

function onFabAction(action: 'add' | 'import') {
  fabMenuOpen.value = false
  if (action === 'add') {
    router.push('/assets/new')
  } else {
    router.push('/settings/import-report')
  }
}

const overview = computed(() => dashboardStore.overview)
// Category counts from backend (full counts, not page-limited)
const categoriesWithAssetCount = computed(() => {
  return dashboardStore.categoryCounts
    .map(c => ({ id: c.id, name: c.name, icon: c.icon, count: c.count }))
    .sort((a, b) => b.count - a.count)
})

// Asset list: displayedAssets is already filtered by backend (status + optional category)
const filteredByCategoryAssets = computed(() => dashboardStore.displayedAssets)

const statusLabelMap: Record<string, string> = {
  in_use: '服役中',
  idle: '闲置',
  sold: '已出售',
  retired: '已退役'
}

// More actions
const moreActions = [
  { name: '转为退役', value: 'retire' },
  { name: '转为服役', value: 'activate' },
  { name: '导出', value: 'export' },
]

const sectionTitle = computed(() => {
  const status = activeStatus.value || 'in_use'
  const pageInfo = dashboardStore.assetPageInfo.get(status)
  // Use server-side total count when available, fallback to displayed assets count
  const count = pageInfo ? pageInfo.total : dashboardStore.displayedAssets.length
  if (!activeStatus.value) {
    return `资产列表 (${count})`
  }
  const label = statusLabelMap[activeStatus.value] || activeStatus.value
  return `${label} (${count})`
})

function onCategoryChange(index: number) {
  activeCategoryIndex.value = index
  const targetStatus = activeStatus.value || 'in_use'
  if (index === 0) {
    activeCategoryId.value = null  // "全部" tab
    dashboardStore.resetAssetPagination(targetStatus)
    dashboardStore.fetchAssetsPage(targetStatus, 1, 20, '')
  } else {
    const category = categoriesWithAssetCount.value[index - 1]
    if (!category) return
    activeCategoryId.value = category.id
    dashboardStore.resetAssetPagination(targetStatus)
    dashboardStore.fetchAssetsPage(targetStatus, 1, 20, category.id)
  }
}

function onStatusSelect(status: string | null) {
  activeStatus.value = status
  activeCategoryId.value = null
  activeCategoryIndex.value = 0
  const targetStatus = status || 'in_use'
  dashboardStore.resetAssetPagination(targetStatus)
  dashboardStore.fetchAssetsPage(targetStatus, 1, 20, '')
  dashboardStore.fetchCategoryCounts(targetStatus)
}

// Selection mode functions
function enterSelectionMode() {
  selectionMode.value = true
  selectedIds.value = []
  selectAll.value = false
}

function exitSelectionMode() {
  selectionMode.value = false
  selectedIds.value = []
  selectAll.value = false
}

function toggleSelectAll() {
  if (selectAll.value) {
    selectedIds.value = dashboardStore.displayedAssets.map(a => a.id)
  } else {
    selectedIds.value = []
  }
}

function toggleSelection(id: string) {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
  selectAll.value = selectedIds.value.length === dashboardStore.displayedAssets.length
}

async function handleBatchShare() {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }

  showLoadingToast({
    message: '生成分享图片中...',
    forbidClick: true,
    duration: 0,
  })

  try {
    const selectedAssets = dashboardStore.displayedAssets.filter(a => selectedIds.value.includes(a.id))

    let blob: Blob
    let title: string

    if (selectedAssets.length === 1) {
      // 单个资产：生成资产卡片
      blob = await generateAssetCard(selectedAssets[0])
      title = `${selectedAssets[0].name} - 资产卡片`
    } else {
      // 多个资产：生成汇总卡片
      blob = await generateSummaryCard(selectedAssets)
      title = `我的资产汇总 (${selectedAssets.length}件)`
    }

    closeToast()

    // Download the image
    downloadImage(blob, `${title}.png`)
    showToast(t('toast.imageSaved'))
    exitSelectionMode()
  } catch (error) {
    closeToast()
    console.error('Share failed:', error)
    showToast(t('toast.shareFailed'))
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }

  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除选中的 ${selectedIds.value.length} 项资产吗？此操作不可恢复。`,
    })
    showLoadingToast({ message: '删除中...', forbidClick: true, duration: 0 })
    try {
      const res = await batchArchiveAssets(selectedIds.value)
      closeToast()
      showToast(t('toast.assetDeleteBatchSuccess', { count: res.data.success_count }))
      selectionMode.value = false
      selectedIds.value = []
      selectAll.value = false
      await dashboardStore.fetchAll()
    } catch {
      closeToast()
      showToast(t('toast.deleteFailed'))
    }
  } catch {
    // User cancelled
  }
}

async function handleBatchCategory() {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }
  // Show category picker - simplified version
  showToast(t('toast.assetEditCategoryHint'))
}

async function handleBatchTag() {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }
  showToast(t('toast.assetEditTagHint'))
}

async function onMoreActionSelect(action: { value: string }) {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }

  showLoadingToast({ message: '处理中...', forbidClick: true, duration: 0 })
  try {
    switch (action.value) {
      case 'retire': {
        const res = await batchUpdateStatus(selectedIds.value, 'archived')
        closeToast()
        showToast(t('toast.assetRetireBatchSuccess', { count: res.data.success_count }))
        break
      }
      case 'activate': {
        const res = await batchUpdateStatus(selectedIds.value, 'active')
        closeToast()
        showToast(t('toast.assetActivateBatchSuccess', { count: res.data.success_count }))
        break
      }
      case 'export': {
        const res = await batchExportAssets(selectedIds.value)
        closeToast()
        // Create downloadable JSON
        const dataStr = JSON.stringify(res.data.data, null, 2)
        const blob = new Blob([dataStr], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `assets-export-${new Date().toISOString().slice(0, 10)}.json`
        a.click()
        URL.revokeObjectURL(url)
        showToast(t('toast.assetExportBatchSuccess', { count: res.data.count }))
        break
      }
    }
    selectionMode.value = false
    selectedIds.value = []
    selectAll.value = false
    await dashboardStore.fetchAll()
  } catch {
    closeToast()
    showToast(t('toast.operationFailed'))
  }
}

// Scroll handler for category nav
function handleScroll() {
  if (!overviewCardRef.value) return

  const overviewCard = overviewCardRef.value.$el
  if (overviewCard) {
    const rect = overviewCard.getBoundingClientRect()
    // Show category nav when overview card is scrolled out of view
    showCategoryNav.value = rect.bottom < 0 && categoriesWithAssetCount.value.length > 0
  }
}

function onTrendPeriodChange(period: 'month' | 'quarter' | 'year') {
  dashboardStore.fetchTrend(period)
}

function toggleTrend() {
  trendExpanded.value = trendExpanded.value.includes('trend') ? [] : ['trend']
  localStorage.setItem('dashboard_trend_expanded', trendExpanded.value.length > 0 ? 'true' : 'false')
}

function toggleAllocation() {
  allocationExpanded.value = allocationExpanded.value.includes('allocation') ? [] : ['allocation']
  localStorage.setItem('dashboard_allocation_expanded', allocationExpanded.value.length > 0 ? 'true' : 'false')
}

async function onLoadMore() {
  if (dashboardStore.assetListFinished || dashboardStore.assetListLoading) return
  loadingMore.value = true
  try {
    await dashboardStore.loadNextAssetsPage()
  } finally {
    loadingMore.value = false
  }
}

async function onRefresh() {
  activeCategoryId.value = null
  activeCategoryIndex.value = 0
  dashboardStore.resetAssetPagination()
  await dashboardStore.fetchAll()
  const currentStatus = activeStatus.value || 'in_use'
  await Promise.all([
    dashboardStore.fetchAssetsPage(currentStatus, 1, 20, undefined),
    dashboardStore.fetchCategoryCounts(currentStatus),
  ])
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  refreshing.value = false
}

onMounted(() => {
  // Fetch dashboard bundle first, then load first page of assets
  dashboardStore.fetchAll().then(() => {
    const initialStatus = activeStatus.value || 'in_use'
    dashboardStore.fetchAssetsPage(initialStatus, 1, 20, undefined)
    dashboardStore.fetchCategoryCounts(initialStatus)
  })
  if (authStore.user?.role === 'owner') {
    choreStore.fetchPendingApprovals()
  }
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.dashboard-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}

.stale-hint {
  color: var(--van-gray-6);
  font-size: 12px;
  text-align: center;
  margin: 4px 0;
}

/* Toolbar Icons */
:deep(.toolbar-slot .van-icon) {
  font-size: 20px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
}
:deep(.toolbar-slot .van-icon:active) {
  opacity: 0.6;
}

/* Category Navigation (Sticky) */
.category-nav-sticky {
  position: sticky;
  top: 0;
  z-index: 99;
  background: var(--card-bg);
  border-bottom: 1px solid var(--color-hairline);
}
.category-nav-sticky :deep(.van-tabs__wrap) {
  padding: 0 12px;
}
.category-nav-sticky :deep(.van-tabs__line) {
  background: var(--color-coral);
  height: 2px;
  border-radius: var(--radius-full);
}
.category-nav-sticky :deep(.van-tab--active) {
  color: var(--color-primary);
  font-weight: 600;
}
[data-theme='dark'] .category-nav-sticky :deep(.van-tab--active) {
  color: var(--color-coral);
}

/* Asset Section */
.asset-section {
  padding: 0 12px;
  margin-top: 10px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.asset-list {
  /* cards have their own margin-bottom */
}

/* Selection Mode */
.selection-mode {
  padding: 0 12px;
  margin-top: 10px;
}
.selection-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  margin-bottom: 12px;
}
.selection-count {
  flex: 1;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-primary);
}
.selection-list-cards {
  padding: 0 12px;
}
.selection-actions {
  display: flex;
  justify-content: space-around;
  padding: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  position: sticky;
  bottom: 60px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .selection-actions {
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.3);
}

/* Filter Popup */
.bottom-spacer {
  height: 80px;
}

/* FAB */
.fab {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: var(--color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-elevated);
  z-index: 20;
  cursor: pointer;
  border: none;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.2s ease;
}

.fab:active {
  transform: scale(0.93);
  box-shadow: 0 2px 8px rgba(23, 23, 28, 0.25);
}

.fab-icon {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fab--open .fab-icon {
  transform: rotate(45deg);
}

[data-theme='dark'] .fab {
  background: var(--color-lavender);
  color: #ffffff;
  box-shadow: 0 4px 20px rgba(189, 187, 255, 0.3);
}

/* FAB backdrop */
.fab-backdrop {
  position: fixed;
  inset: 0;
  z-index: 18;
  background: rgba(0, 0, 0, 0.25);
}

.fab-backdrop-enter-active,
.fab-backdrop-leave-active {
  transition: opacity 0.2s ease;
}

.fab-backdrop-enter-from,
.fab-backdrop-leave-to {
  opacity: 0;
}

/* FAB menu */
.fab-menu {
  position: fixed;
  right: 16px;
  bottom: 132px;
  z-index: 19;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.fab-menu-enter-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fab-menu-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fab-menu-enter-from,
.fab-menu-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.92);
}

.fab-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--card-bg, #fff);
  border: none;
  border-radius: 8px;
  padding: 10px 14px 10px 16px;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(1, 1, 32, 0.12);
  min-height: 44px;
  white-space: nowrap;
  transition: transform 0.1s ease, box-shadow 0.1s ease;
}

.fab-menu-item:active {
  transform: scale(0.97);
  box-shadow: 0 1px 6px rgba(1, 1, 32, 0.1);
}

.fab-menu-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.fab-menu-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(124, 58, 237, 0.12) 100%);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

[data-theme='dark'] .fab-menu-item {
  background: #1a1a3a;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
}

[data-theme='dark'] .fab-menu-icon {
  background: linear-gradient(135deg, rgba(189, 187, 255, 0.15) 0%, rgba(124, 58, 237, 0.15) 100%);
  color: var(--color-lavender);
}

.chart-section {
  margin-top: 12px;
}

.chart-section :deep(.van-collapse-item__content) {
  padding: 12px;
}
</style>
