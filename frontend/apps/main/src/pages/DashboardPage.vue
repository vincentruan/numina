<template>
  <div class="dashboard-page" role="main" :aria-label="t('dashboard.aria.pageTitle')">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Skeleton Loading State -->
      <DashboardSkeleton v-if="dashboardStore.loading && !overview?.asset_count" />

      <!-- Empty State for new users -->
      <div v-else-if="!dashboardStore.loading && overview?.asset_count === 0" class="empty-dashboard">
        <van-empty :description="t('dashboard.emptyState.startRecording')">
          <van-button type="primary" size="small" @click="$router.push('/assets/new')">
            {{ t('dashboard.emptyState.addAssetBtn') }}
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <!-- Hero section: colored background ends here -->
        <div class="hero-section">
          <NetWorthCard
            :net-worth="overview?.net_worth || 0"
            :total-assets="overview?.total_assets || 0"
            :total-liabilities="overview?.total_liabilities || 0"
            :total-daily-cost="overview?.total_daily_cost || 0"
            :asset-count="overview?.asset_count || 0"
            :month-over-month-change="overview?.month_over_month_change"
            :month-over-month-change-amount="overview?.month_over_month_change_amount"
          />
        </div>

        <!-- D2/A1a: finance_coach proactive suggestions card (Plan B T5) -->
        <FinanceCoachCard />

        <!-- Smart Reminders (includes expiring soon + upcoming payments + idle + AI reminders) -->
        <SmartRemindersCard
          :idle-assets="dashboardStore.lowUsageAssets.filter((a) => a.usage_frequency === 'idle')"
          :expiring-assets="dashboardStore.expiringSoonAssets"
          :upcoming-payments="upcomingPayments"
          @select-status="onStatusSelect"
        />

        <!-- D1: Pending approvals (owner-only; component self-gates on non-empty list) -->
        <PendingApprovalsSection v-if="authStore.user?.role === 'owner'" />

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
        </div>
      </template>

      <div class="bottom-spacer" />
    </van-pull-refresh>

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

    <!-- New User Onboarding Overlay -->
    <OnboardingOverlay :visible="showOnboarding" @complete="onOnboardingComplete" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { showToast, showFailToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { usePageLoading } from '@/composables/usePageLoading'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useChoreStore } from '@/stores/chore'
import { batchArchiveAssets, batchUpdateStatus, batchExportAssets } from '@/api/assets'
import { getUpcomingPayments } from '@/api/dashboard'
import { updateSettings } from '@/api/auth'
import type { UpcomingPaymentItem } from '@/api/dashboard'

import { getIconId } from '@/utils/icon'
import NetWorthCard from '@/components/dashboard/NetWorthCard.vue'
import StatusSummaryGrid from '@/components/dashboard/StatusSummaryGrid.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import SmartRemindersCard from '@/components/dashboard/SmartRemindersCard.vue'
import FinanceCoachCard from '@/components/dashboard/FinanceCoachCard.vue'
import PendingApprovalsSection from '@/components/dashboard/PendingApprovalsSection.vue'
import OnboardingOverlay from '@/components/common/OnboardingOverlay.vue'

const { t } = useI18n()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const dashboardStore = useDashboardStore()
const authStore = useAuthStore()
const choreStore = useChoreStore()
const viewMode = computed(() => authStore.user?.view_mode || 'card')
const updatingViewMode = ref(false)
const refreshing = ref(false)
const activeStatus = ref<string | null>(null)

// Upcoming payments
const upcomingPayments = ref<UpcomingPaymentItem[]>([])

// Pagination state
const loadingMore = ref(false)

// Category view
const activeCategoryIndex = ref(0)
const activeCategoryId = ref<string | null>(null) // null = show all

// Selection mode
const selectionMode = ref(false)
const selectedIds = ref<string[]>([])
const selectAll = ref(false)

// Toolbar
const showMoreActions = ref(false)

// FAB menu
const fabMenuOpen = ref(false)

// Onboarding overlay
const showOnboarding = ref(false)

function onOnboardingComplete() {
  showOnboarding.value = false
  localStorage.setItem('onboarding_completed', 'true')
}

function maybeShowOnboarding() {
  if (localStorage.getItem('onboarding_completed') === 'true') return
  // Only show when there are no assets yet
  if ((overview.value?.asset_count ?? 0) === 0) {
    showOnboarding.value = true
  }
}

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

const overview = computed(() => dashboardStore.overview)
// Category counts from backend (full counts, not page-limited)
const categoriesWithAssetCount = computed(() => {
  return dashboardStore.categoryCounts
    .map((c) => ({ id: c.id, name: c.name, icon: c.icon, color: c.color, count: c.count }))
    .sort((a, b) => b.count - a.count)
})

// Asset list: displayedAssets is already filtered by backend (status + optional category)
const filteredByCategoryAssets = computed(() => dashboardStore.displayedAssets)

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
  const status = activeStatus.value || 'in_use'
  const pageInfo = dashboardStore.assetPageInfo.get(status)
  // Use server-side total count when available, fallback to displayed assets count
  const count = pageInfo ? pageInfo.total : dashboardStore.displayedAssets.length
  if (!activeStatus.value) {
    return t('dashboard.section.assetList', { count })
  }
  const label = statusLabel(activeStatus.value)
  return `${label} (${count})`
})

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

  try {
    await showConfirmDialog({
      title: t('dashboard.dialog.confirmDeleteTitle'),
      message: t('dashboard.dialog.confirmDeleteMessage', { count: selectedIds.value.length }),
    })
    increment()
    try {
      const res = await batchArchiveAssets(selectedIds.value)
      decrement()
      showToast(t('toast.assetDeleteBatchSuccess', { count: res.data.success_count }))
      selectionMode.value = false
      selectedIds.value = []
      selectAll.value = false
      await dashboardStore.fetchAll()
    } catch {
      decrement()
      showFailToast(t('toast.deleteFailed'))
    }
  } catch {
    // User cancelled
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
  // Fetch dashboard bundle first, then load first page of assets
  dashboardStore.fetchAll().then(() => {
    const initialStatus = activeStatus.value || 'in_use'
    dashboardStore.fetchAssetsPage(initialStatus, 1, 20, undefined)
    dashboardStore.fetchCategoryCounts(initialStatus)
    maybeShowOnboarding()
  })
  if (authStore.user?.role === 'owner') {
    choreStore.fetchPendingApprovals()
  }

  // Fetch upcoming liability payments
  getUpcomingPayments()
    .then((res) => {
      upcomingPayments.value = res.data.items
    })
    .catch(() => {
      // Non-critical: silently ignore if endpoint not available
    })

  // Attach scroll listener for freeze/unfreeze logic
  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})

</script>

<style scoped>
.dashboard-page {
  background: var(--card-bg);
  min-height: 100vh;
}

.hero-section {
  background: var(--bg-secondary);
}

.stale-hint {
  color: var(--van-gray-6);
  font-size: 12px;
  text-align: center;
  margin: 4px 0;
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
