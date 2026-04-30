<template>
  <van-cell-group inset class="chart-section">
    <van-collapse v-model="expanded" @change="onToggle">
      <van-collapse-item name="reminders">
        <template #title>
          <span>🔔 提醒</span>
          <span v-if="totalCount > 0" class="reminder-summary">
            <template v-if="expiringAssets.length > 0">到期 {{ expiringAssets.length }}</template>
            <template v-if="idleAssets.length > 0"> · 闲置 {{ idleAssets.length }}</template>
            <template v-if="store.summary.maturity > 0"> · 理财 {{ store.summary.maturity }}</template>
            <template v-if="store.summary.allocation_drift > 0"> · 失衡 {{ store.summary.allocation_drift }}</template>
            <template v-if="store.summary.large_purchase > 0"> · 冷静期 {{ store.summary.large_purchase }}</template>
          </span>
          <span v-else class="reminder-summary reminder-summary--empty">暂无提醒</span>
        </template>

        <!-- Expiring Soon items (shown first) -->
        <template v-if="expiringAssets.length > 0">
          <div class="reminder-section-label">即将到期</div>
          <div
            v-for="item in expiringAssets"
            :key="`exp-${item.id}`"
            class="expiring-row"
            :class="getRemainingClass(item)"
            @click="goToAsset(item.id)"
          >
            <van-icon name="clock-o" class="expiring-icon" />
            <div class="expiring-content">
              <div class="expiring-name">{{ item.name }}</div>
              <div class="expiring-meta">{{ item.category_name }} · {{ item.asset_type === 'financial' ? '金融' : '实物' }}</div>
            </div>
            <div class="expiring-remaining" :class="getRemainingClass(item)">
              {{ formatRemaining(item.remaining_days) }}
            </div>
          </div>
        </template>

        <!-- Idle Assets -->
        <template v-if="idleAssets.length > 0">
          <div class="reminder-section-label">闲置资产</div>
          <van-cell
            v-for="item in idleAssets"
            :key="`idle-${item.id}`"
            :title="item.name"
            :label="item.category_name"
            icon="box-o"
            is-link
            @click="$emit('select-status', 'idle')"
          />
        </template>

        <!-- AI Smart Reminders -->
        <template v-if="store.summary.total > 0 || loaded">
          <div v-if="expiringAssets.length > 0 || idleAssets.length > 0" class="reminder-section-label">智能提醒</div>
          <van-loading v-if="store.loading" size="24px" class="reminder-loading" />
          <van-empty
            v-else-if="store.reminders.length === 0 && expiringAssets.length === 0 && idleAssets.length === 0"
            :description="t('reminders.empty')"
            image-size="60"
          />
          <template v-else>
            <van-swipe-cell v-for="reminder in store.reminders" :key="reminder.id">
              <van-cell
                :title="reminder.title"
                :label="reminder.body"
                :icon="severityIcon(reminder.severity)"
              />
              <template #right>
                <van-button
                  square
                  type="warning"
                  :text="t('reminders.dismiss')"
                  class="dismiss-btn"
                  @click="onDismiss(reminder.id)"
                />
              </template>
            </van-swipe-cell>
          </template>
        </template>

        <!-- Empty state when no alerts at all -->
        <van-empty
          v-if="!store.loading && totalCount === 0 && loaded"
          :description="t('reminders.empty')"
          image-size="60"
        />
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useRemindersStore } from '@/stores/reminders'
import type { LowUsageItem } from '@/types'
import type { ExpiringSoonItem } from '@/api/dashboard'

const props = defineProps<{
  idleAssets?: LowUsageItem[]
  expiringAssets?: ExpiringSoonItem[]
}>()

defineEmits<{
  'select-status': [status: string]
}>()

const { t } = useI18n()
const router = useRouter()
const store = useRemindersStore()
const expanded = ref<string[]>([])
const loaded = ref(false)

const idleAssets = computed(() => props.idleAssets ?? [])
const expiringAssets = computed(() => props.expiringAssets ?? [])

const totalCount = computed(
  () => expiringAssets.value.length + idleAssets.value.length + store.summary.total
)

onMounted(() => {
  store.fetchSummary()
})

async function onToggle(names: string[]) {
  if (names.includes('reminders') && !loaded.value) {
    loaded.value = true
    await store.fetchReminders()
  }
}

async function onDismiss(id: number) {
  await store.dismiss(id)
}

function severityIcon(severity: string): string {
  if (severity === 'critical') return 'warning-o'
  if (severity === 'warning') return 'info-o'
  return 'bell'
}

function formatRemaining(days: number | null): string {
  if (days === null) return '-'
  if (days < 0) return `已过期 ${Math.abs(days)} 天`
  if (days === 0) return '今天到期'
  if (days < 30) return `${days} 天后到期`
  return `${Math.round(days / 30)} 个月后到期`
}

function getRemainingClass(item: ExpiringSoonItem): string {
  const days = item.remaining_days ?? 0
  if (days < 0) return 'expired'
  if (days < 7) return 'urgent'
  if (days < 30) return 'warning'
  return 'normal'
}

function goToAsset(id: string) {
  router.push(`/assets/${id}`)
}
</script>

<style scoped>
.reminder-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.reminder-summary--empty {
  color: var(--van-text-color-3);
}
.reminder-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}
.dismiss-btn {
  height: 100%;
}

.reminder-section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--van-text-color-3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 8px 16px 4px;
}

.expiring-row {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--van-border-color);
  gap: 10px;
}
.expiring-row:last-of-type {
  border-bottom: none;
}
.expiring-row:active {
  background: var(--van-background-2);
}

.expiring-icon {
  font-size: 18px;
  color: var(--van-text-color-3);
  flex-shrink: 0;
}

.expiring-content {
  flex: 1;
  min-width: 0;
}

.expiring-name {
  font-size: 14px;
  color: var(--van-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.expiring-meta {
  font-size: 12px;
  color: var(--van-text-color-3);
  margin-top: 2px;
}

.expiring-remaining {
  font-size: 12px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}
.expiring-remaining.normal {
  background: var(--van-background-2);
  color: var(--van-text-color-2);
}
.expiring-remaining.warning {
  background: #fff7e6;
  color: #d48806;
}
.expiring-remaining.urgent {
  background: #fff1f0;
  color: #cf1322;
}
.expiring-remaining.expired {
  background: #f5f5f5;
  color: #999;
}
</style>
