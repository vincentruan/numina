<template>
  <div class="liability-list-page">
    <PageHeader title="负债" :show-back="false" />

    <van-tabs v-model:active="activeTab" sticky @change="onTabChange">
      <van-tab title="还款中" name="active" />
      <van-tab title="已结清" name="inactive" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Summary -->
      <div v-if="liabilityStore.liabilities.length" class="summary-bar">
        <div class="summary-row">
          <span>共 {{ liabilityStore.liabilities.length }} 笔</span>
          <span>剩余 ¥{{ totalAmount.toLocaleString() }}</span>
        </div>
        <div v-if="activeTab === 'active'" class="repay-progress">
          <div class="repay-progress-bar">
            <div class="repay-progress-fill" :style="{ width: repaidPercent + '%' }" />
          </div>
          <span class="repay-percent">已还 {{ repaidPercent }}%</span>
        </div>
      </div>

      <div v-if="liabilityStore.liabilities.length" class="liability-list">
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

const totalOriginal = computed(() =>
  liabilityStore.liabilities.reduce((sum, l) => sum + (l.original_amount ?? l.remaining_amount), 0)
)

const repaidPercent = computed(() => {
  if (totalOriginal.value <= 0) return 0
  const repaid = totalOriginal.value - totalAmount.value
  return Math.round((repaid / totalOriginal.value) * 100)
})

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
  background: var(--bg-secondary);
  min-height: 100vh;
}
.summary-bar {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-tertiary);
  background: var(--card-bg);
  margin-bottom: 8px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.repay-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}
.repay-progress-bar {
  flex: 1;
  height: 6px;
  background: rgba(25, 137, 250, 0.1);
  border-radius: 3px;
  overflow: hidden;
}
[data-theme='dark'] .repay-progress-bar {
  background: rgba(25, 137, 250, 0.15);
}
.repay-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1989fa, #07c160);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.repay-percent {
  font-size: 11px;
  color: #07c160;
  font-weight: 500;
  white-space: nowrap;
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
[data-theme='dark'] .fab {
  box-shadow: 0 4px 12px rgba(25, 137, 250, 0.6);
}
</style>
