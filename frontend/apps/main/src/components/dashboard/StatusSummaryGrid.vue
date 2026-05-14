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
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { StatesSummaryResponse } from '@/types'

const { t } = useI18n()

const props = defineProps<{
  summary: StatesSummaryResponse | null
  activeStatus: string | null
}>()

const emit = defineEmits<{
  select: [status: string | null]
}>()

const statusList = computed<{ key: string | null; label: string }[]>(() => [
  { key: null, label: t('statusGrid.all') },
  { key: 'in_use', label: t('statusGrid.inUse') },
  { key: 'idle', label: t('statusGrid.idle') },
  { key: 'sold', label: t('statusGrid.sold') },
  { key: 'retired', label: t('statusGrid.retired') },
])

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
  padding: 8px 12px;
  gap: 8px;
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
  border-radius: 8px;
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
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  border-color: var(--van-primary-color);
}
[data-theme='dark'] .status-tab.active {
  background: rgba(189, 187, 255, 0.25);
  border-color: var(--color-lavender);
  color: #ffffff;
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
