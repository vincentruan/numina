<template>
  <van-cell-group inset class="chart-section reminders-card">
    <van-collapse v-model="expanded" @change="onToggle">
      <van-collapse-item name="reminders">
        <template #title>
          <div class="reminder-header">
            <span class="reminder-title">
              <span class="bell-icon" :class="{ 'bell-icon--ringing': hasExpiringSoon }">
                <IIcon :icon="hasExpiringSoon ? 'lucide:bell-ring' : 'lucide:bell'" size="18" class="bell-icon__svg" />
                <span v-if="hasExpiringSoon" class="bell-icon__wave bell-icon__wave--1" />
                <span v-if="hasExpiringSoon" class="bell-icon__wave bell-icon__wave--2" />
                <span v-if="hasExpiringSoon" class="bell-icon__wave bell-icon__wave--3" />
              </span>
              <span class="reminder-title__text">{{ t('alertCards.reminder') }}</span>
            </span>
            <span v-if="totalCount > 0" class="reminder-summary">
              <template v-if="expiringAssets.length > 0">{{ t('reminders.expiringSoon') }} {{ expiringAssets.length }}</template>
              <template v-if="upcomingPayments.length > 0"> · {{ t('reminders.upcomingPayments') }} {{ upcomingPayments.length }}</template>
              <template v-if="idleAssets.length > 0"> · {{ t('reminders.idleAssets') }} {{ idleAssets.length }}</template>
              <template v-if="store.summary.maturity > 0"> · {{ t('reminders.types.maturity') }} {{ store.summary.maturity }}</template>
              <template v-if="store.summary.large_purchase > 0"> · {{ t('reminders.types.large_purchase') }} {{ store.summary.large_purchase }}</template>
            </span>
            <span v-else class="reminder-summary reminder-summary--empty">{{ t('reminders.empty') }}</span>
          </div>
        </template>

        <!-- Dynamic section order: 有数据的在前，都有/都无时智能提醒在前 -->
        <template v-for="section in sectionOrder" :key="section">

          <!-- 即将到期 + 即将还款 + 闲置资产 -->
          <template v-if="section === 'expiring'">
            <!-- 资产到期 -->
            <template v-if="expiringAssets.length > 0">
              <div class="reminder-section-label">{{ t('reminders.expiringSoon') }}</div>
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

            <!-- 还款到期 -->
            <template v-if="upcomingPayments.length > 0">
              <div class="reminder-section-label">{{ t('reminders.upcomingPayments') }}</div>
              <div
                v-for="item in upcomingPayments"
                :key="`pay-${item.liability_id}`"
                class="expiring-row payment-row"
                :class="getPaymentUrgencyClass(item.due_date)"
                @click="goToLiability(item.liability_id)"
              >
                <van-icon name="gold-coin-o" class="expiring-icon" />
                <div class="expiring-content">
                  <div class="expiring-name">{{ item.name }}</div>
                  <div class="expiring-meta">{{ item.due_date }} · {{ t('liability.title') }}</div>
                </div>
                <div class="expiring-right">
                  <div class="payment-amount">{{ currency.format(item.amount ?? 0) }}</div>
                  <div class="expiring-remaining" :class="getPaymentUrgencyClass(item.due_date)">
                    {{ formatPaymentDays(item.due_date) }}
                  </div>
                </div>
              </div>
            </template>

            <!-- 无任何到期时的空状态 -->
            <van-empty
              v-if="expiringAssets.length === 0 && upcomingPayments.length === 0"
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
import IIcon from '@/components/IIcon.vue'
import { useRemindersStore } from '@/stores/reminders'
import type { LowUsageItem } from '@/types'
import type { ExpiringSoonItem, UpcomingPaymentItem } from '@/api/dashboard'
import { useCurrency } from '@/composables/useCurrency'

const props = defineProps<{
  idleAssets?: LowUsageItem[]
  expiringAssets?: ExpiringSoonItem[]
  upcomingPayments?: UpcomingPaymentItem[]
}>()

defineEmits<{
  'select-status': [status: string]
}>()

const { t } = useI18n()
const router = useRouter()
const currency = useCurrency()
const store = useRemindersStore()
const expanded = ref<string[]>([])
const loaded = ref(false)

const idleAssets = computed(() => props.idleAssets ?? [])
const expiringAssets = computed(() => props.expiringAssets ?? [])
const upcomingPayments = computed(() => props.upcomingPayments ?? [])

// 排序规则：有数据的在前；都有/都无时，智能提醒在前
// 注意：闲置资产固定跟在即将到期后面，不参与排序决策
const hasExpiringSoon = computed(() => expiringAssets.value.length > 0 || upcomingPayments.value.length > 0)
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
  () => expiringAssets.value.length + idleAssets.value.length + upcomingPayments.value.length + store.summary.total
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

async function onDismiss(id: string) {
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

function goToLiability(id: string) {
  router.push(`/liabilities/${id}`)
}

function daysUntilDue(dueDateStr: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(dueDateStr)
  due.setHours(0, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86_400_000)
}

function formatPaymentDays(dueDateStr: string): string {
  const days = daysUntilDue(dueDateStr)
  if (days < 0) return t('reminders.expiredDays', { days: Math.abs(days) })
  if (days === 0) return t('reminders.dueToday')
  return t('reminders.dueInDays', { days })
}

function getPaymentUrgencyClass(dueDateStr: string): string {
  const days = daysUntilDue(dueDateStr)
  if (days <= 3) return 'urgent'
  if (days <= 7) return 'warning'
  return 'normal'
}
</script>

<style scoped>
.reminders-card :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}
.reminders-card :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  align-items: center;
}
.reminder-header {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 8px;
}
.reminder-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.bell-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
}
.bell-icon__svg {
  position: relative;
  z-index: 1;
  transform-origin: top center;
}
.bell-icon--ringing .bell-icon__svg {
  animation: bell-ring 8s ease-in-out infinite;
}
.bell-icon__wave {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 1.4em;
  height: 1.4em;
  margin: -0.7em 0 0 -0.7em;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  opacity: 0;
  pointer-events: none;
  animation: bell-wave 2.4s ease-out infinite;
}
.bell-icon--ringing .bell-icon__wave--1 {
  animation-delay: 0s;
}
.bell-icon--ringing .bell-icon__wave--2 {
  animation-delay: 0.8s;
}
.bell-icon--ringing .bell-icon__wave--3 {
  animation-delay: 1.6s;
}
@keyframes bell-ring {
  0%, 2% { transform: rotate(0); }
  4% { transform: rotate(14deg); }
  6% { transform: rotate(-12deg); }
  8% { transform: rotate(10deg); }
  10% { transform: rotate(-8deg); }
  12% { transform: rotate(6deg); }
  14%, 100% { transform: rotate(0); }
}
@keyframes bell-wave {
  0% {
    transform: scale(0.7);
    opacity: 0.55;
  }
  70% {
    opacity: 0;
  }
  100% {
    transform: scale(2.4);
    opacity: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .bell-icon--ringing .bell-icon__svg,
  .bell-icon__wave {
    animation: none;
  }
}

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

.expiring-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.payment-amount {
  font-size: 13px;
  font-weight: 600;
  color: var(--van-text-color);
}

[data-theme='dark'] .expiring-remaining.warning {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

[data-theme='dark'] .expiring-remaining.urgent {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}
</style>
