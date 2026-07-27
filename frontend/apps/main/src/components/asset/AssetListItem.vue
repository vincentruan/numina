<template>
  <div
    class="asset-list-item"
    :class="{ 'selection-mode': selectable, selected: selected }"
    role="listitem"
    :aria-label="`${asset.name}, ${statusText}, ${formatCurrency(asset.purchase_price || 0, asset.currency)}购入`"
    :aria-selected="selected"
    tabindex="0"
    @click="$emit('click')"
    @touchstart="startLongPress"
    @touchend="cancelLongPress"
    @touchmove="cancelLongPress"
    @contextmenu.prevent="triggerLongPress"
    @keydown.enter="$emit('click')"
    @keydown.space.prevent="toggleSelect"
  >
    <div class="item-main">
      <div
        class="item-icon"
        :class="{ 'has-image': asset.image_url && !imageError }"
        :style="
          asset.image_url && !imageError
            ? undefined
            : { background: asset.category?.color || 'var(--color-primary)' }
        "
      >
        <template v-if="asset.image_url && !imageError">
          <img
            :src="imageUrl"
            :alt="asset.name"
            class="icon-img"
            @error="onImageError"
          />
          <span class="icon-label">{{ asset.name }}</span>
        </template>
        <SvgIcon v-else :name="getIconId(asset.category?.icon)" class="icon-svg" />
      </div>
      <div class="item-info">
        <div class="item-header">
          <span class="item-name">{{ asset.name }}</span>
          <van-tag :type="statusType" size="medium" class="item-status-tag">{{
            statusText
          }}</van-tag>
        </div>
        <div class="item-meta">
          <span class="item-price-days"
            >{{ formatCurrency(asset.purchase_price || 0, asset.currency) }} | {{ daysUsed }}天</span
          >
        </div>
        <div class="item-cost">
          <span v-if="asset.daily_cost != null && asset.daily_cost > 0" class="item-daily">
            {{ formatCurrency(asset.daily_cost, asset.currency) }}/天
          </span>
        </div>

        <!-- Progress bar section -->
        <div v-if="targetDays > 0" class="item-progress-section">
          <div class="progress-bar-wrapper">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>
              <div
                class="progress-marker"
                :style="{
                  left: `${progressPercent}%`,
                  background: asset.category?.color || 'var(--color-primary)',
                }"
              >
                <SvgIcon :name="getIconId(asset.category?.icon)" class="progress-marker-svg" />
              </div>
            </div>
          </div>
          <div class="progress-info">
            <span class="progress-target">{{ targetLabel }}</span>
            <span class="progress-remaining">{{ remainingLabel }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Asset } from '@/types'
import { useCurrency } from '@/composables/useCurrency'
import { formatCurrency, parseLocalDate } from '@/utils/format'
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

const currency = useCurrency()
const { t } = useI18n()

const imageError = ref(false)

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

onUnmounted(() => {
  cancelLongPress()
})

const statusType = computed(() => {
  switch (props.asset.status) {
    case 'in_use':
      return 'primary'
    case 'idle':
      return 'warning'
    case 'sold':
      return 'danger'
    case 'retired':
      return 'default'
    default:
      return 'primary'
  }
})

const statusText = computed(() => {
  switch (props.asset.status) {
    case 'in_use':
      return t('asset.inUse')
    case 'idle':
      return t('asset.idle')
    case 'sold':
      return t('asset.sold')
    case 'retired':
      return t('asset.retired')
    default:
      return props.asset.status
  }
})

const daysUsed = computed(() => {
  if (!props.asset.purchase_date) return 0
  const purchase = parseLocalDate(props.asset.purchase_date)
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

const YEAR_THRESHOLD_DAYS = 5475

const targetLabel = computed(() =>
  targetDays.value >= YEAR_THRESHOLD_DAYS
    ? t('asset.progressTargetYears', { years: Math.round(targetDays.value / 365) })
    : t('asset.progressTarget', { days: targetDays.value }),
)

const remainingLabel = computed(() =>
  targetDays.value >= YEAR_THRESHOLD_DAYS
    ? t('asset.progressRemainingYears', { years: Math.round(remainingDays.value / 365) })
    : t('asset.progressRemaining', { days: remainingDays.value }),
)

</script>

<style scoped>
.asset-list-item {
  display: flex;
  background: var(--card-bg);
  padding: 12px 14px;
  border-bottom: 1px solid var(--separator);
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}
.asset-list-item:active {
  background: var(--bg-tertiary);
}
.asset-list-item:last-child {
  border-bottom: none;
}

/* Selection mode styles */
.asset-list-item.selection-mode.selected {
  box-shadow: inset 0 0 0 2px var(--van-primary-color);
}

/* Accessibility - Focus styles */
.asset-list-item:focus-visible {
  outline: 2px solid var(--color-focus-blue);
  outline-offset: -2px;
}

.item-main {
  display: flex;
  width: 100%;
  gap: 10px;
}

.item-icon {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}
.item-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(255, 255, 255, 0.55) 50%,
    transparent 70%
  );
  transform: translateX(-150%);
  animation: icon-shimmer 2.8s ease-in-out infinite;
  pointer-events: none;
}
.icon-svg {
  position: relative;
  z-index: 1;
  width: 20px;
  height: 20px;
  fill: white;
  color: white;
}
.icon-img {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.icon-label {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  font-size: 8px;
  font-weight: 500;
  line-height: 1.1;
  color: #fff;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: rgba(0, 0, 0, 0.28);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
  pointer-events: none;
}
.item-icon.has-image::before {
  display: none;
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
  .item-icon::before {
    animation: none;
    display: none;
  }
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
  color: var(--text-primary);
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
  color: var(--text-secondary);
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
  background: var(--separator);
  border-radius: 3px;
  overflow: visible;
}

.progress-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: var(--van-primary-color);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-marker {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 14px;
  height: 14px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(23, 23, 28, 0.25);
  transition: left 0.3s ease;
}
[data-theme='dark'] .progress-marker {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
}

.progress-marker-svg {
  width: 8px;
  height: 8px;
  fill: white;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.progress-target {
  color: var(--text-tertiary);
}

.progress-remaining {
  color: var(--color-primary);
  font-weight: 500;
}
[data-theme='dark'] .progress-remaining {
  color: var(--color-coral);
}
</style>
