<template>
  <div class="asset-list-panel">
    <!-- Sticky Filter Bar: Status + Category -->
    <div ref="filterBarRef" class="filter-bar-sticky">
      <!-- Placeholder: maintains layout space when content is fixed -->
      <div v-if="filterBarFrozen" class="filter-bar-placeholder" :style="{ height: `${filterBarHeight}px` }" />

      <!-- Filter bar content: becomes fixed when frozen -->
      <div ref="filterBarContentRef" class="filter-bar-content" :class="{ 'filter-bar-content--fixed': filterBarFrozen }">
        <!-- Status Summary Grid + Toolbar -->
        <StatusSummaryGrid
          :summary="dashboardStore.statesSummary"
          :active-status="activeStatus"
          @select="onStatusSelect"
        >
          <template #toolbar>
            <button
              class="toolbar-selection-btn"
              :aria-label="t('dashboard.aria.openBatchSelection')"
              @click="enterSelectionMode"
            >
              <van-icon name="checked" size="18" />
            </button>
          </template>
        </StatusSummaryGrid>

        <!-- Asset Type Tabs (ported from AssetListPage) -->
        <van-tabs v-model:active="activeTypeIndex" class="type-tabs" @change="onTypeTabChange">
          <van-tab :title="t('asset.all')" name="all" />
          <van-tab :title="t('asset.physical')" name="physical" />
          <van-tab :title="t('asset.financial')" name="financial" />
        </van-tabs>

        <!-- Category Navigation (Always visible when categories exist) -->
        <div
          v-if="categoriesWithAssetCount.length > 0"
          class="category-nav-container"
        >
          <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
            <van-tab :title="t('statusGrid.all')" />
            <van-tab
              v-for="cat in categoriesWithAssetCount"
              :key="cat.id"
            >
              <template #title>
                <span class="cat-tab-title">
                  <span class="cat-tab-icon" :style="{ background: cat.color || 'var(--color-primary)' }">
                    <SvgIcon :name="getIconId(cat.icon)" class="cat-tab-svg" />
                  </span>
                  {{ cat.name }} ({{ cat.count }})
                </span>
              </template>
            </van-tab>
          </van-tabs>
        </div>

        <!-- Search & Sort (ported from AssetListPage) -->
        <div class="search-bar">
          <van-search
            v-model="searchText"
            :placeholder="t('asset.search')"
            @search="onSearch"
            @clear="onSearch"
          />
          <button
            class="sort-trigger"
            :aria-label="t('asset.sortLabel') + ': ' + currentSortLabel"
            @click="cycleSortOption"
          >
            <van-icon name="exchange" class="sort-trigger-icon" />
            <span class="sort-trigger-label">{{ currentSortLabel }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Asset List (Normal Mode) -->
    <div v-if="!selectionMode" class="asset-section">
      <div class="section-header">
        <span class="section-title">{{ sectionTitle }}</span>
        <div class="view-mode-toggle">
          <button
            class="view-toggle-btn"
            :aria-label="viewMode === 'card' ? t('dashboard.viewModeList') : t('dashboard.viewModeCard')"
            :disabled="updatingViewMode"
            @click="setViewMode(viewMode === 'card' ? 'list' : 'card')"
          >
            <van-icon :name="viewMode === 'card' ? 'bars' : 'apps-o'" size="18" />
          </button>
        </div>
      </div>

      <!-- Sentinel: top of asset list, used to detect when to unfreeze filter bar -->
      <div ref="assetListTopRef" class="asset-list-top-sentinel" />

      <!-- Asset List -->
      <template v-if="filteredByCategoryAssets.length">
        <van-list
          v-model:loading="loadingMore"
          :finished="dashboardStore.assetListFinished"
          :finished-text="t('common.noMore')"
          @load="onLoadMore"
        >
          <div class="asset-list">
            <template v-if="viewMode === 'list'">
              <template v-for="group in groupedByCategory" :key="group.key">
                <AssetGroupHeader
                  :category="group.category"
                  :count="group.items.length"
                  :subtotal="group.subtotal"
                  :collapsed="collapsedGroups.has(group.key)"
                  :selection-mode="selectionMode"
                  :selected-count="groupSelectedCount(group.items)"
                  @toggle="toggleGroup(group.key)"
                />
                <Transition name="collapse">
                  <div v-if="!collapsedGroups.has(group.key)" class="group-items">
                    <van-swipe-cell
                      v-for="asset in group.items"
                      :key="asset.id"
                      :ref="setAssetSwipeRef(asset.id)"
                      :left-width="0"
                      :right-width="assetSwipeWidth(asset)"
                      class="asset-swipe"
                      stop-propagation
                      :disabled="!assetHasSwipe(asset)"
                    >
                      <AssetListItem
                        :asset="asset"
                        @click="$router.push(`/assets/${asset.id}`)"
                      />
                      <template v-if="assetHasSwipe(asset)" #right>
                        <van-button
                          v-if="asset.status === 'in_use'"
                          square
                          type="warning"
                          class="swipe-action-btn"
                          :text="t('asset.markIdle')"
                          @click="onSwipeMarkIdle(asset)"
                        />
                        <van-button
                          v-if="asset.status === 'idle'"
                          square
                          type="primary"
                          class="swipe-action-btn"
                          :text="t('asset.reactivate')"
                          @click="onSwipeReactivate(asset)"
                        />
                        <van-button
                          square
                          type="danger"
                          class="swipe-action-btn"
                          :text="t('asset.deleteAsset')"
                          @click="onSwipeDeleteAsset(asset)"
                        />
                      </template>
                    </van-swipe-cell>
                  </div>
                </Transition>
              </template>
            </template>
            <template v-else>
              <template v-for="group in groupedByCategory" :key="group.key">
                <AssetGroupHeader
                  :category="group.category"
                  :count="group.items.length"
                  :subtotal="group.subtotal"
                  :collapsed="collapsedGroups.has(group.key)"
                  :selection-mode="selectionMode"
                  :selected-count="groupSelectedCount(group.items)"
                  @toggle="toggleGroup(group.key)"
                />
                <Transition name="collapse">
                  <div v-if="!collapsedGroups.has(group.key)" class="group-items group-items--grid">
                    <AssetCard
                      v-for="asset in group.items"
                      :key="asset.id"
                      :asset="asset"
                      @click="$router.push(`/assets/${asset.id}`)"
                    />
                  </div>
                </Transition>
              </template>
            </template>
          </div>
        </van-list>
      </template>

      <!-- D7: gate empty-state on assetListLoading to avoid flashing "无资产" during pagination -->
      <van-empty v-else-if="!dashboardStore.assetListLoading" :description="t('dashboard.emptyState.noAssets')" image-size="60" />
    </div>

    <!-- Selection Mode -->
    <div v-else class="selection-mode">
      <div class="selection-header">
        <van-checkbox :model-value="selectAll" @change="toggleSelectAll">{{
          t('dashboard.selectAll')
        }}</van-checkbox>
        <span class="selection-count">{{
          t('dashboard.selectedCount', { count: selectedIds.length })
        }}</span>
        <van-button
          type="primary"
          size="small"
          class="selection-done-btn"
          @click="exitSelectionMode"
          >{{ t('dashboard.selectionDone') }}</van-button
        >
      </div>
      <div class="selection-actions">
        <button class="action-btn" @click="handleBatchDelete">
          <van-icon name="delete-o" size="18" />
          <span>{{ t('dashboard.actionDelete') }}</span>
        </button>
        <button class="action-btn" @click="showMoreActions = true">
          <van-icon name="ellipsis" size="18" />
          <span>{{ t('dashboard.actionMore') }}</span>
        </button>
      </div>
      <div class="selection-list-cards">
        <template v-if="viewMode === 'list'">
          <template v-for="group in groupedByCategory" :key="group.key">
            <AssetGroupHeader
              :category="group.category"
              :count="group.items.length"
              :subtotal="group.subtotal"
              :collapsed="collapsedGroups.has(group.key)"
              :selection-mode="true"
              :selected-count="groupSelectedCount(group.items)"
              @toggle="toggleGroup(group.key)"
            />
            <Transition name="collapse">
              <div v-if="!collapsedGroups.has(group.key)" class="group-items">
                <AssetListItem
                  v-for="asset in group.items"
                  :key="asset.id"
                  :asset="asset"
                  :selectable="true"
                  :selected="selectedIds.includes(asset.id)"
                  @click="toggleSelection(asset.id)"
                />
              </div>
            </Transition>
          </template>
        </template>
        <template v-else>
          <template v-for="group in groupedByCategory" :key="group.key">
            <AssetGroupHeader
              :category="group.category"
              :count="group.items.length"
              :subtotal="group.subtotal"
              :collapsed="collapsedGroups.has(group.key)"
              :selection-mode="true"
              :selected-count="groupSelectedCount(group.items)"
              @toggle="toggleGroup(group.key)"
            />
            <Transition name="collapse">
              <div v-if="!collapsedGroups.has(group.key)" class="group-items group-items--grid">
                <AssetCard
                  v-for="asset in group.items"
                  :key="asset.id"
                  :asset="asset"
                  :selectable="true"
                  :selected="selectedIds.includes(asset.id)"
                  @click="toggleSelection(asset.id)"
                />
              </div>
            </Transition>
          </template>
        </template>
      </div>
    </div>

    <!-- FAB Menu -->
    <template v-if="!selectionMode">
      <!-- Backdrop -->
      <transition name="fab-backdrop">
        <div
          v-if="fabMenuOpen"
          class="fab-backdrop"
          aria-hidden="true"
          @click="fabMenuOpen = false"
        />
      </transition>
      <!-- Menu items -->
      <transition name="fab-menu">
        <div v-if="fabMenuOpen" class="fab-menu" role="menu" :aria-label="t('dashboard.aria.quickActions')">
          <button class="fab-menu-item" role="menuitem" @click="onFabAction('import')">
            <span class="fab-menu-label">{{ t('dashboard.fabImportBill') }}</span>
            <span class="fab-menu-icon" aria-hidden="true">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
            </span>
          </button>
          <button class="fab-menu-item" role="menuitem" @click="onFabAction('add')">
            <span class="fab-menu-label">{{ t('dashboard.fabAddAsset') }}</span>
            <span class="fab-menu-icon" aria-hidden="true">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <rect x="2" y="7" width="20" height="14" rx="2" />
                <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2" />
                <line x1="12" y1="12" x2="12" y2="17" />
                <line x1="9.5" y1="14.5" x2="14.5" y2="14.5" />
              </svg>
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
      :cancel-text="t('common.cancel')"
      @select="onMoreActionSelect"
    />

    <!-- Destructive confirm: batch delete assets -->
    <BottomSheetConfirm
      v-model:show="deleteSheet.show"
      :title="t('dashboard.dialog.confirmDeleteTitle')"
      :description="t('dashboard.dialog.confirmDeleteMessage', { count: selectedIds.length })"
      :impact-preview="t('bottomSheet.impactAssetBatchDelete')"
      @confirm="executeBatchDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { showToast, showFailToast, showConfirmDialog, showSuccessToast } from 'vant'
import type { ComponentPublicInstance } from 'vue'
import BottomSheetConfirm from '@/components/BottomSheetConfirm.vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { usePageLoading } from '@/composables/usePageLoading'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useExchangeRate } from '@/composables/useExchangeRate'
import { batchArchiveAssets, batchUpdateStatus, batchExportAssets, deleteAsset, retireAsset, reactivateAsset } from '@/api/assets'
import { updateSettings } from '@/api/auth'

import { getIconId } from '@/utils/icon'
import StatusSummaryGrid from '@/components/dashboard/StatusSummaryGrid.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import AssetGroupHeader from '@/components/asset/AssetGroupHeader.vue'
import SvgIcon from '@/components/SvgIcon.vue'
import type { Asset, Category } from '@/types'

const { t } = useI18n()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const { ensureRate } = useExchangeRate()
const viewMode = computed(() => authStore.user?.view_mode || 'card')
const updatingViewMode = ref(false)
const activeStatus = ref<string | null>(null)

// Pagination state
const loadingMore = ref(false)

// Category view
const activeCategoryIndex = ref(0)
const activeCategoryId = ref<string | null>(null) // null = show all

// Feature-parity filters (ported from AssetListPage): type tab / search / sort
const TYPE_TABS = ['all', 'physical', 'financial'] as const
const activeTypeIndex = ref<string>('all')
const searchText = ref('')
const sortBy = ref('current_value')

// Selection mode
const selectionMode = ref(false)
const selectedIds = ref<string[]>([])
const selectAll = ref(false)

// Toolbar
const showMoreActions = ref(false)

// FAB menu
const fabMenuOpen = ref(false)

// Destructive confirm sheet
const deleteSheet = ref({ show: false })

// Filter bar sticky/frozen control
const filterBarRef = ref<HTMLElement | null>(null)
const filterBarContentRef = ref<HTMLElement | null>(null)
const assetListTopRef = ref<HTMLElement | null>(null)
const filterBarFrozen = ref(false)
const filterBarHeight = ref(0)

function onScroll() {
  if (!filterBarRef.value || !assetListTopRef.value) return

  const scrollY = window.scrollY

  if (!filterBarFrozen.value) {
    // Read offsetTop fresh each time — content above (charts, reminders) can change height
    const naturalTop = filterBarRef.value.offsetTop
    if (scrollY >= naturalTop) {
      filterBarHeight.value = filterBarRef.value.offsetHeight
      filterBarFrozen.value = true
    }
  } else {
    // Unfreeze when the asset list top sentinel scrolls back above the filter bar bottom
    const sentinelTop = assetListTopRef.value.getBoundingClientRect().top
    if (sentinelTop >= filterBarHeight.value) {
      filterBarFrozen.value = false
    }
  }
}

function onFabAction(action: 'add' | 'import') {
  fabMenuOpen.value = false
  if (action === 'add') {
    router.push('/assets/new')
  } else {
    router.push('/settings/import-report')
  }
}

// Category counts from backend (full counts, not page-limited)
// Filter by active type tab: when "实物" or "金融" is selected, only show matching categories
const categoriesWithAssetCount = computed(() => {
  const activeType = activeTypeIndex.value as string
  return dashboardStore.categoryCounts
    .filter((c) => activeType === 'all' || c.asset_type === activeType)
    .map((c) => ({ id: c.id, name: c.name, icon: c.icon, color: c.color, count: c.count }))
    .sort((a, b) => b.count - a.count)
})

// Asset list: displayedAssets is already filtered by backend (status + optional category)
const filteredByCategoryAssets = computed(() => dashboardStore.displayedAssets)

// Grouped assets by category (for list view)
const UNCATEGORIZED_KEY = '__uncategorized__'
const collapsedGroups = ref<Set<string>>(new Set())

interface AssetGroup {
  key: string
  category: Category | undefined
  items: Asset[]
  subtotal: number
}


const groupedByCategory = computed<AssetGroup[]>(() => {
  const assets = filteredByCategoryAssets.value
  // Build a map of category_id → server-converted amount from allocation data.
  // This ensures category subtotals display in the user's default_currency
  // rather than raw CNY values with a swapped symbol.
  const allocationByCategory = new Map<string, number>()
  for (const item of dashboardStore.allocation || []) {
    allocationByCategory.set(item.category_id, item.amount)
  }

  const map = new Map<string, { category: Category | undefined; items: Asset[]; subtotal: number }>()

  for (const asset of assets) {
    const key = asset.category?.id ?? UNCATEGORIZED_KEY
    let group = map.get(key)
    if (!group) {
      group = { category: asset.category, items: [], subtotal: 0 }
      map.set(key, group)
    }
    group.items.push(asset)
  }

  // Use server-converted allocation amounts for subtotals (fallback to raw sum
  // only when allocation data is not yet available, e.g. during initial load).
  for (const [key, group] of map) {
    if (key !== UNCATEGORIZED_KEY && allocationByCategory.has(key)) {
      group.subtotal = allocationByCategory.get(key)!
    } else {
      for (const asset of group.items) {
        const val = Number(asset.current_value ?? 0)
        group.subtotal += isNaN(val) ? 0 : val
      }
    }
  }

  // Sort by subtotal descending (highest value category first)
  return Array.from(map.values())
    .sort((a, b) => b.subtotal - a.subtotal)
    .map((g) => ({ key: g.category?.id ?? UNCATEGORIZED_KEY, ...g }))
})

function toggleGroup(key: string) {
  if (collapsedGroups.value.has(key)) {
    collapsedGroups.value.delete(key)
  } else {
    collapsedGroups.value.add(key)
  }
}

function groupSelectedCount(items: Asset[]): number {
  return items.filter((a) => selectedIds.value.includes(a.id)).length
}

// Expand all groups when search/filter changes
watch([searchText, sortBy, activeTypeIndex, activeCategoryIndex, activeStatus], () => {
  collapsedGroups.value.clear()
})

function statusLabel(status: string): string {
  const key = status === 'in_use' ? 'statusGrid.inUse' : `statusGrid.${status}`
  return t(key)
}

// More actions
const moreActions = computed(() => [
  { name: t('dashboard.actionSheet.retire'), value: 'retire' },
  { name: t('dashboard.actionSheet.activate'), value: 'activate' },
  { name: t('dashboard.actionSheet.export'), value: 'export' },
])

const sectionTitle = computed(() => {
  if (!activeStatus.value) {
    // "All" filter: use global total from statesSummary (matches StatusSummaryGrid)
    const count = dashboardStore.statesSummary?.total_count ?? dashboardStore.displayedAssets.length
    return t('dashboard.section.assetList', { count })
  }
  const pageInfo = dashboardStore.assetPageInfo.get(activeStatus.value)
  const count = pageInfo ? pageInfo.total : dashboardStore.displayedAssets.length
  const label = statusLabel(activeStatus.value)
  return `${label} (${count})`
})

const sortOptions = computed(() => [
  { text: t('asset.sortByValue'), value: 'current_value' },
  { text: t('asset.sortByDate'), value: 'purchase_date' },
  { text: t('asset.sortByName'), value: 'name' },
])

const currentSortLabel = computed(() => {
  const opt = sortOptions.value.find((o) => o.value === sortBy.value)
  return opt?.text ?? t('asset.sortByValue')
})

const SORT_CYCLE = ['current_value', 'purchase_date', 'name'] as const
function cycleSortOption() {
  const idx = SORT_CYCLE.indexOf(sortBy.value as (typeof SORT_CYCLE)[number])
  sortBy.value = SORT_CYCLE[(idx + 1) % SORT_CYCLE.length]
  onSearch()
}

function onCategoryChange(index: number) {
  activeCategoryIndex.value = index
  const targetStatus = activeStatus.value || 'in_use'
  if (index === 0) {
    activeCategoryId.value = null // "全部" tab
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
  if (!status) {
    // "All" filter: fetch across all statuses
    dashboardStore.fetchAllAssetsPage(20)
    dashboardStore.fetchCategoryCounts('in_use')
  } else {
    dashboardStore.resetAssetPagination(status)
    dashboardStore.fetchAssetsPage(status, 1, 20, '')
    dashboardStore.fetchCategoryCounts(status)
  }
}

// Type tab change (ported): map tab index → asset_type filter, reset pagination, refetch page 1
function onTypeTabChange(name: string | number) {
  const tab = typeof name === 'number' ? TYPE_TABS[name] : (name as (typeof TYPE_TABS)[number])
  const assetType = tab === 'all' ? null : (tab as 'physical' | 'financial')
  // Reset category filter when type changes (filtered category list changes)
  activeCategoryIndex.value = 0
  activeCategoryId.value = null
  // applyAssetFilters will reset pagination and fetch assets with updated filters
  dashboardStore.applyAssetFilters({ assetType, resetCategory: true })
}

// Search / sort change (ported): apply current search text + sort, reset pagination, refetch page 1
function onSearch() {
  dashboardStore.applyAssetFilters({ search: searchText.value, sortBy: sortBy.value })
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
  // Ignore Vant's emitted boolean — read current state and toggle manually
  if (!selectAll.value) {
    selectedIds.value = dashboardStore.displayedAssets.map((a) => a.id)
    selectAll.value = dashboardStore.displayedAssets.length > 0
  } else {
    selectedIds.value = []
    selectAll.value = false
  }
}

function toggleSelection(id: string) {
  const index = selectedIds.value.indexOf(id)
  if (index > -1) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
  const total = dashboardStore.displayedAssets.length
  selectAll.value = total > 0 && selectedIds.value.length === total
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }
  deleteSheet.value.show = true
}

async function executeBatchDelete() {
  increment()
  try {
    const res = await batchArchiveAssets(selectedIds.value)
    decrement()
    showToast(t('toast.assetDeleteBatchSuccess', { count: res.data.success_count }))
    deleteSheet.value.show = false
    selectionMode.value = false
    selectedIds.value = []
    selectAll.value = false
    await dashboardStore.fetchAll()
  } catch {
    decrement()
    showFailToast(t('toast.deleteFailed'))
  }
}

async function onMoreActionSelect(action: { value: string }) {
  if (selectedIds.value.length === 0) {
    showToast(t('toast.assetSelectFirst'))
    return
  }

  increment()
  try {
    switch (action.value) {
      case 'retire': {
        const res = await batchUpdateStatus(selectedIds.value, 'archived')
        decrement()
        showToast(t('toast.assetRetireBatchSuccess', { count: res.data.success_count }))
        break
      }
      case 'activate': {
        const res = await batchUpdateStatus(selectedIds.value, 'active')
        decrement()
        showToast(t('toast.assetActivateBatchSuccess', { count: res.data.success_count }))
        break
      }
      case 'export': {
        const res = await batchExportAssets(selectedIds.value)
        decrement()
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
    decrement()
    showFailToast(t('toast.operationFailed'))
  }
}

// ── Swipe actions (list view) ──
const assetSwipeRefs = new Map<string, ComponentPublicInstance<{ close: (pos?: string) => void }>>()
function setAssetSwipeRef(id: string) {
  return (el: unknown) => {
    if (el) assetSwipeRefs.set(id, el as ComponentPublicInstance<{ close: (pos?: string) => void }>)
    else assetSwipeRefs.delete(id)
  }
}
function closeAssetSwipe(id: string) {
  assetSwipeRefs.get(id)?.close('right')
}

// Only in_use and idle assets have swipe actions; sold/retired are terminal.
function assetHasSwipe(asset: Asset): boolean {
  return asset.status === 'in_use' || asset.status === 'idle'
}
function assetSwipeWidth(asset: Asset): number {
  if (!assetHasSwipe(asset)) return 0
  return 140 // 2 buttons × 70px
}

async function onSwipeMarkIdle(asset: Asset) {
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('toast.confirmMarkIdle', { name: asset.name }),
    })
    await retireAsset(asset.id)
    closeAssetSwipe(asset.id)
    showSuccessToast(t('toast.assetMarkedIdle'))
    await dashboardStore.fetchAll()
  } catch {
    // user cancelled dialog
  }
}

async function onSwipeReactivate(asset: Asset) {
  try {
    await reactivateAsset(asset.id)
    closeAssetSwipe(asset.id)
    showSuccessToast(t('toast.assetReactivated'))
    await dashboardStore.fetchAll()
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

async function onSwipeDeleteAsset(asset: Asset) {
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('toast.confirmDelete', { name: asset.name }),
    })
    await deleteAsset(asset.id)
    closeAssetSwipe(asset.id)
    showSuccessToast(t('toast.deleteSuccess'))
    await dashboardStore.fetchAll()
  } catch {
    // user cancelled dialog
  }
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

async function setViewMode(mode: 'card' | 'list') {
  if (updatingViewMode.value || viewMode.value === mode) return
  updatingViewMode.value = true
  try {
    await updateSettings({ view_mode: mode })
    await authStore.fetchMe()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    updatingViewMode.value = false
  }
}

onMounted(() => {
  // Attach scroll listener for freeze/unfreeze logic
  window.addEventListener('scroll', onScroll, { passive: true })
  const initialStatus = activeStatus.value || 'in_use'
  // Load category counts for secondary filter nav on initial render
  dashboardStore.fetchCategoryCounts(initialStatus)
  // Load initial asset page — required because van-list is gated by
  // v-if="filteredByCategoryAssets.length" and never fires @load on empty list.
  // When no status filter ("All"), fetch across all statuses.
  if (!activeStatus.value) {
    dashboardStore.fetchAllAssetsPage(20)
  } else {
    dashboardStore.fetchAssetsPage(initialStatus, 1, 20, '')
  }
})

// Prefetch exchange rates for all unique currencies in displayed assets
// AND the user's target currency, so formatConverted() in child components
// (AssetListItem, AssetCard) can show converted amounts on first render.
watch(
  [() => filteredByCategoryAssets.value, () => authStore.user?.default_currency],
  ([assets, targetCurrency]) => {
    const currencies = new Set<string>()
    // Prefetch target currency rate (user's default_currency)
    if (targetCurrency && targetCurrency !== 'CNY') {
      currencies.add(targetCurrency)
    }
    // Prefetch source currency rates for non-CNY assets
    for (const asset of assets) {
      if (asset.currency && asset.currency !== 'CNY') {
        currencies.add(asset.currency)
      }
    }
    for (const code of currencies) {
      ensureRate(code)
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})

// Exposed for unit tests (script-setup does not expose internals by default).
defineExpose({
  activeStatus,
  activeCategoryIndex,
  activeCategoryId,
  activeTypeIndex,
  searchText,
  sortBy,
  selectionMode,
  selectedIds,
  selectAll,
  onSearch,
  onTypeTabChange,
  onStatusSelect,
  onCategoryChange,
  onLoadMore,
  enterSelectionMode,
  exitSelectionMode,
  toggleSelection,
  toggleSelectAll,
})
</script>

<style scoped>
.asset-list-panel {
  background: var(--card-bg);
}

.asset-swipe {
  touch-action: pan-y;
  border-radius: 12px;
  overflow: hidden;
}

.swipe-action-btn {
  height: 100%;
  min-width: 70px;
  font-size: 13px;
  font-weight: 500;
}

/* Toolbar Icons */
:deep(.toolbar-slot) {
  display: flex;
  align-items: center;
  gap: 4px;
}
.toolbar-selection-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-xs);
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  border: none;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    opacity 0.15s ease;
}
.toolbar-selection-btn:active {
  transform: scale(0.95);
  opacity: 0.9;
}
[data-theme='dark'] .toolbar-selection-btn {
  background: var(--color-lavender);
  color: #010120;
}

/* Sticky Filter Bar: Status + Category */
.filter-bar-sticky {
  position: relative;
  z-index: 99;
}

.filter-bar-content {
  background: var(--card-bg);
}

.filter-bar-content--fixed {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 99;
  background: var(--card-bg);
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.08);
}

[data-theme='dark'] .filter-bar-content--fixed {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* Asset type tabs (ported) */
.type-tabs :deep(.van-tabs__line) {
  background: var(--color-coral);
  height: 2px;
  border-radius: var(--radius-full);
}
.type-tabs :deep(.van-tab--active) {
  color: var(--color-primary);
  font-weight: 600;
}
[data-theme='dark'] .type-tabs :deep(.van-tab--active) {
  color: var(--color-coral);
}

/* Category tab with icon */
.cat-tab-title {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.cat-tab-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 4px;
  flex-shrink: 0;
}
.cat-tab-svg {
  width: 10px;
  height: 10px;
  fill: white;
  color: white;
}

/* Category Navigation Container */
.category-nav-container {
  background: var(--card-bg);
}
.category-nav-container :deep(.van-tabs__wrap) {
  padding: 0 12px;
}
.category-nav-container :deep(.van-tabs__line) {
  background: var(--color-coral);
  height: 2px;
  border-radius: var(--radius-full);
}
.category-nav-container :deep(.van-tab--active) {
  color: var(--color-primary);
  font-weight: 600;
}
[data-theme='dark'] .category-nav-container :deep(.van-tab--active) {
  color: var(--color-coral);
}

/* Search & Sort bar (ported) */
.search-bar {
  display: flex;
  align-items: center;
  background: var(--card-bg);
}
.search-bar :deep(.van-search) {
  flex: 1;
  padding: 8px 12px;
}

/* Sort trigger button */
.sort-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  margin-right: 8px;
  border-radius: var(--radius-full);
  background: var(--color-primary-light);
  color: var(--color-primary);
  border: none;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.sort-trigger:active {
  transform: scale(0.95);
  opacity: 0.8;
}
.sort-trigger-icon {
  font-size: 14px;
}
.sort-trigger-label {
  line-height: 1;
}
[data-theme='dark'] .sort-trigger {
  background: rgba(189, 187, 255, 0.15);
  color: var(--color-lavender);
}

/* Asset Section */
.asset-section {
  padding: 0 12px;
  margin-top: 10px;
}

/* Sentinel for detecting asset list scroll position */
.asset-list-top-sentinel {
  height: 1px;
  width: 100%;
  visibility: hidden;
  pointer-events: none;
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
.view-mode-toggle {
  display: flex;
  gap: 4px;
}
.view-toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-xs);
  background: var(--card-bg);
  color: var(--text-secondary);
  border: 1px solid var(--separator);
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.view-toggle-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.view-toggle-btn:active {
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  border-color: var(--van-primary-color);
}
[data-theme='dark'] .view-toggle-btn {
  border-color: rgba(255, 255, 255, 0.12);
}
[data-theme='dark'] .view-toggle-btn:active {
  background: var(--color-lavender);
  color: #010120;
  border-color: var(--color-lavender);
}
.asset-list {
  /* cards have their own margin-bottom */
}

/* Group items wrapper for collapse transition */
.group-items {
  overflow: hidden;
}

/* Card mode: 2-column grid */
.group-items--grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding-bottom: 4px;
}

/* Collapse transition */
.collapse-enter-active,
.collapse-leave-active {
  transition: all 200ms ease;
  max-height: 2000px;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .collapse-enter-active,
  .collapse-leave-active {
    transition: none;
  }
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
  padding: 6px 12px;
  background: var(--card-bg);
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  margin-bottom: 0;
  gap: 8px;
}
[data-theme='dark'] .selection-header {
  border-color: rgba(255, 255, 255, 0.12);
}
.selection-count {
  flex: 1;
  text-align: center;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
}
[data-theme='dark'] .selection-count {
  color: var(--color-lavender);
}
.selection-done-btn {
  min-width: 60px;
  padding: 0 16px;
  height: 32px;
  flex-shrink: 0;
}
.selection-actions {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 5px 12px;
  background: var(--card-bg);
  border-radius: 0 0 8px 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-top: none;
  margin-bottom: 12px;
  box-shadow: 0 4px 10px rgba(1, 1, 32, 0.1);
}
[data-theme='dark'] .selection-actions {
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
}
.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  color: var(--text-secondary);
  transition:
    color 0.15s,
    background 0.15s;
  min-width: 44px;
  min-height: 44px;
  justify-content: center;
}
.action-btn span {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: -0.1px;
}
.action-btn:active {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary);
}
[data-theme='dark'] .action-btn:active {
  background: rgba(255, 255, 255, 0.08);
}
.selection-list-cards {
  padding: 0;
}

/* FAB */
.fab {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-elevated);
  z-index: 20;
  cursor: pointer;
  border: none;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    background 0.2s ease;
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
  transition:
    opacity 0.2s ease,
    transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fab-menu-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
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
  transition:
    transform 0.1s ease,
    box-shadow 0.1s ease;
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
</style>
