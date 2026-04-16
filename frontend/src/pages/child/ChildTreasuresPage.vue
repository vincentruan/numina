<template>
  <div class="ledger-page">
    <div class="balance-card">
      <p class="balance-label">我的星星币</p>
      <p class="balance-value">⭐ {{ balance }}</p>
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getCoinBalance, getCoinLedger, type CoinTransaction } from '@/api/coins'

const balance = ref(0)
const transactions = ref<CoinTransaction[]>([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const [bal, txs] = await Promise.all([getCoinBalance(), getCoinLedger()])
    balance.value = bal
    transactions.value = txs
  } finally {
    loading.value = false
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
</style>

