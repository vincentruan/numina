<template>
  <van-popup
    :show="visible"
    position="bottom"
    round
    :style="{ maxHeight: '70vh' }"
    @update:show="(val: boolean) => emit('update:visible', val)"
  >
    <div class="history-dialog">
      <div class="history-header">
        <h3 class="history-title">{{ t('manifesto.versionHistory') }}</h3>
        <button class="history-close" :aria-label="t('common.close')" @click="close">
          <van-icon name="cross" />
        </button>
      </div>

      <van-loading v-if="loading" size="24px" class="history-loading" />
      <van-empty v-else-if="items.length === 0" :description="t('manifesto.noManifesto')" image-size="60" />
      <van-list v-else>
        <div
          v-for="item in items"
          :key="item.id"
          class="history-row"
          :class="{ 'history-row--active': expandedId === item.id }"
          @click="toggleRow(item.id)"
        >
          <div class="history-row__main">
            <span class="history-row__version">v{{ item.version_number }}</span>
            <span class="history-row__badge" :class="`history-row__badge--${item.change_type}`">
              {{ t(`manifesto.changeType.${item.change_type}`) }}
            </span>
            <span class="history-row__title">{{ item.title }}</span>
            <van-icon
              name="arrow"
              class="history-row__arrow"
              :class="{ 'history-row__arrow--open': expandedId === item.id }"
            />
          </div>
          <div class="history-row__meta">
            {{ formatDateTime(item.created_at) }}
          </div>
          <div v-if="expandedId === item.id" class="history-row__detail">
            {{ getDetail(item.id) || t('manifesto.noContent') }}
          </div>
        </div>
      </van-list>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as manifestoApi from '@/api/manifesto'
import type { ManifestoVersionHistoryItem } from '@/types/manifesto'

const { t } = useI18n()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const loading = ref(false)
const items = ref<ManifestoVersionHistoryItem[]>([])
const expandedId = ref<string | null>(null)
const detailCache = new Map<string, string>()

function close() {
  emit('update:visible', false)
}

function toggleRow(id: string) {
  if (expandedId.value === id) {
    expandedId.value = null
    return
  }
  expandedId.value = id
  if (!detailCache.has(id)) {
    loadDetail(id)
  }
}

async function loadDetail(id: string) {
  try {
    const res = await manifestoApi.getCurrentManifesto()
    const version = res.data?.current_version
    if (version && version.id === id) {
      detailCache.set(id, version.body)
    }
  } catch {
    // ignore
  }
}

function getDetail(id: string): string {
  return detailCache.get(id) ?? ''
}

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

watch(() => props.visible, async (val) => {
  if (!val) return
  loading.value = true
  try {
    const res = await manifestoApi.getVersionHistory()
    items.value = res.data ?? []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.history-dialog {
  padding: 0 0 16px;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 8px;
  position: sticky;
  top: 0;
  background: var(--van-popup-background, #fff);
  z-index: 1;
}
.history-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--van-text-color);
}
.history-close {
  background: none;
  border: none;
  padding: 4px 8px;
  font-size: 18px;
  color: var(--van-text-color-2);
  cursor: pointer;
}
.history-loading {
  display: flex;
  justify-content: center;
  padding: 32px;
}
.history-row {
  padding: 10px 16px;
  border-bottom: 1px solid var(--van-border-color);
  cursor: pointer;
}
.history-row:last-of-type {
  border-bottom: none;
}
.history-row:active {
  background: var(--van-background-2);
}
.history-row--active {
  background: var(--van-background-2);
}
.history-row__main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.history-row__version {
  font-size: 13px;
  font-weight: 600;
  color: var(--van-text-color);
  flex-shrink: 0;
}
.history-row__badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  flex-shrink: 0;
}
.history-row__badge--initial {
  background: var(--van-gray-2, #f2f3f5);
  color: var(--van-text-color-2);
}
.history-row__badge--minor {
  background: rgba(25, 137, 250, 0.1);
  color: #1989fa;
}
.history-row__badge--major {
  background: rgba(255, 147, 0, 0.12);
  color: #ff9300;
}
[data-theme='dark'] .history-row__badge--minor {
  background: rgba(25, 137, 250, 0.2);
}
[data-theme='dark'] .history-row__badge--major {
  background: rgba(255, 147, 0, 0.2);
}
.history-row__title {
  flex: 1;
  font-size: 14px;
  color: var(--van-text-color);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-row__arrow {
  color: var(--van-text-color-3);
  flex-shrink: 0;
  transition: transform 0.2s;
}
.history-row__arrow--open {
  transform: rotate(90deg);
}
.history-row__meta {
  font-size: 12px;
  color: var(--van-text-color-3);
  margin-top: 4px;
  padding-left: 32px;
}
.history-row__detail {
  font-size: 13px;
  color: var(--van-text-color-2);
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--van-background-2);
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
