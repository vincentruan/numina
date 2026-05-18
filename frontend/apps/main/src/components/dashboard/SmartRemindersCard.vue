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

        <!-- Dynamic section order: 有数据的在前，都有/都无时智能提醒在前 -->
        <template v-for="section in sectionOrder" :key="section">

          <!-- 即将到期 + 闲置资产 -->
          <template v-if="section === 'expiring'">
            <div class="reminder-section-label">{{ t('reminders.expiringSoon') }}</div>
            <template v-if="expiringAssets.length > 0">
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
                  <div class="expiring-meta">{{ item.category_name }} · {{ item.asset_type === 'financial' ? t('asset.financial') : t('asset.physical') }}</div>
                </div>
                <div class="expiring-remaining" :class="getRemainingClass(item)">
                  {{ formatRemaining(item.remaining_days) }}
                </div>
              </div>
            </template>
            <van-empty
              v-else
              :description="t('reminders.expiringSoonEmpty')"
              image-size="60"
              class="section-empty"
            />

            <template v-if="idleAssets.length > 0">
              <div class="reminder-section-label">{{ t('reminders.idleAssets') }}</div>
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
          </template>

          <!-- 智能提醒 -->
          <template v-if="section === 'smart'">
            <div class="reminder-section-label">{{ t('reminders.title') }}</div>
            <van-loading v-if="store.loading" size="24px" class="reminder-loading" />
            <template v-else-if="store.reminders.length > 0">
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
            <van-empty
              v-else-if="loaded"
              :description="t('reminders.smartRemindersEmpty')"
              image-size="60"
              class="section-empty"
            />
          </template>

        </template>
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

// 排序规则：有数据的在前；都有/都无时，智能提醒在前
// 注意：闲置资产固定跟在即将到期后面，不参与排序决策
const hasExpiringSoon = computed(() => expiringAssets.value.length > 0)
const hasSmartReminders = computed(() => store.reminders.length > 0)

const sectionOrder = computed(() => {
  if (hasExpiringSoon.value === hasSmartReminders.value) {
    // 都有数据或都无数据：智能提醒在前
    return ['smart', 'expiring']
  }
  // 一方有数据：有数据的在前
  return hasExpiringSoon.value ? ['expiring', 'smart'] : ['smart', 'expiring']
})

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

.section-empty {
  padding: 12px 0;
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
