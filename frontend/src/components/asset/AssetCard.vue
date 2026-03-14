<template>
  <van-cell class="asset-card" clickable @click="$emit('click')">
    <template #icon>
      <div class="card-icon" :style="{ background: asset.category?.color || '#1989fa' }">
        {{ asset.category?.icon || '📦' }}
      </div>
    </template>
    <template #title>
      <div class="card-title">
        <span class="name">{{ asset.name }}</span>
        <van-tag :type="statusType" size="medium">{{ statusText }}</van-tag>
      </div>
    </template>
    <template #label>
      <div class="card-label">
        <span>{{ asset.category?.name || '未分类' }}</span>
        <span v-if="asset.daily_cost" class="daily-cost">日耗 ¥{{ asset.daily_cost.toFixed(2) }}</span>
      </div>
    </template>
    <template #value>
      <MoneyDisplay :amount="asset.current_value" size="normal" />
    </template>
  </van-cell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Asset } from '@/types'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'

const props = defineProps<{
  asset: Asset
}>()

defineEmits<{
  click: []
}>()

const statusMap: Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }> = {
  in_use: { text: '使用中', type: 'success' },
  idle: { text: '闲置', type: 'warning' },
  sold: { text: '已出售', type: 'default' },
  retired: { text: '已报废', type: 'danger' }
}

const statusText = computed(() => statusMap[props.asset.status]?.text || props.asset.status)
const statusType = computed(() => statusMap[props.asset.status]?.type || 'default')
</script>

<style scoped>
.asset-card {
  margin-bottom: 8px;
  border-radius: 8px;
}
.card-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-right: 10px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.name {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}
.card-label {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #969799;
  margin-top: 2px;
}
.daily-cost {
  color: #ff976a;
}
</style>
