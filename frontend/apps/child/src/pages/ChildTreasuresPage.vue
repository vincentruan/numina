<template>
  <div class="treasures-page">
    <!-- Header summary — lavender feature card -->
    <div class="summary-card">
      <p class="summary-title">{{ t('treasures.title') }}</p>
      <p v-if="treasures.length > 0" class="summary-count">{{ treasures.length }}</p>
      <p v-if="treasures.length > 0" class="summary-desc">
        {{ t('treasures.earnedCount', { count: treasures.length }) }}
      </p>
      <p v-if="totalCoins > 0" class="summary-coins">{{ t('treasures.totalCoins', { coins: totalCoins }) }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <EmptyState
      v-else-if="treasures.length === 0"
      :illustration="noTreasuresSvg"
      :text="t('empty.noTreasures')"
      :action-text="t('nav.wishes')"
      action-to="/wishes"
    />

    <div v-else class="grid">
      <div v-for="item in treasures" :key="item.id" class="treasure-card">
        <van-image
          v-if="item.image_url"
          :src="item.image_url"
          width="100%"
          height="100px"
          fit="cover"
          radius="16px 16px 0 0"
        />
        <div v-else class="placeholder-img">🎁</div>
        <div class="card-body">
          <p class="card-name">{{ item.name }}</p>
          <p v-if="item.purchase_date" class="card-date">{{ formatDate(item.purchase_date) }}</p>
          <p v-if="item.coins_spent != null" class="card-coins">⭐ {{ item.coins_spent }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildTreasures' })
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listTreasures, type TreasureItem } from '@/api/treasures'
import EmptyState from '@/components/EmptyState.vue'
import noTreasuresSvgRaw from '@/assets/empty-states/no-treasures.svg?raw'

const noTreasuresSvg = noTreasuresSvgRaw

const { t, locale } = useI18n()
const treasures = ref<TreasureItem[]>([])
const loading = ref(true)
const error = ref<string>('')

const totalCoins = computed(() =>
  treasures.value.reduce((sum, t) => sum + (t.coins_spent ?? 0), 0),
)

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value, { year: 'numeric', month: 'short', day: 'numeric' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    treasures.value = await listTreasures()
  } catch {
    error.value = t('errors.LOAD_FAILED')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* ── Canvas ── */
.treasures-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Summary card — lavender feature card ── */
.summary-card {
  background: var(--color-brand-lavender);
  border-radius: var(--radius-xl);
  padding: 32px 20px;
  text-align: center;
  margin-bottom: var(--space-lg);
  color: var(--color-ink);
}
[data-theme="dark"] .summary-card {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-lavender-rgb), 0.16), rgba(var(--color-brand-lavender-rgb), 0.08)),
    var(--color-surface-card);
  color: var(--color-on-feature-lavender);
}
.summary-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 6px;
}
.summary-count {
  font-family: Inter, sans-serif;
  font-size: 48px;
  font-weight: 600;
  line-height: 1;
  margin: 4px 0 4px;
}
.summary-desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  margin: 0 0 4px;
  opacity: 0.75;
}
.summary-coins {
  font-family: Inter, sans-serif;
  font-size: 14px;
  margin: 0;
  opacity: 0.7;
}

.loading,
.empty {
  text-align: center;
  margin-top: 60px;
  color: var(--color-muted-soft);
}
.empty-emoji { font-size: 56px; margin: 0 0 12px; }
.empty-text  {
  font-family: Inter, sans-serif;
  font-size: 15px;
}

/* ── Grid ── */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.treasure-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--color-hairline);
  transition: transform 0.15s;
}
.treasure-card:active { transform: scale(0.97); }

.placeholder-img {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  background: var(--color-surface-card);
}

.card-body { padding: 10px 12px; }
.card-name {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 4px;
  /* allow 2 lines so names aren't truncated on small screens */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-date {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted-soft);
  margin: 0 0 4px;
}
.card-coins {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  margin: 0;
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
