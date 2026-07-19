<template>
  <div class="ledger-page">
    <!-- Skeleton during initial load -->
    <ChildLedgerSkeleton v-if="loading && !refreshing && transactions.length === 0" />

    <!-- Actual content -->
    <template v-else>
    <van-pull-refresh
      v-model="refreshing"
      :pulling-text="t('common.pullRefresh.pulling')"
      :loosing-text="t('common.pullRefresh.loosing')"
      :loading-text="t('common.pullRefresh.loading')"
      :success-text="t('common.pullRefresh.success')"
      @refresh="onRefresh"
    >
    <!-- Balance hero — shared component -->
    <BalanceHero :amount="balance" variant="ledger" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" />
    <button v-if="hasSiblings" class="gift-btn" @click="showGiftSheet = true">{{ t('ledger.giftBtn') }}</button>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <EmptyState
      v-else-if="transactions.length === 0"
      :illustration="noRecordsSvg"
      :text="t('empty.noRecords')"
      :action-text="t('nav.tasks')"
      action-to="/tasks"
    />

    <div v-else class="tx-list">
      <div v-for="tx in transactions" :key="tx.id" class="tx-card">
        <span class="tx-emoji">{{ tx.narrative_emoji || '⭐' }}</span>
        <div class="tx-info">
          <p class="tx-narrative">{{ tx.narrative || t(`ledger.txType.${tx.transaction_type}`) }}</p>
          <p class="tx-time">{{ tx.relative_time }}</p>
        </div>
        <span class="tx-amount" :class="tx.amount > 0 ? 'positive' : 'negative'">
          {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount }}
        </span>
      </div>
    </div>
    </van-pull-refresh>

    <!-- Gift bottom sheet -->
    <van-popup v-model:show="showGiftSheet" position="bottom" round>
      <div class="sheet-inner">
        <p class="sheet-title">{{ t('ledger.sheetTitle') }}</p>
        <div class="sibling-list">
          <div
            v-for="s in siblings"
            :key="s.id"
            class="sibling-item"
            :class="{ selected: selectedSiblingId === s.id }"
            @click="selectedSiblingId = s.id"
          >
            <span class="sibling-avatar" :style="{ background: s.avatar_color || 'var(--color-brand-ochre)' }">
              {{ s.display_name[0] }}
            </span>
            <span class="sibling-name">{{ s.display_name }}</span>
          </div>
        </div>
        <van-field
          v-model="giftAmountStr"
          type="digit"
          :label="t('ledger.amountLabel')"
          :placeholder="t('ledger.amountPlaceholder')"
          class="sheet-field"
          :class="{ 'field-error': giftExceedsBalance }"
        />
        <p v-if="giftAmountStr" class="gift-preview" :class="{ 'is-error': giftExceedsBalance }">
          <template v-if="giftExceedsBalance">
            {{ t('ledger.giftInsufficient', { max: balance }) }}
          </template>
          <template v-else>
            {{ t('ledger.giftRemaining', { remaining: giftRemaining }) }}
          </template>
        </p>
        <van-button
          block
          type="primary"
          :disabled="!giftCanSubmit"
          class="btn-confirm"
          @click="doGift"
        >{{ giftCanSubmit ? t('ledger.confirmGiftWithRemaining', { remaining: giftRemaining }) : t('ledger.confirmGift') }}</van-button>
      </div>
    </van-popup>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildLedger' })
import { ref, computed, onMounted } from 'vue'
import { usePageLoading } from '@/composables/usePageLoading'
import ChildLedgerSkeleton from '@/components/skeletons/ChildLedgerSkeleton.vue'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getCoinLedger, getSiblings, giftCoins, type CoinTransaction, type Sibling } from '@/api/coins'
import BalanceHero from '@/components/BalanceHero.vue'
import EmptyState from '@/components/EmptyState.vue'
import noRecordsSvgRaw from '@/assets/empty-states/no-records.svg?raw'

const noRecordsSvg = noRecordsSvgRaw
import { useFamilyStore } from '@/stores/family'
import { useBalancePolling } from '@/composables/useBalancePolling'

const { t } = useI18n()

const familyStore = useFamilyStore()
const { complete } = usePageLoading()
// Balance polling via composable
const { balance, refresh: refreshBalance } = useBalancePolling()
const transactions = ref<CoinTransaction[]>([])
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const siblings = ref<Sibling[]>([])
const showGiftSheet = ref(false)
const selectedSiblingId = ref('')
const giftAmountStr = ref('')

const hasSiblings = computed(() => siblings.value.length > 0)

// Gift preview: show "after this transfer you'll have N ⭐" so the
// consequence is visible before the irreversible submit, and block amounts
// that exceed the current balance.
const giftAmount = computed(() => parseInt(giftAmountStr.value) || 0)
const giftExceedsBalance = computed(() => giftAmount.value > balance.value)
const giftRemaining = computed(() => Math.max(0, balance.value - giftAmount.value))
const giftCanSubmit = computed(() =>
  !!selectedSiblingId.value &&
  giftAmount.value > 0 &&
  !giftExceedsBalance.value,
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [txs, sibs] = await Promise.all([getCoinLedger(), getSiblings()])
    transactions.value = txs
    siblings.value = sibs
  } catch {
    error.value = t('errors.LOAD_FAILED')
  } finally {
    loading.value = false
    // Complete page loading - skeleton takes over visual feedback
    complete()
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

async function doGift() {
  if (!giftCanSubmit.value) return
  const amount = giftAmount.value
  try {
    const res = await giftCoins(selectedSiblingId.value, amount, '🎁')
    showToast(t('toast.childGrantedStars', { amount: res.sent_amount, name: res.to_display_name }))
    showGiftSheet.value = false
    selectedSiblingId.value = ''
    giftAmountStr.value = ''
    await refreshBalance()
    await load()
  } catch {
    showFailToast(t('toast.grantBalanceFailed'))
  }
}

onMounted(load)
</script>

<style scoped>
/* ── Canvas ── */
.ledger-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* Gift button — secondary action below the hero */
.gift-btn {
  margin-top: -8px;
  margin-bottom: var(--space-lg);
  margin-left: auto;
  display: block;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  color: var(--color-ink);
  border-radius: var(--radius-md);
  padding: 0 20px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 40px;
  transition: opacity 0.15s;
}
.gift-btn:active { opacity: 0.8; }

.loading {
  text-align: center;
  margin-top: 40px;
  color: var(--color-muted-soft);
  font-family: Inter, sans-serif;
  font-size: 15px;
}

/* Empty state */
.empty {
  text-align: center;
  margin-top: 60px;
}
.empty-emoji { font-size: 48px; margin: 0 0 12px; }
.empty-text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-muted-soft);
  margin: 0;
}

/* ── Transaction list ── */
.tx-list { display: flex; flex-direction: column; gap: 8px; }
.tx-card {
  display: flex;
  align-items: center;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  gap: 12px;
  border: 1px solid var(--color-hairline);
  min-height: 56px;
}
.tx-emoji { font-size: 24px; }
.tx-info { flex: 1; }
.tx-narrative {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body-strong);
  margin: 0;
}
.tx-time {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  margin: 2px 0 0;
}
.tx-amount {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
}
.tx-amount.positive { color: var(--color-brand-ochre); }
.tx-amount.negative { color: var(--color-brand-coral); }

/* ── Gift sheet ── */
.sheet-inner {
  padding: 24px 16px 40px;
}
.sheet-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  text-align: center;
  margin: 0 0 16px;
}
.sibling-list { display: flex; gap: 12px; flex-wrap: wrap; }
.sibling-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px;
  border-radius: var(--radius-lg);
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s;
  min-height: 44px;
}
.sibling-item.selected {
  border-color: var(--color-ink);
  background: var(--color-surface-soft);
}
.sibling-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 500;
  color: var(--color-on-dark);
}
.sibling-name {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body-strong);
}
.sheet-field {
  margin-top: 16px;
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}
.sheet-field.field-error :deep(.van-field__control) {
  color: var(--color-brand-coral);
}
.gift-preview {
  margin: 8px 4px 0;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-brand-mint);
  line-height: 1.4;
}
.gift-preview.is-error {
  color: var(--color-brand-coral);
}
.btn-confirm {
  margin-top: 16px;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  border: none;
  height: 44px;
}

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-primary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin: 0 0 16px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  text-align: center;
}
</style>
