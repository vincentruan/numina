<template>
  <div class="ledger-page">
    <div class="balance-card">
      <p class="balance-label">我的星星币</p>
      <p class="balance-value"><CoinDisplay :amount="balance" :icon-size="28" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" /></p>
      <button v-if="hasSiblings" class="gift-btn" @click="showGiftSheet = true">🎁 送给兄弟姐妹</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="transactions.length === 0" class="empty">
      <p>还没有记录，快去完成家务吧！</p>
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
      <p class="sheet-title">🎁 送星星币</p>
      <div class="sibling-list">
        <div
          v-for="s in siblings"
          :key="s.id"
          class="sibling-item"
          :class="{ selected: selectedSiblingId === s.id }"
          @click="selectedSiblingId = s.id"
        >
          <span class="sibling-avatar" :style="{ background: s.avatar_color || '#f5a623' }">
            {{ s.display_name[0] }}
          </span>
          <span class="sibling-name">{{ s.display_name }}</span>
        </div>
      </div>
      <van-field
        v-model="giftAmountStr"
        type="digit"
        label="数量"
        placeholder="输入星星币数量"
        style="margin-top: 16px; border-radius: 8px; background: #f9f9f9"
      />
      <van-button
        block
        type="primary"
        :disabled="!selectedSiblingId || !giftAmountStr"
        style="margin-top: 16px; border-radius: 12px; background: #f5a623; border: none"
        @click="doGift"
      >确认赠送</van-button>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { getCoinBalance, getCoinLedger, getSiblings, giftCoins, type CoinTransaction, type Sibling } from '@/api/coins'
import CoinDisplay from '@/components/coins/CoinDisplay.vue'
import { useFamilyStore } from '@/stores/family'

const familyStore = useFamilyStore()
const balance = ref(0)
const transactions = ref<CoinTransaction[]>([])
const loading = ref(true)
const siblings = ref<Sibling[]>([])
const showGiftSheet = ref(false)
const selectedSiblingId = ref('')
const giftAmountStr = ref('')

const hasSiblings = computed(() => siblings.value.length > 0)

async function load() {
  loading.value = true
  try {
    const [bal, txs, sibs] = await Promise.all([getCoinBalance(), getCoinLedger(), getSiblings()])
    balance.value = bal
    transactions.value = txs
    siblings.value = sibs
  } finally {
    loading.value = false
  }
}

async function doGift() {
  const amount = parseInt(giftAmountStr.value)
  if (!selectedSiblingId.value || !amount || amount <= 0) return
  try {
    const res = await giftCoins(selectedSiblingId.value, amount, '🎁')
    showToast(`已送出 ${res.sent_amount} 颗星给 ${res.to_display_name}！`)
    showGiftSheet.value = false
    selectedSiblingId.value = ''
    giftAmountStr.value = ''
    await load()
  } catch {
    showToast('❌ 赠送失败，请检查余额')
  }
}

onMounted(load)
</script>

<style scoped>
.ledger-page {
  padding: 16px;
  background: #FFF9E6;
  min-height: 100vh;
}
.balance-card {
  background: linear-gradient(135deg, #f5a623, #f7c948);
  border-radius: 16px;
  padding: 24px;
  text-align: center;
  margin-bottom: 20px;
  color: #fff;
}
.balance-label { font-size: 14px; margin: 0; opacity: 0.9; }
.balance-value { font-size: 36px; font-weight: bold; margin: 8px 0 0; }
.gift-btn {
  margin-top: 12px;
  background: rgba(255,255,255,0.25);
  border: 1.5px solid rgba(255,255,255,0.6);
  color: #fff;
  border-radius: 20px;
  padding: 6px 18px;
  font-size: 14px;
  cursor: pointer;
}
.loading, .empty {
  text-align: center;
  margin-top: 40px;
  color: #999;
  font-size: 15px;
}
.tx-list { display: flex; flex-direction: column; gap: 10px; }
.tx-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
  gap: 12px;
}
.tx-emoji { font-size: 24px; }
.tx-info { flex: 1; }
.tx-narrative { font-size: 14px; color: #333; margin: 0; }
.tx-time { font-size: 12px; color: #999; margin: 2px 0 0; }
.tx-amount { font-size: 18px; font-weight: bold; }
.tx-amount.positive { color: #f5a623; }
.tx-amount.negative { color: #e74c3c; }

.sheet-title { font-size: 18px; font-weight: bold; text-align: center; margin: 0 0 16px; }
.sibling-list { display: flex; gap: 12px; flex-wrap: wrap; }
.sibling-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px;
  border-radius: 12px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s;
}
.sibling-item.selected { border-color: #f5a623; background: #fff9e6; }
.sibling-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  color: #fff;
}
.sibling-name { font-size: 13px; color: #333; }
</style>

