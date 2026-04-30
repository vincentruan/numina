<template>
  <div class="treasures-page">
    <!-- Header summary -->
    <div class="summary-card">
      <p class="summary-title">{{ t('treasures.title') }}</p>
      <p v-if="treasures.length > 0" class="summary-desc">
        {{ t('treasures.earnedCount', { count: treasures.length }) }}
      </p>
      <p v-if="totalCoins > 0" class="summary-coins">{{ t('treasures.totalCoins', { coins: totalCoins }) }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="treasures.length === 0" class="empty">
      <p class="empty-emoji">🎁</p>
      <p class="empty-text">{{ t('treasures.empty') }}</p>
    </div>

    <div v-else class="grid">
      <div v-for="item in treasures" :key="item.id" class="treasure-card">
        <van-image
          v-if="item.image_url"
          :src="item.image_url"
          width="100%"
          height="100px"
          fit="cover"
          radius="12px 12px 0 0"
        />
        <div v-else class="placeholder-img">🎁</div>
        <div class="card-body">
          <p class="card-name">{{ item.name }}</p>
          <p v-if="item.purchase_date" class="card-date">{{ item.purchase_date }}</p>
          <p v-if="item.coins_spent != null" class="card-coins">⭐ {{ item.coins_spent }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listTreasures, type TreasureItem } from '@/api/treasures'

const { t } = useI18n()
const treasures = ref<TreasureItem[]>([])
const loading = ref(true)

const totalCoins = computed(() =>
  treasures.value.reduce((sum, t) => sum + (t.coins_spent ?? 0), 0),
)

async function load() {
  loading.value = true
  try {
    treasures.value = await listTreasures()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.treasures-page {
  padding: 16px;
  background: #fff9e6;
  min-height: 100vh;
}

.summary-card {
  background: linear-gradient(135deg, #f5a623, #f7c948);
  border-radius: 16px;
  padding: 20px;
  text-align: center;
  margin-bottom: 20px;
  color: #fff;
}
.summary-title {
  font-size: 20px;
  font-weight: bold;
  margin: 0 0 6px;
}
.summary-desc {
  font-size: 14px;
  margin: 0 0 4px;
  opacity: 0.95;
}
.summary-coins {
  font-size: 14px;
  margin: 0;
  opacity: 0.9;
}

.loading,
.empty {
  text-align: center;
  margin-top: 60px;
  color: #999;
}
.empty-emoji {
  font-size: 56px;
  margin: 0 0 12px;
}
.empty-text {
  font-size: 15px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.treasure-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.07);
}

.placeholder-img {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  background: #fef3c7;
}

.card-body {
  padding: 10px 12px;
}
.card-name {
  font-size: 14px;
  font-weight: bold;
  color: #333;
  margin: 0 0 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-date {
  font-size: 11px;
  color: #aaa;
  margin: 0 0 4px;
}
.card-coins {
  font-size: 13px;
  font-weight: bold;
  color: #f5a623;
  margin: 0;
}
</style>
