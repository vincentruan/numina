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

        <!-- Pending Chore Approvals (owner only) -->
        <PendingApprovalsSection v-if="authStore.user?.role === 'owner'" />

        <!-- Status Summary Grid + Toolbar -->
        <StatusSummaryGrid
          :summary="dashboardStore.statesSummary"
          :active-status="activeStatus"
          @select="onStatusSelect"
        >
          <template #toolbar>
            <van-icon name="sort" @click="showSortPopup = true" />
            <van-icon name="filter-o" @click="showFilterPopup = true" />
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
            <div class="section-actions">
              <span class="view-toggle" :aria-label="viewMode === 'card' ? '切换列表视图' : '切换卡片视图'" @click="toggleViewMode">
                <svg v-if="viewMode === 'card'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
              </span>
              <span class="category-toggle" @click="toggleCategoryView">
                {{ showCategoryGroups ? '列表' : '分类' }}
              </span>
            </div>
          </div>

          <!-- Category Grouped View -->
          <template v-if="showCategoryGroups && groupedByCategory.length">
            <div v-for="group in groupedByCategory" :key="group.id" class="category-group">
              <div class="category-group-header">
                <span class="category-icon">{{ group.icon }}</span>
                <span class="category-name">{{ group.name }}</span>
                <span class="category-count">({{ group.assets.length }})</span>
              </div>
              <div v-if="viewMode === 'card'" class="asset-list">
                <AssetCard
                  v-for="asset in group.assets"
                  :key="asset.id"
                  :asset="asset"
                  @click="$router.push(`/assets/${asset.id}`)"
                />
              </div>
              <div v-else class="asset-list-compact">
                <AssetListItem
                  v-for="asset in group.assets"
                  :key="asset.id"
                  :asset="asset"
                  @click="$router.push(`/assets/${asset.id}`)"
                />
              </div>
            </div>
          </template>

          <!-- Normal List View -->
          <template v-else-if="sortedAndFilteredAssets.length">
            <div v-if="viewMode === 'card'" class="asset-list">
              <AssetCard
                v-for="asset in sortedAndFilteredAssets"
                :key="asset.id"
                :asset="asset"
                @click="$router.push(`/assets/${asset.id}`)"
              />
            </div>
            <div v-else class="asset-list-compact">
              <AssetListItem
                v-for="asset in sortedAndFilteredAssets"
                :key="asset.id"
                :asset="asset"
                @click="$router.push(`/assets/${asset.id}`)"
              />
            </div>
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
              v-for="asset in sortedAndFilteredAssets"
              :key="asset.id"
              :asset="asset"
              :selectable="true"
              :selected="selectedIds.includes(asset.id)"
              @click="toggleSelection(asset.id)"
            />
          </div>
          <div class="selection-actions">
            <van-button icon="share-o" size="small" @click="handleBatchShare">分享</van-button>
            <van-button icon="delete-o" size="small" @click="handleBatchDelete">删除</van-button>
            <van-button icon="label-o" size="small" @click="handleBatchCategory">分类</van-button>
            <van-button icon="tag-o" size="small" @click="handleBatchTag">标签</van-button>
            <van-button icon="ellipsis" size="small" @click="showMoreActions = true">更多</van-button>
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

    <!-- Sort Popup -->
    <van-popup v-model:show="showSortPopup" position="bottom" round>
      <div class="sort-popup">
        <div class="sort-header">
          <span class="sort-title">排序方式</span>
          <van-icon name="cross" @click="showSortPopup = false" />
        </div>

        <div class="sort-content">
          <div v-for="group in sortGroups" :key="group.key" class="sort-group">
            <div class="sort-group-label">{{ group.label }}</div>
            <div class="sort-options">
              <van-button
                v-for="opt in group.options"
                :key="opt.value"
                :type="currentSort === opt.value ? 'primary' : 'default'"
                size="small"
                @click="selectSort(opt.value)"
              >
                {{ opt.label }}
              </van-button>
            </div>
          </div>
        </div>
      </div>
    </van-popup>

    <!-- Filter Popup -->
    <van-popup v-model:show="showFilterPopup" position="bottom" round>
      <div class="filter-popup">
        <div class="filter-header">
          <span>按标签筛选</span>
          <van-button type="primary" size="small" @click="applyFilter">确定</van-button>
        </div>
        <van-checkbox-group v-model="selectedTags">
          <van-cell-group>
            <van-cell
              v-for="tag in allTags"
              :key="tag"
              clickable
              @click="toggleTag(tag)"
            >
              <template #title>
                <van-checkbox :name="tag" @click.stop>{{ tag }}</van-checkbox>
              </template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>
      </div>
    </van-popup>

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
import { batchArchiveAssets, batchUpdateCategory, batchUpdateTags, batchUpdateStatus, batchExportAssets } from '@/api/assets'
import type { Asset } from '@/types'
import { generateAssetCard, generateSummaryCard, downloadImage } from '@/utils/shareImage'
import NetWorthCard from '@/components/dashboard/NetWorthCard.vue'
import StatusSummaryGrid from '@/components/dashboard/StatusSummaryGrid.vue'
import AlertCards from '@/components/dashboard/AlertCards.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'

const { t } = useI18n()

const dashboardStore = useDashboardStore()
const categoryStore = useCategoryStore()
const assetStore = useAssetStore()
const authStore = useAuthStore()
const choreStore = useChoreStore()
const refreshing = ref(false)
const activeStatus = ref<string | null>(null)
const viewMode = ref<'card' | 'list'>('card')
const overviewCardRef = ref()

// Category view
const showCategoryNav = ref(false)
const showCategoryGroups = ref(false)
const activeCategoryIndex = ref(0)

// Selection mode
const selectionMode = ref(false)
const selectedIds = ref<string[]>([])
const selectAll = ref(false)

// Toolbar
const showSortPopup = ref(false)
const showFilterPopup = ref(false)
const showMoreActions = ref(false)
const selectedTags = ref<string[]>([])
const currentSort = ref<string>('created_at_desc')

const overview = computed(() => dashboardStore.overview)
const categories = computed(() => categoryStore.categories)

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

// Sort options
// Sort options grouped
const sortGroups = [
  {
    key: 'created_at',
    label: '添加时间',
    options: [
      { label: '最新优先', value: 'created_at_desc' },
      { label: '最早优先', value: 'created_at_asc' },
    ]
  },
  {
    key: 'purchase_date',
    label: '购买时间',
    options: [
      { label: '最近购买', value: 'purchase_date_desc' },
      { label: '最早购买', value: 'purchase_date_asc' },
    ]
  },
  {
    key: 'service_days',
    label: '服役时长',
    options: [
      { label: '服役最久', value: 'service_days_desc' },
      { label: '服役最短', value: 'service_days_asc' },
    ]
  },
  {
    key: 'current_value',
    label: '物品价值',
    options: [
      { label: '价值最高', value: 'current_value_desc' },
      { label: '价值最低', value: 'current_value_asc' },
    ]
  },
  {
    key: 'daily_cost',
    label: '日均成本',
    options: [
      { label: '成本最高', value: 'daily_cost_desc' },
      { label: '成本最低', value: 'daily_cost_asc' },
    ]
  },
]

// More actions
const moreActions = [
  { name: '转为退役', value: 'retire' },
  { name: '转为服役', value: 'activate' },
  { name: '导出', value: 'export' },
]

const sectionTitle = computed(() => {
  if (!activeStatus.value) {
    const count = filteredAssets.value.length
    return `资产列表 (${count})`
  }
  const label = statusLabelMap[activeStatus.value] || activeStatus.value
  const count = filteredAssets.value.length
  return `${label} (${count})`
})

const filteredAssets = computed(() => {
  if (!activeStatus.value) {
    const allAssets = Object.values(dashboardStore.homeAssets).flat()
    return allAssets
  }
  return dashboardStore.homeAssets[activeStatus.value] || []
})

// Get all unique tags from assets
const allTags = computed(() => {
  const tags = new Set<string>()
  filteredAssets.value.forEach(asset => {
    if (asset.tags && Array.isArray(asset.tags)) {
      asset.tags.forEach(tag => {
        if (typeof tag === 'string') {
          tags.add(tag)
        } else if (tag && typeof tag === 'object' && 'name' in tag) {
          tags.add(tag.name)
        }
      })
    }
  })
  return Array.from(tags)
})

// Apply tag filter
const tagFilteredAssets = computed(() => {
  if (selectedTags.value.length === 0) {
    return filteredAssets.value
  }
  return filteredAssets.value.filter(asset => {
    if (!asset.tags || !Array.isArray(asset.tags)) return false
    return selectedTags.value.some(selectedTag => {
      return asset.tags!.some(tag => {
        if (typeof tag === 'string') {
          return tag === selectedTag
        } else if (tag && typeof tag === 'object' && 'name' in tag) {
          return tag.name === selectedTag
        }
        return false
      })
    })
  })
})

// Apply sorting
const sortedAndFilteredAssets = computed(() => {
  const assets = [...tagFilteredAssets.value]
  const [field, order] = currentSort.value.split('_')
  const isDesc = order === 'desc'

  assets.sort((a, b) => {
    let aVal: any
    let bVal: any

    switch (field) {
      case 'created':
        aVal = new Date(a.created_at).getTime()
        bVal = new Date(b.created_at).getTime()
        break
      case 'purchase':
        aVal = a.purchase_date ? new Date(a.purchase_date).getTime() : 0
        bVal = b.purchase_date ? new Date(b.purchase_date).getTime() : 0
        break
      case 'service':
        aVal = a.purchase_date ? Date.now() - new Date(a.purchase_date).getTime() : 0
        bVal = b.purchase_date ? Date.now() - new Date(b.purchase_date).getTime() : 0
        break
      case 'current':
        aVal = a.current_value || 0
        bVal = b.current_value || 0
        break
      case 'daily':
        aVal = a.daily_cost || 0
        bVal = b.daily_cost || 0
        break
      default:
        aVal = new Date(a.updated_at).getTime()
        bVal = new Date(b.updated_at).getTime()
    }

    return isDesc ? bVal - aVal : aVal - bVal
  })

  return assets
})

// Group assets by category
const groupedByCategory = computed(() => {
  const groups = new Map<string, { id: string; name: string; icon: string; assets: Asset[] }>()

  sortedAndFilteredAssets.value.forEach(asset => {
    const categoryId = asset.category_id
    const category = asset.category || categories.value.find(c => c.id === categoryId)

    if (category) {
      if (!groups.has(categoryId)) {
        groups.set(categoryId, {
          id: categoryId,
          name: category.name,
          icon: category.icon,
          assets: []
        })
      }
      groups.get(categoryId)!.assets.push(asset)
    }
  })

  return Array.from(groups.values())
})

function toggleViewMode() {
  viewMode.value = viewMode.value === 'card' ? 'list' : 'card'
}

function toggleCategoryView() {
  showCategoryGroups.value = !showCategoryGroups.value
  if (showCategoryGroups.value) {
    showToast('已切换到分类视图')
  } else {
    showToast('已切换到列表视图')
  }
}

function onCategoryChange(index: number) {
  activeCategoryIndex.value = index
  // Scroll to the category group
  const categoryGroups = document.querySelectorAll('.category-group')
  if (categoryGroups[index]) {
    categoryGroups[index].scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function onStatusSelect(status: string | null) {
  activeStatus.value = status
}

function selectSort(value: string) {
  currentSort.value = value
  showSortPopup.value = false
}

function toggleTag(tag: string) {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tag)
  }
}

function applyFilter() {
  showFilterPopup.value = false
  if (selectedTags.value.length > 0) {
    showToast(`已筛选 ${selectedTags.value.length} 个标签`)
  }
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
    selectedIds.value = sortedAndFilteredAssets.value.map(a => a.id)
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
  selectAll.value = selectedIds.value.length === sortedAndFilteredAssets.value.length
}

async function handleBatchShare() {
  if (selectedIds.value.length === 0) {
    showToast('请先选择资产')
    return
  }

  showLoadingToast({
    message: '生成分享图片中...',
    forbidClick: true,
    duration: 0,
  })

  try {
    const selectedAssets = sortedAndFilteredAssets.value.filter(a => selectedIds.value.includes(a.id))

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
    showToast('图片已保存')
    exitSelectionMode()
  } catch (error) {
    closeToast()
    console.error('Share failed:', error)
    showToast('分享失败，请重试')
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) {
    showToast('请先选择资产')
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
      showToast(`成功删除 ${res.data.success_count} 项资产`)
      selectionMode.value = false
      selectedIds.value = []
      selectAll.value = false
      await dashboardStore.fetchAll()
    } catch {
      closeToast()
      showToast('删除失败，请重试')
    }
  } catch {
    // User cancelled
  }
}

async function handleBatchCategory() {
  if (selectedIds.value.length === 0) {
    showToast('请先选择资产')
    return
  }
  // Show category picker - simplified version
  showToast('请使用单个资产编辑功能修改分类')
}

async function handleBatchTag() {
  if (selectedIds.value.length === 0) {
    showToast('请先选择资产')
    return
  }
  showToast('请使用单个资产编辑功能修改标签')
}

async function onMoreActionSelect(action: any) {
  if (selectedIds.value.length === 0) {
    showToast('请先选择资产')
    return
  }

  const loading = showLoadingToast({ message: '处理中...', forbidClick: true, duration: 0 })
  try {
    switch (action.value) {
      case 'retire': {
        const res = await batchUpdateStatus(selectedIds.value, 'archived')
        closeToast()
        showToast(`成功退役 ${res.data.success_count} 项资产`)
        break
      }
      case 'activate': {
        const res = await batchUpdateStatus(selectedIds.value, 'active')
        closeToast()
        showToast(`成功激活 ${res.data.success_count} 项资产`)
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
        showToast(`成功导出 ${res.data.count} 项资产`)
        break
      }
    }
    selectionMode.value = false
    selectedIds.value = []
    selectAll.value = false
    await dashboardStore.fetchAll()
  } catch {
    closeToast()
    showToast('操作失败，请重试')
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

async function onRefresh() {
  await dashboardStore.fetchAll()
  if (authStore.user?.role === 'owner') {
    await choreStore.fetchPendingApprovals()
  }
  refreshing.value = false
}

onMounted(() => {
  // Initialize viewMode from user settings
  if (authStore.user?.view_mode === 'list') {
    viewMode.value = 'list'
  }
  dashboardStore.fetchAll()
  categoryStore.fetchCategories()
  if (authStore.user?.role === 'owner') {
    choreStore.fetchPendingApprovals()
  }
  window.addEventListener('scroll', handleScroll)
})

// Watch for user settings changes
watch(() => authStore.user?.view_mode, (newMode) => {
  if (newMode === 'list' || newMode === 'card') {
    viewMode.value = newMode
  }
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
.section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.view-toggle,
.category-toggle {
  font-size: 13px;
  color: var(--color-action-primary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(21, 101, 192, 0.1);
}
[data-theme='dark'] .view-toggle,
[data-theme='dark'] .category-toggle {
  background: rgba(21, 101, 192, 0.15);
}
.view-toggle:active,
.category-toggle:active {
  opacity: 0.7;
}
.asset-list {
  /* cards have their own margin-bottom */
}
.asset-list-compact {
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
[data-theme='dark'] .asset-list-compact {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

/* Category Group */
.category-group {
  margin-bottom: 16px;
}
.category-group-header {
  display: flex;
  align-items: center;
  padding: 12px 8px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 8px;
  margin-bottom: 8px;
}
[data-theme='dark'] .category-group-header {
  background: linear-gradient(135deg, #2a2a2a 0%, #1f1f1f 100%);
}
.category-icon {
  font-size: 20px;
  margin-right: 8px;
}
.category-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.category-count {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-left: 4px;
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
.filter-popup {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}
.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-size: 16px;
  font-weight: 600;
}

.bottom-spacer {
  height: 80px;
}

/* Sort Popup */
.sort-popup {
  padding: 16px;
}
.sort-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.sort-title {
  font-size: 16px;
  font-weight: 600;
}
.sort-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sort-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sort-group-label {
  font-size: 13px;
  color: var(--text-tertiary);
}
.sort-options {
  display: flex;
  gap: 8px;
}
</style>
