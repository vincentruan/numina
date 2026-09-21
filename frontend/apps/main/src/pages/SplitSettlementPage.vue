<template>
  <div class="split-settlement-page">
    <PageHeader :title="t('travel.settlement.title')" />

    <van-loading v-if="loading" class="page-loading" />

    <template v-else>
      <van-empty v-if="settlements.length === 0" :description="t('travel.settlement.noSettlements')" />

      <van-cell-group v-else inset class="settlement-list">
        <div
          v-for="settlement in settlements"
          :key="settlement.id"
          class="settlement-card"
        >
          <div class="settlement-header">
            <div class="settlement-parties">
              <span class="from-name">{{ settlement.from_participant_name }}</span>
              <van-icon name="arrow" />
              <span class="to-name">{{ settlement.to_participant_name }}</span>
            </div>
            <van-tag :type="settlement.is_complete ? 'success' : 'warning'" size="medium">
              {{ settlement.is_complete ? t('travel.settlement.completed') : t('travel.settlement.pending') }}
            </van-tag>
          </div>

          <div class="settlement-amount">
            <span class="amount-value">{{ formatAmount(settlement.amount, settlement.currency) }}</span>
            <span class="amount-currency">{{ settlement.currency }}</span>
          </div>

          <div class="settlement-actions">
            <van-button size="small" plain type="primary" @click="copyTransferInfo(settlement)">
              {{ t('travel.settlement.copyTransfer') }}
            </van-button>

            <van-button
              v-if="!settlement.is_complete"
              size="small"
              type="success"
              @click="handleMarkComplete(settlement)"
            >
              {{ t('travel.settlement.markComplete') }}
            </van-button>

            <van-button
              v-else-if="canReverse(settlement)"
              size="small"
              plain
              type="danger"
              @click="handleReverse(settlement)"
            >
              {{ t('travel.settlement.reverse') }}
            </van-button>
          </div>
        </div>
      </van-cell-group>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useTravelStore } from '@/stores/travel'
import { markSettlementComplete, reverseSettlement } from '@/api/travel'
import PageHeader from '@/components/common/PageHeader.vue'
import type { SplitSettlement } from '@/types/travel'
import { useCurrency } from '@/composables/useCurrency'

const { t, locale } = useI18n()
const route = useRoute()
const store = useTravelStore()
const { formatIn } = useCurrency()

const loading = ref(true)

const tripId = computed(() => route.params.tripId as string)
const settlements = computed(() => store.settlements)

function formatAmount(amount: string, currency = 'CNY'): string {
  return formatIn(amount, currency)
}

async function copyTransferInfo(settlement: SplitSettlement) {
  const amount = formatAmount(settlement.amount, settlement.currency)
  const message = t('travel.settlement.transferTemplate', {
    amount,
    name: settlement.to_participant_name,
  })
  try {
    await navigator.clipboard.writeText(message)
    showSuccessToast(t('travel.splitGroup.copied'))
  } catch {
    showFailToast(t('travel.splitGroup.copyFailed'))
  }
}

async function handleMarkComplete(settlement: SplitSettlement) {
  try {
    await showConfirmDialog({
      title: t('travel.settlement.markComplete'),
      message: t('travel.settlement.markCompleteConfirm'),
    })
    await markSettlementComplete(tripId.value, settlement.id)
    await store.fetchSettlements(tripId.value)
    showSuccessToast(t('common.success'))
  } catch {
    // user cancelled or error
  }
}

async function handleReverse(settlement: SplitSettlement) {
  try {
    await showConfirmDialog({
      title: t('travel.settlement.reverse'),
      message: t('travel.settlement.reverseConfirm'),
    })
    await reverseSettlement(tripId.value, settlement.id)
    await store.fetchSettlements(tripId.value)
    showSuccessToast(t('common.success'))
  } catch {
    // user cancelled or error
  }
}

function canReverse(settlement: SplitSettlement): boolean {
  if (!settlement.settled_at) return false
  const settledAt = new Date(settlement.settled_at)
  const now = new Date()
  const hoursDiff = (now.getTime() - settledAt.getTime()) / (1000 * 60 * 60)
  return hoursDiff <= 24
}

onMounted(async () => {
  try {
    await store.fetchSettlements(tripId.value)
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.split-settlement-page {
  min-height: 100vh;
  background: var(--bg-secondary);
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.page-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.settlement-list {
  margin: 12px;
}
.settlement-card {
  padding: 16px;
  border-bottom: 1px solid var(--border-color, #ebedf0);
}
.settlement-card:last-child {
  border-bottom: none;
}
.settlement-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.settlement-parties {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.from-name,
.to-name {
  font-weight: 600;
  color: var(--text-primary);
}
.settlement-amount {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
}
.amount-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}
.amount-currency {
  font-size: 14px;
  color: var(--text-secondary);
}
.settlement-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
