<template>
  <div
    class="asset-card"
    :class="{ 'selection-mode': selectable, 'selected': selected, 'syncing': syncing }"
    :aria-disabled="syncing ? 'true' : undefined"
    role="listitem"
    :aria-label="`${asset.name}, ${statusText}, 当前价值 ${formatPrice(asset.current_value)}${syncing ? ' (同步中)' : ''}`"
    tabindex="0"
    @click="handleClick"
    @touchstart="startLongPress"
    @touchend="cancelLongPress"
    @touchmove="cancelLongPress"
    @contextmenu.prevent="triggerLongPress"
    @keydown.enter="handleClick"
    @keydown.space.prevent="toggleSelect"
  >
    <!-- Syncing indicator badge -->
    <div v-if="syncing" class="syncing-badge" aria-hidden="true">
      <van-tag type="warning">同步中</van-tag>
    </div>
    <div v-if="selectable" class="selection-overlay" aria-hidden="true">
      <van-checkbox
        :model-value="selected"
        @update:model-value="$emit('update:selected', $event)"
      />
    </div>
    <input
      v-if="selectable"
      type="checkbox"
      class="sr-only"
      :checked="selected"
      :aria-label="`选择 ${asset.name}`"
      tabindex="-1"
      @change="$emit('update:selected', ($event.target as HTMLInputElement).checked)"
    />
    <div class="card-left">
      <div v-if="asset.image_url && !imageError" class="card-image">
        <img :src="imageUrl" :alt="asset.name" @error="onImageError" />
      </div>
      <div v-else class="card-icon" :style="{ background: asset.category?.color || 'var(--color-primary)' }">
        <svg class="icon-svg" aria-hidden="true">
          <use :href="`#${getIconId(asset.category?.icon)}`" />
        </svg>
      </div>
    </div>
    <div class="card-right">
      <div class="card-row-top">
        <span class="card-name">{{ asset.name }}</span>
        <van-tag :type="statusType" size="medium">{{ statusText }}</van-tag>
      </div>
      <div class="card-row-category">
        <span class="card-category-text">{{ asset.category?.name || '未分类' }}</span>
        <span v-if="daysUsed > 0" class="card-days">已使用 {{ daysUsed }} 天</span>
      </div>
      <div class="card-row-prices">
        <div class="price-item">
          <span class="price-label">购入</span>
          <span class="price-value">{{ formatPrice(asset.purchase_price) }}</span>
        </div>
        <div class="price-item">
          <span class="price-label">当前</span>
          <span class="price-value current">{{ formatPrice(asset.current_value) }}</span>
        </div>
      </div>
      <div class="card-row-bottom">
          <span v-if="asset.daily_cost != null && asset.daily_cost > 0" class="card-daily-cost">
            <van-icon name="clock-o" size="12" aria-hidden="true" />
            日均 {{ currency.format(asset.daily_cost) }}
          </span>
        <span v-else class="card-daily-cost-placeholder" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import type { Asset } from '@/types'
import { useCurrency } from '@/composables/useCurrency'
import { useAssetStore } from '@/stores/asset'
import { getIconId } from '@/utils/icon'

const props = defineProps<{
  asset: Asset
  selectable?: boolean
  selected?: boolean
}>()

const emit = defineEmits<{
  click: []
  'update:selected': [value: boolean]
  longpress: []
}>()

const assetStore = useAssetStore()
const currency = useCurrency()
const imageError = ref(false)

// Check if this asset is currently syncing
const syncing = computed(() => assetStore.isSyncing(props.asset.id))

// Long press detection
let longPressTimer: ReturnType<typeof setTimeout> | null = null
const LONG_PRESS_DURATION = 500 // 500ms

function startLongPress() {
  longPressTimer = setTimeout(() => {
    emit('longpress')
  }, LONG_PRESS_DURATION)
}

function cancelLongPress() {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

function triggerLongPress() {
  emit('longpress')
}

function toggleSelect() {
  if (props.selectable) {
    emit('update:selected', !props.selected)
  }
}

// Handle click - prevent action if syncing
function handleClick() {
  if (!syncing.value) {
    emit('click')
  }
}

onUnmounted(() => {
  cancelLongPress()
})

const imageUrl = computed(() => {
  if (!props.asset.image_url) return ''
  if (props.asset.image_url.startsWith('/')) {
    return `/api/v1${props.asset.image_url}`
  }
  return props.asset.image_url
})

function onImageError() {
  imageError.value = true
}

const daysUsed = computed(() => {
  if (!props.asset.purchase_date) return 0
  const purchase = new Date(props.asset.purchase_date)
  const now = new Date()
  const diff = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
})

function formatPrice(price: number | null | undefined): string {
  if (price == null) return '-'
  return currency.format(price)
}

const statusMap: Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }> = {
  in_use: { text: '服役中', type: 'success' },
  idle: { text: '闲置', type: 'warning' },
  sold: { text: '已出售', type: 'default' },
  retired: { text: '已退役', type: 'danger' }
}

const statusText = computed(() => statusMap[props.asset.status]?.text || props.asset.status)
const statusType = computed(() => statusMap[props.asset.status]?.type || 'default')
</script>

<style scoped>
.asset-card {
  position: relative;
  display: flex;
  background: var(--card-bg);
  border-radius: var(--radius-sm);
  padding: 14px 12px;
  margin-bottom: 8px;
  border: 1px solid var(--color-card-border);
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;
}
[data-theme='dark'] .asset-card {
  border-color: var(--color-hairline);
}
.asset-card:active {
  transform: scale(0.985);
  border-color: var(--color-hairline);
}
/* Selection mode styles */
.asset-card.selection-mode {
  border: 2px solid transparent;
}
.asset-card.selection-mode.selected {
  border-color: var(--color-primary);
  background: rgba(23, 23, 28, 0.04);
}
[data-theme='dark'] .asset-card.selection-mode.selected {
  border-color: var(--color-lavender);
  background: rgba(189, 187, 255, 0.08);
}
/* Accessibility - Focus styles */
.asset-card:focus-visible {
  outline: 2px solid var(--color-focus-blue);
  outline-offset: 2px;
}
/* Syncing state styles */
.asset-card.syncing {
  opacity: 0.7;
  pointer-events: none;
}
.syncing-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
}
.selection-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  background: var(--card-bg);
  border-radius: 50%;
  padding: 2px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
.selection-overlay :deep(.van-checkbox) {
  display: flex;
}
.card-left {
  flex-shrink: 0;
  margin-right: 12px;
}
.card-image {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  overflow: hidden;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card-icon {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.icon-svg {
  width: 36px;
  height: 36px;
  fill: white;
  color: white;
}
.card-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
  gap: 3px;
}
.card-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
.card-row-category {
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-category-text {
  font-size: 12px;
  color: var(--text-tertiary);
}
.card-days {
  font-size: 11px;
  color: var(--color-body-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  line-height: 1.4;
}
[data-theme='dark'] .card-days {
  color: var(--color-muted);
  background: rgba(255, 255, 255, 0.06);
}
.card-row-prices {
  display: flex;
  gap: 14px;
}
.price-item {
  display: flex;
  align-items: baseline;
  gap: 3px;
}
.price-label {
  font-size: 11px;
  color: var(--text-tertiary);
}
.price-value {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}
.price-value.current {
  color: var(--text-primary);
  font-weight: 600;
}
.card-row-bottom {
  display: flex;
  align-items: center;
}
.card-daily-cost {
  font-size: 12px;
  color: #ff976a;
  font-weight: 500;
}
</style>
