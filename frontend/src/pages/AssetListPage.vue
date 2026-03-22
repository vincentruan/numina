<template>
  <div class="asset-list-page">
    <PageHeader title="资产" :show-back="false" />

    <!-- Filter Tabs -->
    <van-tabs v-model:active="activeTab" @change="onTabChange" sticky>
      <van-tab title="全部" name="all" />
      <van-tab title="实物" name="physical" />
      <van-tab title="金融" name="financial" />
    </van-tabs>

    <!-- Search & Sort -->
    <div class="search-bar">
      <van-search v-model="searchText" placeholder="搜索资产" @search="onSearch" @clear="onSearch" />
      <van-dropdown-menu>
        <van-dropdown-item v-model="sortBy" :options="sortOptions" @change="onSearch" />
      </van-dropdown-menu>
    </div>

    <!-- Asset List -->
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <div class="asset-list" v-if="assetStore.assets.length">
        <AssetCard
          v-for="asset in assetStore.assets"
          :key="asset.id"
          :asset="asset"
          @click="$router.push(`/assets/${asset.id}`)"
        />
      </div>
      <EmptyState v-else description="暂无资产记录">
        <van-button size="small" type="primary" @click="$router.push('/assets/new')">
          添加资产
        </van-button>
      </EmptyState>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAssetStore } from '@/stores/asset'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AssetCard from '@/components/asset/AssetCard.vue'

const assetStore = useAssetStore()
const route = useRoute()
const refreshing = ref(false)
const activeTab = ref('all')
const searchText = ref('')
const sortBy = ref('current_value')

const sortOptions = [
  { text: '按价值', value: 'current_value' },
  { text: '按日期', value: 'purchase_date' },
  { text: '按名称', value: 'name' }
]

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
  background: #f7f8fa;
  min-height: 100vh;
}
.search-bar {
  display: flex;
  align-items: center;
  background: #fff;
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
</style>
