<template>
  <div class="asset-list-page" role="main" aria-label="资产列表">
    <PageHeader :title="t('asset.title')" :show-back="false" />

    <!-- Filter Tabs -->
    <van-tabs v-model:active="activeTab" sticky aria-label="资产类型筛选" @change="onTabChange">
      <van-tab :title="t('asset.all')" name="all" />
      <van-tab :title="t('asset.physical')" name="physical" />
      <van-tab :title="t('asset.financial')" name="financial" />
    </van-tabs>

    <!-- Category Filter Chips -->
    <div v-if="categoryChips.length > 1" class="category-chips">
      <van-tag
        v-for="chip in categoryChips"
        :key="chip.id"
        :type="selectedCategoryId === chip.id ? 'primary' : 'default'"
        size="medium"
        class="category-chip"
        @click="onCategoryChipClick(chip.id)"
      >
        <svg v-if="chip.icon && chip.icon.startsWith('icon-')" class="chip-icon" aria-hidden="true">
          <use :href="`#${getIconId(chip.icon)}`" />
        </svg>
        <span v-else-if="chip.icon" class="chip-emoji">{{ chip.icon }}</span>
        <span class="chip-name">{{ chip.name }}</span>
      </van-tag>
    </div>

    <!-- Search & Sort -->
    <div class="search-bar">
      <van-search
        v-model="searchText"
        :placeholder="t('asset.search')"
        aria-label="搜索资产"
        @search="onSearch"
        @clear="onSearch"
      />
      <van-dropdown-menu>
        <van-dropdown-item v-model="sortBy" :options="sortOptions" aria-label="排序方式" @change="onSearch" />
      </van-dropdown-menu>
    </div>

    <!-- Selection Mode Bar -->
    <div v-if="selectionMode" class="selection-bar" role="toolbar" aria-label="批量操作工具栏">
      <span class="selection-count" aria-live="polite">
        {{ t('dashboard.selectedCount', { count: selectedAssets.length }) }}
      </span>
      <van-button size="small" aria-label="全选" @click="selectAll">
        {{ isAllSelected ? t('currency.deselectAll') : t('dashboard.selectAll') }}
      </van-button>
      <van-button size="small" type="danger" :disabled="selectedAssets.length === 0" aria-label="批量删除" @click="confirmBatchDelete">
        {{ t('common.delete') }}
      </van-button>
      <van-button size="small" aria-label="退出选择模式" @click="exitSelectionMode">
        {{ t('common.cancel') }}
      </van-button>
    </div>

    <!-- Asset List -->
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Loading Skeleton -->
      <div v-if="assetStore.loading" class="asset-list">
        <AssetCardSkeleton v-for="i in 3" :key="i" />
      </div>
      <div v-else-if="assetStore.assets.length">
        <!-- Card View with Virtual List (for large datasets) -->
        <template v-if="viewMode === 'card'">
          <RecycleScroller
            v-if="assetStore.assets.length > 100"
            class="virtual-list"
            :items="assetStore.assets"
            :item-size="110"
            key-field="id"
            :buffer="200"
            role="list"
            aria-label="资产卡片列表"
          >
            <template #default="{ item }">
              <AssetCard
                :asset="item"
                :selectable="selectionMode"
                :selected="isSelected(item.id)"
                @click="onAssetClick(item)"
                @longpress="startSelectionMode(item.id)"
                @update:selected="toggleSelection(item.id)"
              />
            </template>
          </RecycleScroller>
          <div v-else class="asset-list" role="list" aria-label="资产卡片列表">
            <AssetCard
              v-for="asset in assetStore.assets"
              :key="asset.id"
              :asset="asset"
              :selectable="selectionMode"
              :selected="isSelected(asset.id)"
              @click="onAssetClick(asset)"
              @longpress="startSelectionMode(asset.id)"
              @update:selected="toggleSelection(asset.id)"
            />
          </div>
        </template>
        <!-- List View with Virtual List -->
        <template v-else>
          <RecycleScroller
            v-if="assetStore.assets.length > 100"
            class="virtual-list-view"
            :items="assetStore.assets"
            :item-size="72"
            key-field="id"
            :buffer="200"
            role="list"
            aria-label="资产列表视图"
          >
            <template #default="{ item }">
              <AssetListItem
                :asset="item"
                :selectable="selectionMode"
                :selected="isSelected(item.id)"
                @click="onAssetClick(item)"
                @longpress="startSelectionMode(item.id)"
                @update:selected="toggleSelection(item.id)"
              />
            </template>
          </RecycleScroller>
          <div v-else class="asset-list-view" role="list" aria-label="资产列表视图">
            <AssetListItem
              v-for="asset in assetStore.assets"
              :key="asset.id"
              :asset="asset"
              :selectable="selectionMode"
              :selected="isSelected(asset.id)"
              @click="onAssetClick(asset)"
              @longpress="startSelectionMode(asset.id)"
              @update:selected="toggleSelection(asset.id)"
            />
          </div>
        </template>
      </div>
      <EmptyState v-else :description="t('common.noData')">
        <van-button size="small" type="primary" @click="$router.push('/assets/new')">
          {{ t('asset.addAsset') }}
        </van-button>
      </EmptyState>
    </van-pull-refresh>

    <!-- Batch Delete Confirmation Dialog -->
    <van-dialog
      v-model:show="showDeleteDialog"
      :title="t('asset.batchDelete')"
      :message="`确定要删除 ${selectedAssets.length} 项资产吗？此操作不可撤销。`"
      show-cancel-button
      aria-modal="true"
      aria-label="批量删除确认"
      @confirm="executeBatchDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useAssetStore } from '@/stores/asset'
import { useAuthStore } from '@/stores/auth'
import { useCategoryStore } from '@/stores/category'
import { getIconId } from '@/utils/icon'
import { RecycleScroller } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import AssetCardSkeleton from '@/components/common/AssetCardSkeleton.vue'
import type { Asset } from '@/types'

const { t } = useI18n()
const router = useRouter()
const assetStore = useAssetStore()
const authStore = useAuthStore()
const categoryStore = useCategoryStore()
const route = useRoute()
const refreshing = ref(false)
const activeTab = ref('all')
const searchText = ref('')
const sortBy = ref('current_value')
const selectedCategoryId = ref('')

// Category chips: "全部" + categories filtered by active tab
const categoryChips = computed(() => {
  const type = activeTab.value === 'all' ? undefined : activeTab.value
  const filtered = type
    ? categoryStore.categories.filter(c => c.asset_type === type)
    : categoryStore.categories
  return [{ id: '' as string, icon: '', name: t('asset.all') }, ...filtered]
})

function onCategoryChipClick(id: string) {
  selectedCategoryId.value = id
  assetStore.fetchAssets(buildFilters())
}

// Selection mode state
const selectionMode = ref(false)
const selectedAssets = ref<string[]>([])
const showDeleteDialog = ref(false)

const viewMode = computed(() => authStore.user?.view_mode || 'card')

const sortOptions = computed(() => [
  { text: t('asset.sortByValue'), value: 'current_value' },
  { text: t('asset.sortByDate'), value: 'purchase_date' },
  { text: t('asset.sortByName'), value: 'name' }
])

function buildFilters() {
  return {
    asset_type: activeTab.value === 'all' ? undefined : activeTab.value as 'physical' | 'financial',
    category_id: selectedCategoryId.value || undefined,
    search: searchText.value || undefined,
    sort_by: sortBy.value
  }
}

function onTabChange() {
  selectedCategoryId.value = ''
  assetStore.fetchAssets(buildFilters())
}

function onSearch() {
  assetStore.fetchAssets(buildFilters())
}

async function onRefresh() {
  await assetStore.fetchAssets(buildFilters())
  refreshing.value = false
}

// Selection mode functions
function startSelectionMode(assetId: string) {
  selectionMode.value = true
  selectedAssets.value = [assetId]
}

function isSelected(assetId: string): boolean {
  return selectedAssets.value.includes(assetId)
}

function toggleSelection(assetId: string) {
  const index = selectedAssets.value.indexOf(assetId)
  if (index > -1) {
    selectedAssets.value.splice(index, 1)
  } else {
    selectedAssets.value.push(assetId)
  }
}

function selectAll() {
  if (isAllSelected.value) {
    selectedAssets.value = []
  } else {
    selectedAssets.value = assetStore.assets.map(a => a.id)
  }
}

const isAllSelected = computed(() => 
  selectedAssets.value.length === assetStore.assets.length && assetStore.assets.length > 0
)

function exitSelectionMode() {
  selectionMode.value = false
  selectedAssets.value = []
}

function onAssetClick(asset: Asset) {
  if (selectionMode.value) {
    toggleSelection(asset.id)
  } else {
    router.push(`/assets/${asset.id}`)
  }
}

function confirmBatchDelete() {
  showDeleteDialog.value = true
}

async function executeBatchDelete() {
  try {
    // Delete each selected asset
    for (const assetId of selectedAssets.value) {
      await assetStore.deleteAsset(assetId)
    }
    showToast(t('toast.assetDeletedCount', { count: selectedAssets.value.length }))
    exitSelectionMode()
    await assetStore.fetchAssets(buildFilters())
  } catch {
    showToast(t('toast.deleteFailed'))
  }
}

// Keyboard navigation support
function handleKeyDown(event: KeyboardEvent) {
  if (selectionMode.value) {
    if (event.key === 'Escape') {
      exitSelectionMode()
    } else if (event.key === 'a' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      selectAll()
    }
  }
}

onMounted(() => {
  const statusParam = route.query.status as string | undefined
  categoryStore.fetchCategories()
  assetStore.fetchAssets({ ...buildFilters(), status: statusParam })
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.asset-list-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
/* Category Filter Chips */
.category-chips {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  overflow-x: auto;
  background: var(--card-bg);
  scrollbar-width: none;
}
.category-chips::-webkit-scrollbar {
  display: none;
}
.category-chip {
  flex-shrink: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.chip-icon {
  width: 14px;
  height: 14px;
  fill: currentColor;
}
.chip-emoji {
  font-size: 12px;
  line-height: 1;
}
.chip-name {
  font-size: 12px;
  line-height: 1;
}

.search-bar {
  display: flex;
  align-items: center;
  background: var(--card-bg);
}
.search-bar :deep(.van-search) {
  flex: 1;
}
.search-bar :deep(.van-dropdown-menu) {
  width: 100px;
}
.search-bar :deep(.van-dropdown-menu__bar) {
  box-shadow: none;
}

/* Selection Mode Bar */
.selection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--color-action-primary);
  color: #fff;
  gap: 8px;
}
[data-theme='dark'] .selection-bar {
  background: var(--color-action-primary);
}
.selection-count {
  font-size: 14px;
  font-weight: 500;
}
.selection-bar :deep(.van-button) {
  --van-button-default-background-color: rgba(255, 255, 255, 0.2);
  --van-button-primary-background-color: rgba(255, 255, 255, 0.3);
  --van-button-danger-background-color: rgba(238, 10, 36, 0.8);
  color: #fff;
}

/* Asset List Styles */
.asset-list {
  padding: 8px 12px;
}
.asset-list-view {
  background: var(--card-bg);
}

/* Virtual List Styles */
.virtual-list {
  padding: 8px 12px;
}
.virtual-list-view {
  background: var(--card-bg);
}

/* Accessibility - Focus styles */
:deep([role="list"]:focus-visible) {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}
</style>