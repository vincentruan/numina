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

        <!-- Quick Stats -->
        <van-cell-group inset class="quick-stats-section">
          <van-cell title="资产数量" :value="`${overview?.asset_count ?? 0} 项`" />
          <van-cell title="日均成本总计" :value="`¥${(overview?.total_daily_cost ?? 0).toFixed(2)}/天`" />
        </van-cell-group>

        <!-- Trend Chart -->
        <van-cell-group inset class="chart-section">
          <van-collapse v-model="trendExpanded" @change="toggleTrend">
            <van-collapse-item title="资产趋势" name="trend">
              <TrendLineChart v-if="dashboardStore.trend.length" :data="dashboardStore.trend" />
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

        <!-- Alert Cards: Idle + Expiring Soon -->
        <AlertCards
          v-if="hasAlertCards"
          :idle-assets="dashboardStore.lowUsageAssets.filter(a => a.usage_frequency === 'idle')"
          :expiring-assets="dashboardStore.expiringSoonAssets"
          @select-status="onStatusSelect"
        />

        <!-- Smart Reminders -->
        <SmartRemindersCard />

        <!-- Category Navigation (Sticky, shown when scrolled) -->
        <div v-if="showCategoryNav && categories.length > 1" class="category-nav-sticky">
          <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
            <van-tab v-for="(cat, index) in categories" :key="cat.id" :title="cat.name" />
          </van-tabs>
        </div>

        <!-- Asset List (Normal Mode) -->
        <div v-if="!selectionMode" class="asset-section">
          <div class="section-header">
            <span class="section-title">{{ sectionTitle }}</span>
          </div>

          <!-- Asset List -->
          <template v-if="dashboardStore.displayedAssets.length">
            <van-list
              v-model:loading="loadingMore"
              :finished="dashboardStore.assetListFinished"
              finished-text="没有更多了"
              @load="onLoadMore"
            >
              <div class="asset-list">
                <AssetCard
                  v-for="asset in dashboardStore.displayedAssets"
                  :key="asset.id"
                  :asset="asset"
                  @click="$router.push(`/assets/${asset.id}`)"
                />
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
            <AssetCard
              v-for="asset in dashboardStore.displayedAssets"
              :key="asset.id"
              :asset="asset"
              :selectable="true"
              :selected="selectedIds.includes(asset.id)"
              @click="toggleSelection(asset.id)"
            />
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

    <!-- Add Asset FAB -->
    <van-floating-bubble
      v-if="!selectionMode"
      icon="plus"
      aria-label="添加资产"
      @click="$router.push('/assets/new')"
    />

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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { showToast, showConfirmDialog, showLoadingToast, closeToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useDashboardStore } from '@/stores/dashboard'
import { useCategoryStore } from '@/stores/category'
import { useAssetStore } from '@/stores/asset'
import { useAuthStore } from '@/stores/auth'
import { useChoreStore } from '@/stores/chore'
import { batchArchiveAssets, batchUpdateStatus, batchExportAssets } from '@/api/assets'
import type { Asset } from '@/types'
import { generateAssetCard, generateSummaryCard, downloadImage } from '@/utils/shareImage'
import NetWorthCard from '@/components/dashboard/NetWorthCard.vue'
import StatusSummaryGrid from '@/components/dashboard/StatusSummaryGrid.vue'
import AlertCards from '@/components/dashboard/AlertCards.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'
import SmartRemindersCard from '@/components/dashboard/SmartRemindersCard.vue'

const { t } = useI18n()

const dashboardStore = useDashboardStore()
const categoryStore = useCategoryStore()
const assetStore = useAssetStore()
const authStore = useAuthStore()
const choreStore = useChoreStore()
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

const overview = computed(() => dashboardStore.overview)
const categories = computed(() => categoryStore.categories)

// Filter and sort categories by asset count (descending)
const categoriesWithAssetCount = computed(() => {
  const allAssets = dashboardStore.displayedAssets
  const counts = new Map<string, number>()

  // Count assets per category
  allAssets.forEach(asset => {
    const catId = asset.category_id
    counts.set(catId, (counts.get(catId) || 0) + 1)
  })

  // Filter categories with assets and sort by count descending
  return categories.value
    .filter(cat => counts.get(cat.id) > 0)
    .map(cat => ({
      id: cat.id,
      name: cat.name,
      icon: cat.icon,
      count: counts.get(cat.id) || 0
    }))
    .sort((a, b) => b.count - a.count)
})

// Filter displayed assets by selected category
const filteredByCategoryAssets = computed(() => {
  if (!activeCategoryId.value) {
    return dashboardStore.displayedAssets
  }
  return dashboardStore.displayedAssets.filter(asset => asset.category_id === activeCategoryId.value)
})

// Alert cards visibility
const hasAlertCards = computed(() => {
  const idleCount = dashboardStore.lowUsageAssets.filter(a => a.usage_frequency === 'idle').length
  const expiringCount = dashboardStore.expiringSoonAssets.length
  return idleCount > 0 || expiringCount > 0
})

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
  if (index === 0) {
    activeCategoryId.value = null  // "全部" tab
  } else {
    const category = categoriesWithAssetCount.value[index - 1]
    activeCategoryId.value = category.id
  }
}

function onStatusSelect(status: string | null) {
  activeStatus.value = status
  // Reset pagination and load first page for the new status
  const targetStatus = status || 'in_use'
  dashboardStore.resetAssetPagination(targetStatus)
  dashboardStore.fetchAssetsPage(targetStatus, 1, 20)
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
    const loading = showLoadingToast({ message: '删除中...', forbidClick: true, duration: 0 })
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

async function onMoreActionSelect(action: any) {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }

  const loading = showLoadingToast({ message: '处理中...', forbidClick: true, duration: 0 })
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
    showCategoryNav.value = rect.bottom < 0 && categories.value.length > 1
  }
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
  dashboardStore.resetAssetPagination()
  await dashboardStore.fetchAll()
  // Reload first page after refresh
  const currentStatus = activeStatus.value || 'in_use'
  await dashboardStore.fetchAssetsPage(currentStatus, 1, 20)
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  refreshing.value = false
}

onMounted(() => {
  // Fetch dashboard bundle first, then load first page of assets
  dashboardStore.fetchAll().then(() => {
    const initialStatus = activeStatus.value || 'in_use'
    dashboardStore.fetchAssetsPage(initialStatus, 1, 20)
  })
  categoryStore.fetchCategories()
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
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .category-nav-sticky {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.category-nav-sticky :deep(.van-tabs__wrap) {
  padding: 0 12px;
}
.category-nav-sticky :deep(.van-tabs__line) {
  background: linear-gradient(90deg, transparent, #1989fa, transparent);
  height: 3px;
  border-radius: 3px;
  box-shadow: 0 0 8px rgba(25, 137, 250, 0.6);
}
.category-nav-sticky :deep(.van-tab--active) {
  color: #1989fa;
  font-weight: 600;
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
  color: #1989fa;
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

.quick-stats-section {
  margin-top: 12px;
}

.chart-section {
  margin-top: 12px;
}

.chart-section :deep(.van-collapse-item__content) {
  padding: 12px;
}
</style>
