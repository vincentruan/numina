<template>
  <div class="shared-expense-page">
    <PageHeader :title="t('travel.shared.title')" />

    <van-loading v-if="loading" class="page-loading" />

    <template v-else>
      <!-- Join form (not joined yet) -->
      <div v-if="!hasJoined" class="join-form">
        <van-cell-group inset>
          <van-field
            v-model="name"
            :label="t('travel.shared.enterName')"
            :placeholder="t('travel.shared.enterName')"
            clearable
          />
        </van-cell-group>
        <div class="join-actions">
          <van-button type="primary" block round :loading="joining" @click="handleJoin">
            {{ t('travel.shared.joinGroup') }}
          </van-button>
        </div>
      </div>

      <!-- Shared expense view (joined) -->
      <template v-else>
        <!-- R5: Cancellation notice -->
        <van-notice-bar
          v-if="sharedData?.trip_status === 'cancelled' || sharedData?.trip_status === 'archived'"
          left-icon="warning-o"
          :text="t('travel.cancelledNotice')"
          color="#ee0a24"
          background="#fff0f0"
        />

        <!-- Trip info header -->
        <van-cell-group inset class="trip-info">
          <van-cell :title="t('travel.shared.tripName')" :value="sharedData?.trip_name" />
          <van-cell :title="t('travel.shared.destination')" :value="sharedData?.destination" />
          <van-cell
            :title="t('travel.shared.dates')"
            :value="formatDateRange(sharedData?.departure_date, sharedData?.return_date)"
          />
        </van-cell-group>

        <!-- Invite code display -->
        <van-cell-group inset class="invite-code-section">
          <div class="invite-code-display">
            <div class="code-label">{{ t('travel.shared.inviteCode') }}</div>
            <div class="code-value">{{ inviteCode }}</div>
            <van-button size="small" type="primary" plain @click="copyInviteCode">
              {{ t('travel.splitGroup.copyCode') }}
            </van-button>
          </div>
        </van-cell-group>

        <!-- Participants -->
        <van-cell-group inset class="participants-section">
          <van-cell :title="t('travel.shared.participants')">
            <template #label>
              <div class="participant-list">
                <div
                  v-for="participant in sharedData?.participants"
                  :key="participant.id"
                  class="participant-item"
                >
                  <span class="participant-name">{{ participant.name }}</span>
                </div>
              </div>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Expenses list -->
        <van-cell-group inset class="expenses-section">
          <van-cell :title="t('travel.shared.expenses')" />
          <van-empty
            v-if="!sharedData?.expenses?.length"
            :description="t('travel.shared.noExpenses')"
          />
          <div v-else class="expense-list">
            <div
              v-for="expense in sharedData.expenses"
              :key="expense.id"
              class="expense-item"
            >
              <div class="expense-header">
                <span class="expense-amount">{{ formatAmount(expense.amount, expense.currency) }}</span>
                <span class="expense-currency">{{ expense.currency }}</span>
              </div>
              <div class="expense-details">
                <span class="expense-payer">{{ expense.payer_name }}</span>
                <span v-if="expense.category_name" class="expense-category">
                  {{ expense.category_name }}
                </span>
                <span class="expense-date">{{ formatDate(expense.expense_date) }}</span>
              </div>
            </div>
          </div>
        </van-cell-group>

        <!-- Read-only notice -->
        <div class="readonly-notice">
          <van-icon name="info-o" />
          <span>{{ t('travel.shared.readOnly') }}</span>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { joinSplitGroup, getSharedExpenses } from '@/api/travel'
import PageHeader from '@/components/common/PageHeader.vue'
import type { SharedExpense } from '@/types/travel'
import { useCurrency } from '@/composables/useCurrency'

const { t, locale } = useI18n()
const route = useRoute()
const { formatIn } = useCurrency()

const inviteCode = computed(() => route.params.code as string)
const loading = ref(true)
const joining = ref(false)
const name = ref('')
const sharedData = ref<SharedExpense | null>(null)

const hasJoined = computed(() => {
  const stored = localStorage.getItem(`travel_shared_${inviteCode.value}`)
  return !!stored
})

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })
}

function formatDateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return ''
  if (!end) return formatDate(start)
  return `${formatDate(start)} - ${formatDate(end)}`
}

function formatAmount(amount: string, currency = 'CNY'): string {
  return formatIn(amount, currency)
}

async function copyInviteCode() {
  try {
    await navigator.clipboard.writeText(inviteCode.value)
    showSuccessToast(t('travel.splitGroup.copied'))
  } catch {
    showFailToast(t('travel.splitGroup.copyFailed'))
  }
}

async function handleJoin() {
  if (!name.value.trim()) {
    showFailToast(t('travel.shared.nameRequired'))
    return
  }

  joining.value = true
  try {
    await joinSplitGroup(inviteCode.value, name.value.trim())
    localStorage.setItem(
      `travel_shared_${inviteCode.value}`,
      JSON.stringify({ name: name.value.trim(), joined_at: new Date().toISOString() })
    )
    showSuccessToast(t('travel.shared.joinSuccess'))
    await loadSharedData()
  } catch {
    showFailToast(t('travel.shared.joinFailed'))
  } finally {
    joining.value = false
  }
}

async function loadSharedData() {
  try {
    const res = await getSharedExpenses(inviteCode.value)
    sharedData.value = res.data
  } catch {
    showFailToast(t('common.failed'))
  }
}

onMounted(async () => {
  if (hasJoined.value) {
    await loadSharedData()
  }
  loading.value = false
})
</script>

<style scoped>
.shared-expense-page {
  min-height: 100vh;
  background: var(--bg-secondary);
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.page-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.join-form {
  padding: 20px 0;
}
.join-actions {
  padding: 20px 12px;
}
.trip-info,
.invite-code-section,
.participants-section,
.expenses-section {
  margin: 12px;
}
.invite-code-display {
  padding: 16px 0;
  text-align: center;
}
.code-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.code-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 2px;
  margin-bottom: 12px;
  font-family: monospace;
}
.participant-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}
.participant-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #ebedf0);
}
.participant-item:last-child {
  border-bottom: none;
}
.participant-name {
  font-size: 14px;
  color: var(--text-primary);
}
.expense-list {
  padding: 0 16px;
}
.expense-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color, #ebedf0);
}
.expense-item:last-child {
  border-bottom: none;
}
.expense-header {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 8px;
}
.expense-amount {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}
.expense-currency {
  font-size: 12px;
  color: var(--text-secondary);
}
.expense-details {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
.readonly-notice {
  margin: 20px 12px;
  padding: 12px;
  background: var(--card-bg);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  justify-content: center;
}
</style>
