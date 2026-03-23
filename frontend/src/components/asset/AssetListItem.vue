<template>
  <div class="asset-list-item" @click="$emit('click')">
    <div class="item-main">
      <div class="item-icon" :style="{ background: asset.category?.color || '#1989fa' }">
        {{ asset.category?.icon || '📦' }}
      </div>
      <div class="item-info">
        <div class="item-header">
          <span class="item-name">{{ asset.name }}</span>
          <van-tag :type="statusType" size="medium" class="item-status-tag">{{ statusText }}</van-tag>
        </div>
        <div class="item-meta">
          <span class="item-price-days">¥{{ formatPrice(asset.purchase_price) }} | {{ daysUsed }}天</span>
        </div>
        <div class="item-cost">
          <span v-if="asset.daily_cost != null && asset.daily_cost > 0" class="item-daily">
            ¥{{ asset.daily_cost.toFixed(2) }}/天
          </span>
        </div>

        <!-- Progress bar section -->
        <div v-if="targetDays > 0" class="item-progress-section">
          <div class="progress-bar-wrapper">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>
              <div class="progress-marker" :style="{ left: `${progressPercent}%` }"></div>
            </div>
          </div>
          <div class="progress-info">
            <span class="progress-target">目标：{{ targetDays }}天</span>
            <span class="progress-remaining">还剩{{ remainingDays }}天</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Asset } from '@/types'

const props = defineProps<{
  asset: Asset
}>()

defineEmits<{
  click: []
}>()

const statusType = computed(() => {
  switch (props.asset.status) {
    case 'in_use': return 'primary'
    case 'idle': return 'warning'
    case 'sold': return 'danger'
    case 'retired': return 'default'
    default: return 'primary'
  }
})

const statusText = computed(() => {
  switch (props.asset.status) {
    case 'in_use': return '服役中'
    case 'idle': return '闲置'
    case 'sold': return '已出售'
    case 'retired': return '已退役'
    default: return props.asset.status
  }
})

const daysUsed = computed(() => {
  if (!props.asset.purchase_date) return 0
  const purchase = new Date(props.asset.purchase_date)
  const now = new Date()
  return Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
})

const targetDays = computed(() => props.asset.expected_lifespan_days || 0)

const remainingDays = computed(() => {
  if (!targetDays.value) return 0
  return Math.max(0, targetDays.value - daysUsed.value)
})

const progressPercent = computed(() => {
  if (!targetDays.value) return 0
  return Math.min(100, (daysUsed.value / targetDays.value) * 100)
})

function formatPrice(price: number | null | undefined): string {
  if (price == null) return '-'
  if (price >= 10000) {
    return `${(price / 10000).toFixed(1)}万`
  }
  return price.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}
</script>

<style scoped>
.asset-list-item {
  display: flex;
  background: #fff;
  padding: 12px 14px;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
  transition: background 0.15s;
}
.asset-list-item:active {
  background: #f7f8fa;
}
.asset-list-item:last-child {
  border-bottom: none;
}

.item-main {
  display: flex;
  width: 100%;
  gap: 10px;
}

.item-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.item-status-tag {
  flex-shrink: 0;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-price-days {
  font-size: 12px;
  color: #646566;
}

.item-cost {
  display: flex;
  align-items: center;
}

.item-daily {
  font-size: 13px;
  font-weight: 600;
  color: #ff976a;
}

/* Progress section */
.item-progress-section {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-bar-wrapper {
  position: relative;
  width: 100%;
}

.progress-bar {
  position: relative;
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: visible;
}

.progress-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #1989fa 0%, #4facfe 100%);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-marker {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
  background: #1989fa;
  border: 2px solid #fff;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(25, 137, 250, 0.3);
  transition: left 0.3s ease;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.progress-target {
  color: #969799;
}

.progress-remaining {
  color: #1989fa;
  font-weight: 500;
}
</style>
