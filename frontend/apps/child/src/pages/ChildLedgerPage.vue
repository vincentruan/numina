<template>
  <div class="ledger-page">
    <!-- Balance hero — teal feature card -->
    <div class="balance-card">
      <p class="balance-label">{{ t('ledger.myStars') }}</p>
      <p class="balance-value">
        <CoinDisplay :amount="balance" :icon-size="28" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" />
      </p>
      <button v-if="hasSiblings" class="gift-btn" @click="showGiftSheet = true">{{ t('ledger.giftBtn') }}</button>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <div v-else-if="transactions.length === 0" class="empty">
      <p>{{ t('ledger.empty') }}</p>
    </div>

    <div v-else class="tx-list">
      <div v-for="tx in transactions" :key="tx.id" class="tx-card">
        <span class="tx-emoji">{{ tx.narrative_emoji || '⭐' }}</span>
        <div class="tx-info">
          <p class="tx-narrative">{{ tx.narrative || tx.transaction_type }}</p>
          <p class="tx-time">{{ tx.relative_time }}</p>
        </div>
        <span class="tx-amount" :class="tx.amount > 0 ? 'positive' : 'negative'">
          {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount }}
        </span>
      </div>
    </div>

    <!-- Gift bottom sheet -->
    <van-popup v-model:show="showGiftSheet" position="bottom" round style="padding: 24px 16px 40px">
      <p class="sheet-title">{{ t('ledger.sheetTitle') }}</p>
      <div class="sibling-list">
        <div
          v-for="s in siblings"
          :key="s.id"
          class="sibling-item"
          :class="{ selected: selectedSiblingId === s.id }"
          @click="selectedSiblingId = s.id"
        >
          <span class="sibling-avatar" :style="{ background: s.avatar_color || '#e8b94a' }">
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
        style="margin-top: 16px; border-radius: var(--radius-md); background: var(--color-surface-soft)"
      />
      <van-button
        block
        type="primary"
        :disabled="!selectedSiblingId || !giftAmountStr"
        style="margin-top: 16px; border-radius: var(--radius-md); background: var(--color-primary); border: none"
        @click="doGift"
      >{{ t('ledger.confirmGift') }}</van-button>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getCoinBalance, getCoinLedger, getSiblings, giftCoins, type CoinTransaction, type Sibling } from '@/api/coins'
import CoinDisplay from '@/components/coins/CoinDisplay.vue'
import { useFamilyStore } from '@/stores/family'

const { t } = useI18n()

const familyStore = useFamilyStore()
const balance = ref(0)
const transactions = ref<CoinTransaction[]>([])
const loading = ref(true)
const error = ref('')
const siblings = ref<Sibling[]>([])
const showGiftSheet = ref(false)
const selectedSiblingId = ref('')
const giftAmountStr = ref('')

const hasSiblings = computed(() => siblings.value.length > 0)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [bal, txs, sibs] = await Promise.all([getCoinBalance(), getCoinLedger(), getSiblings()])
    balance.value = bal
    transactions.value = txs
    siblings.value = sibs
  } catch {
    error.value = t('errors.LOAD_FAILED')
  } finally {
    loading.value = false
  }
}

async function doGift() {
  const amount = parseInt(giftAmountStr.value)
  if (!selectedSiblingId.value || !amount || amount <= 0) return
  try {
    const res = await giftCoins(selectedSiblingId.value, amount, '🎁')
    showToast(t('toast.childGrantedStars', { amount: res.sent_amount, name: res.to_display_name }))
    showGiftSheet.value = false
    selectedSiblingId.value = ''
    giftAmountStr.value = ''
    await load()
  } catch {
    showToast(t('toast.grantBalanceFailed'))
  }
}

onMounted(load)
</script>

<style scoped>
/* ── Canvas ── */
.ledger-page {
  padding: 16px;
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Balance card — teal feature card ── */
.balance-card {
  background: var(--color-brand-teal);
  border-radius: var(--radius-xl);
  padding: 28px 24px;
  text-align: center;
  margin-bottom: 24px;
  color: var(--color-on-dark);
}
.balance-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin: 0;
  opacity: 0.7;
}
.balance-value {
  font-size: 36px;
  font-weight: bold;
  margin: 8px 0 0;
}
.gift-btn {
  margin-top: 16px;
  background: rgba(255, 255, 255, 0.15);
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  color: var(--color-on-dark);
  border-radius: var(--radius-md);
  padding: 8px 20px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 44px;
}

.loading, .empty {
  text-align: center;
  margin-top: 40px;
  color: var(--color-muted-soft);
  font-family: Inter, sans-serif;
  font-size: 15px;
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
  font-weight: 700;
}
.tx-amount.positive { color: var(--color-brand-ochre); }
.tx-amount.negative { color: var(--color-brand-coral); }

/* ── Gift sheet ── */
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
  font-weight: 700;
  color: var(--color-on-dark);
}
.sibling-name {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body-strong);
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
