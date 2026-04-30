<template>
  <div class="home-page">
    <!-- Balance hero — ochre feature card -->
    <div class="hero-card">
      <p class="hero-label">{{ t('home.myStars') }}</p>
      <CoinDisplay :amount="balance" :icon-size="32" class="hero-balance" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" />
    </div>

    <!-- Today's chores -->
    <div class="section">
      <p class="section-title">{{ t('home.todayTasks') }}</p>
      <div v-if="loadingChores" class="hint">{{ t('common.loading') }}</div>
      <div v-else-if="todayChores.length === 0" class="hint">{{ t('home.noTasks') }}</div>
      <div v-else class="chore-list">
        <div
          v-for="c in todayChores"
          :key="c.id"
          class="chore-card"
          :class="c.status"
        >
          <span class="chore-emoji">{{ c.chore_emoji || '✅' }}</span>
          <div class="chore-info">
            <p class="chore-name">{{ c.chore_name }}</p>
            <p class="chore-reward">+{{ (c.coin_reward ?? 0) + (c.streak_bonus ?? 0) }} ⭐</p>
          </div>
          <span class="chore-status-badge">{{ statusLabel(c.status) }}</span>
        </div>
      </div>
    </div>

    <!-- Top active wish progress -->
    <router-link v-if="topWish" to="/wishes" class="wish-preview">
      <div class="wish-preview-header">
        <span class="wish-preview-icon">{{ topWish.emoji || '🌟' }}</span>
        <div class="wish-preview-info">
          <p class="wish-preview-name">{{ topWish.name }}</p>
          <p class="wish-preview-sub">{{ t('home.myWishes') }}</p>
        </div>
        <van-icon name="arrow" color="#9a9a9a" size="16" />
      </div>
      <div v-if="topWish.has_cost_set && topWish.progress !== null" class="wish-preview-bar">
        <div class="wish-preview-fill" :style="{ width: Math.min((topWish.progress ?? 0) * 100, 100) + '%' }" />
      </div>
      <p v-if="topWish.has_cost_set && topWish.progress !== null" class="wish-preview-pct">
        {{ Math.min(Math.round((topWish.progress ?? 0) * 100), 100) }}{{ t('home.wishComplete') }}
        <span v-if="(topWish.progress ?? 0) >= 1" class="wish-ready">{{ t('home.wishReady') }}</span>
      </p>
      <p v-else class="wish-preview-pct">{{ t('home.wishWaitingGoal') }}</p>
    </router-link>

    <!-- Calendar -->
    <div class="section">
      <p class="section-title">{{ t('home.myCalendar') }}</p>
      <ChildCalendar :fetch-month="fetchChildMonth" day-route="/calendar/day" variant="child" />
    </div>

    <!-- Quick links — Clay feature-card palette -->
    <div class="quick-links">
      <router-link to="/wishes" class="quick-card quick-card--pink">
        <span class="quick-icon">🌟</span>
        <span class="quick-label">{{ t('home.quickWishes') }}</span>
      </router-link>
      <router-link to="/treasures" class="quick-card quick-card--ochre">
        <span class="quick-icon">🏆</span>
        <span class="quick-label">{{ t('home.quickTreasures') }}</span>
      </router-link>
      <router-link to="/tasks" class="quick-card quick-card--teal">
        <span class="quick-icon">📋</span>
        <span class="quick-label">{{ t('home.quickTasks') }}</span>
      </router-link>
      <router-link to="/ledger" class="quick-card quick-card--lavender">
        <span class="quick-icon">💰</span>
        <span class="quick-label">{{ t('home.quickLedger') }}</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getCoinBalance } from '@/api/coins'
import { getMyChores, type ChoreInstance } from '@/api/chores'
import { getChildCalendar } from '@/api/calendar'
import { listChildWishes, type ChildWish } from '@/api/childWishes'
import CoinDisplay from '@/components/coins/CoinDisplay.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import { useFamilyStore } from '@/stores/family'

const { t } = useI18n()
const familyStore = useFamilyStore()
const balance = ref(0)
const todayChores = ref<ChoreInstance[]>([])
const loadingChores = ref(true)
const topWish = ref<ChildWish | null>(null)

function statusLabel(status: ChoreInstance['status']): string {
  switch (status) {
    case 'available': return t('chore.complete')
    case 'pending_approval': return t('chore.pendingApproval')
    case 'approved': return '✅'
    case 'rejected': return '❌'
    default: return ''
  }
}

function todayDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function fetchChildMonth(year: number, month: number) {
  return getChildCalendar(year, month)
}

onMounted(async () => {
  const [bal, chores, wishData] = await Promise.all([
    getCoinBalance().catch(() => 0),
    getMyChores(todayDate()).catch(() => [] as ChoreInstance[]),
    listChildWishes().catch(() => null),
  ])
  balance.value = bal
  todayChores.value = chores
  loadingChores.value = false
  const active = wishData?.active ?? []
  topWish.value = active.find(w => w.priority === 'high') ?? active[0] ?? null
})
</script>

<style scoped>
/* ── Canvas ── */
.home-page {
  padding: 16px;
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Hero card — ochre feature card ── */
.hero-card {
  background: var(--color-brand-ochre);
  border-radius: var(--radius-xl);
  padding: 28px 20px;
  text-align: center;
  color: var(--color-ink);
  margin-bottom: 24px;
}
.hero-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin: 0 0 8px;
  opacity: 0.7;
}
.hero-balance {
  font-size: 40px;
  font-weight: bold;
}

/* ── Sections ── */
.section { margin-bottom: 24px; }
.section-title {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-muted);
  margin: 0 0 12px;
}
.hint {
  font-size: 14px;
  color: var(--color-muted-soft);
  text-align: center;
  padding: 16px 0;
}

/* ── Chore cards ── */
.chore-list { display: flex; flex-direction: column; gap: 8px; }
.chore-card {
  display: flex;
  align-items: center;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  gap: 12px;
  border: 1px solid var(--color-hairline);
}
.chore-card.approved { opacity: 0.55; }
.chore-emoji { font-size: 24px; }
.chore-info { flex: 1; }
.chore-name {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}
.chore-reward {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-brand-ochre);
  margin: 2px 0 0;
  font-weight: 500;
}
.chore-status-badge {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
  white-space: nowrap;
}

/* ── Wish preview — cream card ── */
.wish-preview {
  display: block;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  margin-bottom: 24px;
  text-decoration: none;
  border: 1px solid var(--color-hairline);
}
.wish-preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.wish-preview-icon { font-size: 32px; flex-shrink: 0; }
.wish-preview-info { flex: 1; min-width: 0; }
.wish-preview-name {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wish-preview-sub {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  margin: 0;
}
.wish-preview-bar {
  height: 8px;
  background: var(--color-surface-strong);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 6px;
}
.wish-preview-fill {
  height: 100%;
  background: var(--color-brand-ochre);
  border-radius: 4px;
  transition: width 0.6s ease;
  max-width: 100%;
}
.wish-preview-pct {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
  margin: 0;
  font-weight: 500;
}
.wish-ready {
  color: var(--color-brand-ochre);
  font-weight: 700;
}

/* ── Quick links — Clay feature-card palette ── */
.quick-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 12px;
  border-radius: var(--radius-xl);
  text-decoration: none;
  transition: transform 0.1s;
}
.quick-card:active { transform: scale(0.96); }
.quick-icon { font-size: 32px; }
.quick-label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
}

/* Pink card — on-dark text */
.quick-card--pink { background: var(--color-brand-pink); color: var(--color-on-dark); }
.quick-card--pink .quick-label { color: var(--color-on-dark); }

/* Ochre card — ink text */
.quick-card--ochre { background: var(--color-brand-ochre); color: var(--color-ink); }
.quick-card--ochre .quick-label { color: var(--color-ink); }

/* Teal card — on-dark text */
.quick-card--teal { background: var(--color-brand-teal); color: var(--color-on-dark); }
.quick-card--teal .quick-label { color: var(--color-on-dark); }

/* Lavender card — ink text */
.quick-card--lavender { background: var(--color-brand-lavender); color: var(--color-ink); }
.quick-card--lavender .quick-label { color: var(--color-ink); }
</style>
