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
          <span class="chore-status-badge" :class="c.status">{{ statusLabel(c.status) }}</span>
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
        <van-icon name="arrow" color="var(--color-muted-soft)" size="16" />
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

    <!-- Settings section — collapsible -->
    <div class="settings-section">
      <button class="settings-toggle" @click="settingsExpanded = !settingsExpanded">
        <span>{{ t('home.settings') }}</span>
        <van-icon :name="settingsExpanded ? 'arrow-up' : 'arrow-down'" size="14" />
      </button>
      <div v-if="settingsExpanded" class="settings-body">
        <p class="settings-label">{{ t('home.settingsTheme') }}</p>
        <div class="theme-options">
          <button
            v-for="opt in themeOptions"
            :key="opt.value"
            class="theme-btn"
            :class="{ active: themeMode === opt.value }"
            @click="setMode(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
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
import { useDarkMode } from '@/utils/darkMode'

const { t } = useI18n()
const familyStore = useFamilyStore()
const { themeMode, setMode } = useDarkMode()

const balance = ref(0)
const todayChores = ref<ChoreInstance[]>([])
const loadingChores = ref(true)
const topWish = ref<ChildWish | null>(null)
const settingsExpanded = ref(false)

const themeOptions = [
  { value: 'system' as const, label: t('home.themeSystem') },
  { value: 'light' as const, label: t('home.themeLight') },
  { value: 'dark' as const, label: t('home.themeDark') },
]

function statusLabel(status: ChoreInstance['status']): string {
  switch (status) {
    case 'available': return t('chore.complete')
    case 'pending_approval': return t('chore.pendingApproval')
    case 'approved': return t('chore.approved')
    case 'rejected': return t('chore.rejected')
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
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Hero card — ochre feature card ── */
.hero-card {
  background: var(--color-brand-ochre);
  border-radius: var(--radius-xl);
  padding: 32px 20px;
  text-align: center;
  color: var(--color-ink);
  margin-bottom: var(--space-lg);
}
[data-theme="dark"] .hero-card { color: var(--color-on-feature-ochre); }
.hero-label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
  opacity: 0.75;
}
.hero-balance {
  font-size: 32px;
  font-weight: 600;
}

/* ── Sections ── */
.section { margin-bottom: var(--space-lg); }
.section-title {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
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
  min-height: 56px;
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

/* Status badge — pill with color per state */
.chore-status-badge {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-surface-card);
  color: var(--color-muted);
}
.chore-status-badge.available {
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-weight: 600;
}
.chore-status-badge.approved {
  background: var(--color-brand-mint);
  color: var(--color-ink);
}
.chore-status-badge.rejected {
  background: var(--color-brand-coral);
  color: var(--color-on-dark);
}

/* ── Wish preview — cream card ── */
.wish-preview {
  display: block;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  margin-bottom: var(--space-lg);
  text-decoration: none;
  border: 1px solid var(--color-hairline);
  transition: transform 0.15s;
}
.wish-preview:active { transform: scale(0.98); }
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
  font-weight: 600;
}

/* ── Settings section ── */
.settings-section {
  margin-top: 8px;
  margin-bottom: var(--space-lg);
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-hairline);
  overflow: hidden;
}
.settings-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  min-height: 44px;
}
.settings-body {
  padding: 0 16px 16px;
  border-top: 1px solid var(--color-hairline);
}
.settings-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-muted);
  margin: 12px 0 10px;
}
.theme-options {
  display: flex;
  gap: 8px;
}
.theme-btn {
  flex: 1;
  padding: 10px 4px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-hairline);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-muted);
  cursor: pointer;
  transition: all 0.15s;
  min-height: 44px;
}
.theme-btn.active {
  background: var(--color-brand-ochre);
  border-color: var(--color-brand-ochre);
  color: var(--color-ink);
  font-weight: 600;
}
.theme-btn:active { transform: scale(0.96); }
</style>
