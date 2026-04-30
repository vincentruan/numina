<template>
  <div class="status-tabs-wrapper">
    <div class="status-tabs">
      <div
        v-for="status in statusList"
        :key="status.key ?? 'all'"
        class="status-tab"
        :class="{ active: activeStatus === status.key }"
        @click="onSelect(status.key)"
      >
        <span class="tab-label">{{ status.label }}</span>
        <span class="tab-count">{{ getCount(status.key) }}</span>
      </div>
    </div>
    <div class="toolbar-slot"><slot name="toolbar"></slot></div>
  </div>
</template>

<script setup lang="ts">
import type { StatesSummaryResponse } from '@/types'

const props = defineProps<{
  summary: StatesSummaryResponse | null
  activeStatus: string | null
}>()

const emit = defineEmits<{
  select: [status: string | null]
}>()

const statusList: { key: string | null; label: string }[] = [
  { key: null, label: '全部' },
  { key: 'in_use', label: '服役中' },
  { key: 'idle', label: '闲置' },
  { key: 'sold', label: '已出售' },
  { key: 'retired', label: '已退役' }
]

function getCount(status: string | null): number {
  if (status === null) {
    return props.summary?.total_count || 0
  }
  return props.summary?.states[status]?.count || 0
}

function onSelect(status: string | null) {
  if (props.activeStatus === status) {
    if (status !== null) {
      emit('select', null)
    }
    return
  }
  emit('select', status)
}
</script>

<style scoped>
.status-tabs-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--card-bg);
  padding: 12px 16px;
  gap: 12px;
  border-bottom: 1px solid var(--color-hairline);
}
.status-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  flex: 1;
  -webkit-overflow-scrolling: touch;
}
.status-tabs::-webkit-scrollbar {
  display: none;
}
.status-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: var(--radius-pill);
  background: var(--bg-secondary);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.18s, color 0.18s, border-color 0.18s;
  white-space: nowrap;
  flex-shrink: 0;
  min-height: 36px;
}
.status-tab:active {
  transform: scale(0.96);
}
.status-tab.active {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border-color: var(--color-primary);
}
[data-theme='dark'] .status-tab.active {
  background: var(--color-coral);
  border-color: var(--color-coral);
}
.tab-label {
  font-size: 14px;
  font-weight: 500;
}
.tab-count {
  font-size: 13px;
  font-weight: 600;
  opacity: 0.8;
}
.status-tab.active .tab-count {
  opacity: 1;
}
.toolbar-slot {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
}
</style>
