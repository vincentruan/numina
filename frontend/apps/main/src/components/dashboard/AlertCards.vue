<template>
  <div class="alert-cards-container">
    <!-- Collapse Toggle Button -->
    <div v-if="hasAlerts" class="alert-toggle" @click="toggleCollapsed">
      <span class="toggle-label">{{ t('alertCards.reminder') }}</span>
      <span class="toggle-count">{{ totalAlertCount }}</span>
      <van-icon :name="isCollapsed ? 'arrow-down' : 'arrow-up'" class="toggle-icon" />
    </div>

    <!-- Alert Cards (Collapsible) -->
    <div class="alert-cards" :class="{ collapsed: isCollapsed }">
      <!-- Idle Assets Card — emphasized color (amber/orange) -->
      <div
        v-if="idleCount > 0"
        class="alert-card idle-card"
        @click="$emit('select-status', 'idle')"
      >
        <div class="card-icon">
          <svg class="icon-svg" aria-hidden="true">
            <use href="#icon-idle" />
          </svg>
        </div>
        <div class="card-content">
          <div class="card-title">{{ t('alertCards.idleAssets') }}</div>
          <div class="card-value">{{ t('alertCards.idleHint', { count: idleCount }) }}</div>
        </div>
        <van-icon name="arrow" class="card-arrow" />
      </div>

      <!-- Expiring Soon Card — muted color for physical assets, subtle alert for financial -->
      <div
        v-if="expiringAssets.length > 0"
        class="alert-card expiring-card"
        :class="{ 'has-financial': hasFinancialExpiring }"
        @click="showExpiringSheet = true"
      >
        <div class="card-icon">
          <svg class="icon-svg" aria-hidden="true">
            <use :href="hasFinancialExpiring ? '#icon-warning' : '#icon-expiring'" />
          </svg>
        </div>
        <div class="card-content">
          <div class="card-title">{{ t('alertCards.expiringSoon') }}</div>
          <div class="card-value">
            {{ t('alertCards.expiringHint', { count: expiringAssets.length }) }}
            <span v-if="expiredCount > 0" class="expired-hint">{{ t('alertCards.expiredHint', { count: expiredCount }) }}</span>
          </div>
        </div>
        <van-icon name="arrow" class="card-arrow" />
      </div>
    </div>

    <!-- Expiring Soon Sheet -->
    <van-popup v-model:show="showExpiringSheet" position="bottom" round :style="{ maxHeight: '70%' }">
      <div class="sheet-header">
        <span class="sheet-title">{{ t('alertCards.sheetTitle') }}</span>
        <van-icon name="cross" @click="showExpiringSheet = false" />
      </div>
      
      <div class="sheet-content">
        <div
          v-for="item in expiringAssets"
          :key="item.id"
          class="expiring-item"
          :class="{
            'is-financial': item.asset_type === 'financial',
            'is-expired': (item.remaining_days ?? 0) < 0
          }"
          @click="goToAsset(item.id)"
        >
          <div class="item-icon">
            <svg class="icon-svg-small" aria-hidden="true">
              <use :href="`#${getIconId(item.icon)}`" />
            </svg>
          </div>
          <div class="item-content">
            <div class="item-name">{{ item.name }}</div>
            <div class="item-meta">
              <span class="item-category">{{ item.category_name }}</span>
              <span class="item-type">{{ item.asset_type === 'financial' ? t('asset.financial') : t('asset.physical') }}</span>
            </div>
          </div>
          <div class="item-remaining" :class="getRemainingClass(item)">
            {{ formatRemaining(item.remaining_days) }}
          </div>
        </div>
      </div>
      
      <div class="sheet-hint">
        <p v-if="hasFinancialExpiring" class="hint-financial">
          {{ t('reminders.financialExpiryHint') }}
        </p>
        <p v-else class="hint-physical">
          {{ t('reminders.physicalExpiryHint') }}
        </p>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { LowUsageItem } from '@/types'
import type { ExpiringSoonItem } from '@/api/dashboard'

const { t } = useI18n()

const props = defineProps<{
  idleAssets: LowUsageItem[]
  expiringAssets: ExpiringSoonItem[]
}>()

defineEmits<{
  'select-status': [status: string]
}>()

const router = useRouter()
const showExpiringSheet = ref(false)
const isCollapsed = ref(true) // Default collapsed

// Load collapse state from localStorage
onMounted(() => {
  const saved = localStorage.getItem('alert-cards-collapsed')
  if (saved !== null) {
    isCollapsed.value = saved === 'true'
  }
})

const idleCount = computed(() => props.idleAssets.length)

const hasFinancialExpiring = computed(() =>
  props.expiringAssets.some(a => a.asset_type === 'financial')
)

const expiredCount = computed(() =>
  props.expiringAssets.filter(a => (a.remaining_days ?? 0) < 0).length
)

const hasAlerts = computed(() => idleCount.value > 0 || props.expiringAssets.length > 0)

const totalAlertCount = computed(() => idleCount.value + props.expiringAssets.length)

function toggleCollapsed() {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('alert-cards-collapsed', String(isCollapsed.value))
}

function formatRemaining(days: number | null): string {
  if (days === null) return '-'
  if (days < 0) return t('reminders.expiredDays', { days: Math.abs(days) })
  if (days === 0) return t('reminders.dueToday')
  if (days < 30) return t('reminders.dueInDays', { days })
  return t('reminders.dueInMonths', { months: Math.round(days / 30) })
}

function getRemainingClass(item: ExpiringSoonItem): string {
  const days = item.remaining_days ?? 0
  if (days < 0) return 'expired'
  if (days < 7) return 'urgent'
  if (days < 30) return 'warning'
  return 'normal'
}

function goToAsset(id: string) {
  showExpiringSheet.value = false
  router.push(`/assets/${id}`)
}

/**
 * Get the icon ID for an asset category icon.
 * If the icon is already an icon ID (starts with 'icon-'), use it directly.
 * Otherwise, fall back to 'icon-other' for emojis or unknown icons.
 */
function getIconId(icon: string | undefined): string {
  if (!icon) return 'icon-other'
  if (icon.startsWith('icon-')) {
    return icon
  }
  // Fallback for emoji or unknown icons
  return 'icon-other'
}
</script>

<style scoped>
.alert-cards-container {
  padding: 0 12px;
}

/* Collapse Toggle Button */
.alert-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--card-bg);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.alert-toggle:active {
  background: var(--van-background-2);
}
.toggle-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}
.toggle-count {
  font-size: 12px;
  color: #ee0a24;
  background: rgba(238, 10, 36, 0.1);
  padding: 2px 8px;
  border-radius: 10px;
}
[data-theme='dark'] .toggle-count {
  background: rgba(238, 10, 36, 0.15);
}
.toggle-icon {
  font-size: 14px;
  color: var(--text-tertiary);
}

/* Alert Cards (Collapsible) */
.alert-cards {
  display: flex;
  gap: 12px;
  transition: max-height 0.3s ease, opacity 0.3s ease, padding 0.3s ease;
  max-height: 100px;
  opacity: 1;
  overflow: hidden;
}
.alert-cards.collapsed {
  max-height: 0;
  opacity: 0;
  padding: 0;
  margin-bottom: 0;
}

.alert-card {
  flex: 1;
  display: flex;
  align-items: center;
  padding: 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.alert-card:active {
  transform: scale(0.98);
}

/* Idle card — emphasized amber/orange */
.idle-card {
  background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%);
  border: 1px solid #ffd591;
}

[data-theme='dark'] .idle-card {
  background: linear-gradient(135deg, #4a3a1f 0%, #3d2d14 100%);
  border-color: #6b4f1e;
}

/* Expiring card — muted gray/blue by default */
.expiring-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border: 1px solid #d9d9d9;
}

[data-theme='dark'] .expiring-card {
  background: linear-gradient(135deg, #2a2a2a 0%, #1f1f1f 100%);
  border-color: #3a3a3a;
}

/* Has financial assets — subtle alert blue */
.expiring-card.has-financial {
  background: linear-gradient(135deg, #e6f4ff 0%, #bae0ff 100%);
  border-color: #91caff;
}

[data-theme='dark'] .expiring-card.has-financial {
  background: linear-gradient(135deg, #1a2a3a 0%, #0d1a2a 100%);
  border-color: #1a4a7a;
}

.card-icon {
  margin-right: 10px;
}
.icon-svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.card-content {
  flex: 1;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--van-text-color);
  margin-bottom: 2px;
}

.card-value {
  font-size: 12px;
  color: var(--van-text-color-2);
}

.expired-hint {
  color: #999;
}

.card-arrow {
  color: var(--van-text-color-3);
  font-size: 16px;
}

/* Sheet */
.sheet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color);
}

.sheet-title {
  font-size: 16px;
  font-weight: 600;
}

.sheet-content {
  padding: 8px 16px;
  max-height: 50vh;
  overflow-y: auto;
}

.expiring-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--van-border-color);
  cursor: pointer;
}

.expiring-item:last-child {
  border-bottom: none;
}

.item-icon {
  margin-right: 12px;
}
.icon-svg-small {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.item-content {
  flex: 1;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--van-text-color);
  margin-bottom: 2px;
}

.item-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--van-text-color-3);
}

.item-type {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--van-background-2);
}

.item-remaining {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 6px;
}

.item-remaining.normal {
  background: var(--van-background-2);
  color: var(--van-text-color-2);
}

.item-remaining.warning {
  background: #fff7e6;
  color: #d48806;
}

.item-remaining.urgent {
  background: #fff1f0;
  color: #cf1322;
}

.item-remaining.expired {
  background: #f5f5f5;
  color: #999;
}

/* Financial assets get highlighted */
.expiring-item.is-financial {
  background: rgba(24, 144, 255, 0.05);
  margin: 0 -16px;
  padding: 12px 16px;
}

.expiring-item.is-financial .item-type {
  background: #e6f4ff;
  color: #1890ff;
}

.sheet-hint {
  padding: 12px 16px;
  background: var(--van-background-2);
  border-top: 1px solid var(--van-border-color);
}

.sheet-hint p {
  font-size: 12px;
  color: var(--van-text-color-3);
  margin: 0;
}

.hint-financial {
  color: #1890ff !important;
}
</style>