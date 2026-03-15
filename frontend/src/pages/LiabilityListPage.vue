<template>
  <div class="liability-list-page">
    <PageHeader title="负债" :show-back="false" />

    <van-tabs v-model:active="activeTab" @change="onTabChange" sticky>
      <van-tab title="还款中" name="active" />
      <van-tab title="已结清" name="inactive" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Summary -->
      <div v-if="liabilityStore.liabilities.length" class="summary-bar">
        <span>共 {{ liabilityStore.liabilities.length }} 笔</span>
        <span>合计 ¥{{ totalAmount.toLocaleString() }}</span>
      </div>

      <div class="liability-list" v-if="liabilityStore.liabilities.length">
        <LiabilityCard
          v-for="item in liabilityStore.liabilities"
          :key="item.id"
          :liability="item"
          @click="$router.push(`/liabilities/${item.id}`)"
        />
      </div>
      <EmptyState v-else description="暂无负债记录">
        <van-button size="small" type="primary" @click="$router.push('/liabilities/new')">
          添加负债
        </van-button>
      </EmptyState>
    </van-pull-refresh>

    <!-- FAB -->
    <div class="fab" @click="$router.push('/liabilities/new')">
      <van-icon name="plus" size="24" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLiabilityStore } from '@/stores/liability'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LiabilityCard from '@/components/liability/LiabilityCard.vue'

const liabilityStore = useLiabilityStore()
const refreshing = ref(false)
const activeTab = ref('active')

const totalAmount = computed(() =>
  liabilityStore.liabilities.reduce((sum, l) => sum + l.remaining_amount, 0)
)

function onTabChange() {
  liabilityStore.fetchLiabilities({ is_active: activeTab.value === 'active' })
}

async function onRefresh() {
  await liabilityStore.fetchLiabilities({ is_active: activeTab.value === 'active' })
  refreshing.value = false
}

onMounted(() => {
  liabilityStore.fetchLiabilities({ is_active: true })
})
</script>

<style scoped>
.liability-list-page {
  background: #f7f8fa;
  min-height: 100vh;
}
.summary-bar {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  font-size: 12px;
  color: #969799;
}
.liability-list {
  padding: 0 12px;
}
.fab {
  position: fixed;
  right: 16px;
  bottom: 70px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #1989fa;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(25, 137, 250, 0.4);
  z-index: 10;
}
</style>
