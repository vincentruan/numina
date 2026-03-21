<template>
  <van-grid :column-num="4" :border="false" class="status-grid">
    <van-grid-item
      v-for="status in statusList"
      :key="status.key"
      :class="{ active: activeStatus === status.key }"
      @click="onSelect(status.key)"
    >
      <div class="status-count">{{ getCount(status.key) }}</div>
      <div class="status-label">{{ status.label }}</div>
      <div class="status-value">{{ formatValue(status.key) }}</div>
    </van-grid-item>
  </van-grid>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StatesSummaryResponse } from '@/types'

const props = defineProps<{
  summary: StatesSummaryResponse | null
  activeStatus: string | null
}>()

const emit = defineEmits<{
  select: [status: string | null]
}>()

const statusList = [
  { key: 'in_use', label: '使用中' },
  { key: 'idle', label: '闲置' },
  { key: 'sold', label: '已出售' },
  { key: 'retired', label: '已报废' }
]

function getCount(status: string): number {
  return props.summary?.states[status]?.count || 0
}

function formatValue(status: string): string {
  const value = props.summary?.states[status]?.total_value || 0
  if (value >= 10000) {
    return `¥${(value / 10000).toFixed(1)}万`
  }
  return `¥${value.toLocaleString()}`
}

function onSelect(status: string) {
  if (props.activeStatus === status) {
    emit('select', null)
  } else {
    emit('select', status)
  }
}
</script>

<style scoped>
.status-grid {
  background: #fff;
  padding: 12px 0;
}
.status-grid :deep(.van-grid-item__content) {
  padding: 8px 4px;
  cursor: pointer;
  transition: background 0.2s;
}
.status-grid :deep(.van-grid-item__content):active {
  background: #f5f5f5;
}
.status-grid .active :deep(.van-grid-item__content) {
  background: #ecf5ff;
  border: 2px solid #1989fa;
  border-radius: 8px;
}
.status-count {
  font-size: 20px;
  font-weight: 600;
  color: #323233;
}
.status-label {
  font-size: 12px;
  color: #969799;
  margin-top: 2px;
}
.status-value {
  font-size: 11px;
  color: #1989fa;
  margin-top: 2px;
}
.active .status-count {
  color: #1989fa;
}
.active .status-label {
  color: #1989fa;
}
</style>