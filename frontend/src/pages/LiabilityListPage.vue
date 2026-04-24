<template>
  <div class="liability-list-page">
    <PageHeader title="负债" :show-back="false" />

    <van-tabs v-model:active="activeTab" sticky @change="onTabChange">
      <van-tab title="还款中" name="active" />
      <van-tab title="已结清" name="inactive" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Summary Banner -->
      <div v-if="liabilityStore.liabilities.length" class="summary-banner">
        <div class="summary-top">
          <div class="summary-main">
            <div class="summary-label">{{ activeTab === 'active' ? '待还总额' : '已结清总额' }}</div>
            <div class="summary-amount">¥{{ formatAmount(totalAmount) }}</div>
          </div>
          <div class="summary-count">
            <span class="count-num">{{ liabilityStore.liabilities.length }}</span>
            <span class="count-unit">笔</span>
          </div>
        </div>
        <template v-if="activeTab === 'active' && totalOriginal > 0">
          <div class="summary-progress-bar">
            <div class="summary-progress-fill" :style="{ width: repaidPercent + '%' }" />
          </div>
          <div class="summary-progress-text">
            <span>总还款进度</span>
            <span class="summary-percent">{{ repaidPercent }}%</span>
          </div>
        </template>
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
      <van-icon name="plus" size="22" />
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

function formatAmount(amount: number): string {
  if (amount >= 100000000) return (amount / 100000000).toFixed(2) + '亿'
  if (amount >= 10000) return (amount / 10000).toFixed(1) + '万'
  return amount.toLocaleString('zh-CN')
}

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
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Crimson+Pro:wght@600&display=swap');

.liability-list-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 80px;
}

/* Summary Banner */
.summary-banner {
  margin: 12px 12px 4px;
  background: linear-gradient(135deg, #991b1b 0%, #dc2626 60%, #ea580c 100%);
  border-radius: 16px;
  padding: 20px;
  color: #fff;
}

.summary-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.summary-label {
  font-size: 13px;
  opacity: 0.8;
  margin-bottom: 6px;
  letter-spacing: 0.3px;
}

.summary-amount {
  font-family: 'Crimson Pro', Georgia, serif;
  font-size: 36px;
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.summary-count {
  text-align: right;
  padding-top: 4px;
}

.count-num {
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 28px;
  font-weight: 600;
  line-height: 1;
}

.count-unit {
  font-size: 14px;
  opacity: 0.8;
  margin-left: 2px;
}

.summary-progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.summary-progress-fill {
  height: 100%;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 3px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.summary-progress-text {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  opacity: 0.85;
}

.summary-percent {
  font-weight: 600;
}

/* List */
.liability-list {
  padding: 8px 12px 0;
}

/* FAB */
.fab {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #dc2626;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(220, 38, 38, 0.45);
  z-index: 10;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.fab:active {
  transform: scale(0.93);
  box-shadow: 0 2px 8px rgba(220, 38, 38, 0.4);
}

[data-theme='dark'] .fab {
  box-shadow: 0 4px 16px rgba(220, 38, 38, 0.6);
}
</style>
