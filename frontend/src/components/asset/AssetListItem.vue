<template>
  <div class="asset-list-item" @click="$emit('click')">
    <div class="item-icon" :style="{ background: asset.category?.color || '#1989fa' }">
      {{ asset.category?.icon || '📦' }}
    </div>
    <div class="item-info">
      <span class="item-name">{{ asset.name }}</span>
      <div class="item-meta">
        <span class="item-category">{{ asset.category?.name || '未分类' }}</span>
        <van-tag :type="statusType" size="medium" class="item-status-tag">{{ statusText }}</van-tag>
      </div>
    </div>
    <div class="item-right">
      <span class="item-value">¥{{ formatPrice(asset.current_value) }}</span>
      <span v-if="asset.daily_cost != null && asset.daily_cost > 0" class="item-daily">
        ¥{{ asset.daily_cost.toFixed(2) }}/天
      </span>
      <span v-if="daysUsed > 0" class="item-days">{{ daysUsed }}天</span>
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
  align-items: center;
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
.item-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  margin-right: 10px;
}
.item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.item-name {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 5px;
}
.item-category {
  font-size: 12px;
  color: #969799;
}
.item-status-tag {
  flex-shrink: 0;
}
.item-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
  margin-left: 8px;
}
.item-value {
  font-size: 14px;
  font-weight: 600;
  color: #323233;
}
.item-daily {
  font-size: 11px;
  color: #ff976a;
}
.item-days {
  font-size: 11px;
  color: #969799;
}
</style>
