<template>
  <div
    class="asset-mini-card"
    :class="{ 'selection-mode': selectable, selected: selected, syncing: syncing }"
    :aria-disabled="syncing ? 'true' : undefined"
    role="listitem"
    :aria-label="
      t('assetCard.ariaLabel', {
        name: asset.name,
        status: statusText,
        value: formatPrice(asset.current_value),
      }) + (syncing ? t('assetCard.ariaSyncing') : '')
    "
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
      <van-tag type="warning">{{ t('assetCard.syncing') }}</van-tag>
    </div>

    <input
      v-if="selectable"
      type="checkbox"
      class="sr-only"
      :checked="selected"
      :aria-label="t('assetCard.selectAriaLabel', { name: asset.name })"
      tabindex="-1"
      @change="$emit('update:selected', ($event.target as HTMLInputElement).checked)"
    />

    <!-- Top row: icon + status -->
    <div class="card-top">
      <div v-if="asset.image_url && !imageError" class="card-image">
        <img :src="imageUrl" :alt="asset.name" @error="onImageError" />
      </div>
      <div
        v-else
        class="card-icon"
        :style="{ background: asset.category?.color || 'var(--color-primary)' }"
      >
        <SvgIcon :name="getIconId(asset.category?.icon)" class="icon-svg" />
      </div>
      <div class="card-status">
        <span class="status-dot" :class="`status-dot--${statusType}`" />
        <span class="status-text">{{ statusText }}</span>
      </div>
    </div>

    <!-- Name -->
    <div class="card-name">{{ asset.name }}</div>

    <!-- Price + days -->
    <div class="card-meta">
      <span class="meta-price">{{ formatPrice(asset.purchase_price) }}</span>
      <span v-if="daysUsed > 0" class="meta-days">{{
        t('assetCard.daysUsed', { days: daysUsed })
      }}</span>
    </div>

    <!-- Daily cost -->
    <div class="card-daily">
      <span v-if="asset.daily_cost != null && asset.daily_cost > 0" class="daily-value">
        {{ currency.formatConverted(asset.daily_cost, asset.currency) }}
        <span class="daily-unit">/{{ t('assetCard.dayUnit') }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Asset } from '@/types'
import { parseLocalDate } from '@/utils/format'
import { useAssetStore } from '@/stores/asset'
import { getIconId } from '@/utils/icon'
import { useCurrency } from '@/composables/useCurrency'

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
const { t } = useI18n()
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
  return props.asset.image_url
})

function onImageError() {
  imageError.value = true
}

const daysUsed = computed(() => {
  if (!props.asset.purchase_date) return 0
  const purchase = parseLocalDate(props.asset.purchase_date)
  const now = new Date()
  const diff = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
})

function formatPrice(price: number | string | null | undefined): string {
  if (price == null) return '-'
  return currency.formatConverted(price, props.asset.currency)
}

const statusMap = computed<
  Record<string, { text: string; type: 'success' | 'warning' | 'danger' | 'default' }>
>(() => ({
  in_use: { text: t('asset.inUse'), type: 'success' },
  idle: { text: t('asset.idle'), type: 'warning' },
  sold: { text: t('asset.sold'), type: 'danger' },
  retired: { text: t('asset.retired'), type: 'default' },
}))

const statusText = computed(() => statusMap.value[props.asset.status]?.text || props.asset.status)
const statusType = computed(() => statusMap.value[props.asset.status]?.type || 'default')
</script>

<style scoped>
.asset-mini-card {
  position: relative;
  background: var(--card-bg);
  border-radius: 16px;
  padding: 14px;
  border: 1px solid var(--color-card-border);
  cursor: pointer;
  transition:
    transform 0.15s,
    border-color 0.15s,
    box-shadow 0.15s;
}
[data-theme='dark'] .asset-mini-card {
  border-color: var(--color-hairline);
}
.asset-mini-card:active {
  transform: scale(0.97);
  border-color: var(--color-hairline);
}

/* Selection mode styles */
.asset-mini-card.selection-mode.selected {
  outline: 2px solid var(--van-primary-color);
  outline-offset: -1px;
}

/* Accessibility - Focus styles */
.asset-mini-card:focus-visible {
  outline: 2px solid var(--color-focus-blue);
  outline-offset: 2px;
}

/* Syncing state styles */
.asset-mini-card.syncing {
  opacity: 0.7;
  pointer-events: none;
}
.syncing-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 10;
}

/* Top row: icon + status */
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.card-image {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
}
.card-image::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 2;
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(255, 255, 255, 0.5) 50%,
    transparent 70%
  );
  transform: translateX(-150%);
  animation: icon-shimmer 3.2s ease-in-out infinite;
  pointer-events: none;
}
.card-image img {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-icon {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}
.card-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(255, 255, 255, 0.5) 50%,
    transparent 70%
  );
  transform: translateX(-150%);
  animation: icon-shimmer 3.2s ease-in-out infinite;
  pointer-events: none;
}
.icon-svg {
  position: relative;
  z-index: 1;
  width: 28px;
  height: 28px;
  fill: white;
  color: white;
}

@keyframes icon-shimmer {
  0% {
    transform: translateX(-150%);
  }
  60%,
  100% {
    transform: translateX(150%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .card-icon::before,
  .card-image::before {
    animation: none;
    display: none;
  }
}

/* Status badge */
.card-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-secondary);
  padding: 4px 10px;
  border-radius: 12px;
  flex-shrink: 0;
}
[data-theme='dark'] .card-status {
  background: rgba(255, 255, 255, 0.06);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot--success {
  background: #52c41a;
}
.status-dot--warning {
  background: #faad14;
}
.status-dot--danger {
  background: #f5222d;
}
.status-dot--default {
  background: var(--text-tertiary);
}

.status-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

/* Name */
.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Price + days */
.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.meta-price {
  font-size: 12px;
  color: var(--text-tertiary);
}
.meta-days {
  font-size: 11px;
  color: var(--color-body-muted);
}
[data-theme='dark'] .meta-days {
  color: var(--color-muted);
}

/* Daily cost */
.card-daily {
  min-height: 24px;
  display: flex;
  align-items: flex-end;
}
.daily-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.daily-unit {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-tertiary);
}
</style>
