<template>
  <div class="asset-list-page">
    <PageHeader :title="t('asset.title')" :show-back="false" />

    <!-- Filter Tabs -->
    <van-tabs v-model:active="activeTab" @change="onTabChange" sticky>
      <van-tab :title="t('asset.all')" name="all" />
      <van-tab :title="t('asset.physical')" name="physical" />
      <van-tab :title="t('asset.financial')" name="financial" />
    </van-tabs>

    <!-- Search & Sort -->
    <div class="search-bar">
      <van-search v-model="searchText" :placeholder="t('asset.search')" @search="onSearch" @clear="onSearch" />
      <van-dropdown-menu>
        <van-dropdown-item v-model="sortBy" :options="sortOptions" @change="onSearch" />
      </van-dropdown-menu>
    </div>

    <!-- Asset List -->
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Loading Skeleton -->
      <div v-if="assetStore.loading" class="asset-list">
        <AssetCardSkeleton v-for="i in 3" :key="i" />
      </div>
      <div v-else-if="assetStore.assets.length">
        <!-- Card View -->
        <div v-if="viewMode === 'card'" class="asset-list">
          <AssetCard
            v-for="asset in assetStore.assets"
            :key="asset.id"
            :asset="asset"
            @click="$router.push(`/assets/${asset.id}`)"
          />
        </div>
        <!-- List View -->
        <div v-else class="asset-list-view">
          <AssetListItem
            v-for="asset in assetStore.assets"
            :key="asset.id"
            :asset="asset"
            @click="$router.push(`/assets/${asset.id}`)"
          />
        </div>
      </div>
      <EmptyState v-else :description="t('common.noData')">
        <van-button size="small" type="primary" @click="$router.push('/assets/new')">
          {{ t('asset.addAsset') }}
        </van-button>
      </EmptyState>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAssetStore } from '@/stores/asset'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AssetCard from '@/components/asset/AssetCard.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import AssetCardSkeleton from '@/components/common/AssetCardSkeleton.vue'

const { t } = useI18n()
const assetStore = useAssetStore()
const authStore = useAuthStore()
const route = useRoute()
const refreshing = ref(false)
const activeTab = ref('all')
const searchText = ref('')
const sortBy = ref('current_value')

const viewMode = computed(() => authStore.user?.view_mode || 'card')

const sortOptions = computed(() => [
  { text: t('asset.sortByValue'), value: 'current_value' },
  { text: t('asset.sortByDate'), value: 'purchase_date' },
  { text: t('asset.sortByName'), value: 'name' }
])

function buildFilters() {
  return {
    asset_type: activeTab.value === 'all' ? undefined : activeTab.value as 'physical' | 'financial',
    search: searchText.value || undefined,
    sort_by: sortBy.value
  }
}

function onTabChange() {
  assetStore.fetchAssets(buildFilters())
}

function onSearch() {
  assetStore.fetchAssets(buildFilters())
}

async function onRefresh() {
  await assetStore.fetchAssets(buildFilters())
  refreshing.value = false
}

onMounted(() => {
  const statusParam = route.query.status as string | undefined
  assetStore.fetchAssets({ ...buildFilters(), status: statusParam })
})
</script>

<style scoped>
.asset-list-page {
  background: var(--bg-secondary);
  min-height: 100vh;
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
.asset-list {
  padding: 8px 12px;
}
.asset-list-view {
  background: var(--card-bg);
}
</style>
