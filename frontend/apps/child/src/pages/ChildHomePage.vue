<template>
  <div class="home-page">
    <!-- Skeleton during initial load -->
    <ChildHomeSkeleton v-if="loadingChores && !refreshing && todayChores.length === 0" />

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
      <!-- Settings entry — top-right gear, out of the main scroll flow -->
      <router-link to="/settings" class="home-settings-link" :aria-label="t('home.settings')">
        <van-icon name="setting-o" size="20" />
      </router-link>
      <!-- Greeting (home-only) -->
      <HackerGreeting
        :name="childAuthStore.childUser?.display_name ?? ''"
        :balance="balance"
        class="hero-greeting"
      />

      <!-- Balance hero — shared component -->
      <BalanceHero :amount="balance" variant="home" coin-tiers-mode="collapsible" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" />

      <!-- Progress ring — own row below the hero -->
      <ProgressRing
        v-if="!loadingChores && todayChores.length > 0"
        :completed="completedChores"
        :pending="pendingChores"
        :total="todayChores.length"
        :total-coins="totalChoreCoins"
        :loading="loadingChores"
        class="home-progress-ring"
      />

    <!-- Today's chores — read-only preview; tap a card to manage on the Tasks page -->
    <div class="section">
      <div class="section-head">
        <p class="section-title">{{ t('home.todayTasks') }}</p>
        <router-link v-if="todayChores.length > 0" to="/tasks" class="section-link">
          {{ t('home.viewAllTasks') }}<van-icon name="arrow" size="12" />
        </router-link>
      </div>
      <div v-if="loadingChores" class="hint">{{ t('common.loading') }}</div>
      <EmptyState
        v-else-if="todayChores.length === 0"
        :illustration="noTasksSvg"
        :text="t('empty.noTasks')"
      />
      <div v-else class="chore-list">
        <router-link
          v-for="c in todayChores"
          :key="c.id"
          to="/tasks"
          class="chore-card"
          :class="c.status"
        >
          <span class="chore-emoji">{{ c.chore_emoji || '✅' }}</span>
          <div class="chore-info">
            <p class="chore-name">{{ c.chore_name }}</p>
            <p class="chore-reward">
              +{{ (c.coin_reward ?? 0) + (c.streak_bonus ?? 0) }} ⭐
              <span
                v-if="c.streak_count > 1"
                class="streak-badge"
                :class="['flame-tier-' + streakTier(c.streak_count), { 'reduced-motion': reducedMotion }]"
              >🔥{{ c.streak_count }}</span>
            </p>
          </div>
          <span class="chore-status-badge" :class="c.status">
            <van-icon v-if="c.status === 'approved'" name="success" size="14" />
            <van-icon v-else-if="c.status === 'rejected'" name="warning-o" size="14" />
            <van-icon v-else-if="c.status === 'pending_approval'" name="clock-o" size="14" />
            <van-icon v-else name="arrow" size="14" />
            <span class="chore-status-text">{{ statusLabel(c.status) }}</span>
          </span>
        </router-link>
      </div>
    </div>

    <!-- Active challenges -->
    <ChallengeCard ref="challengeCard" />

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
    </van-pull-refresh>

    <!-- Celebration animation -->
    <CelebrationAnimation
      :visible="celebrationVisible"
      :task-count="celebrationTaskCount"
      :stars-earned="celebrationStarsEarned"
      @dismiss="onCelebrationDismiss"
    />
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildHome' })
import { ref, computed, onMounted } from 'vue'
import { usePageLoading } from '@/composables/usePageLoading'
import ProgressRing from '@/components/ProgressRing.vue'
import ChildHomeSkeleton from '@/components/skeletons/ChildHomeSkeleton.vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { getMyChores, type ChoreInstance } from '@/api/chores'
import { getChildCalendar } from '@/api/calendar'
import { listChildWishes, type ChildWish } from '@/api/childWishes'
import { getCoinBalance } from '@/api/coins'
import BalanceHero from '@/components/BalanceHero.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import CelebrationAnimation from '@/components/CelebrationAnimation.vue'
import ChallengeCard from '@/components/ChallengeCard.vue'
import HackerGreeting from '@/components/HackerGreeting.vue'
import EmptyState from '@/components/EmptyState.vue'
import noTasksSvgRaw from '@/assets/empty-states/no-tasks.svg?raw'
import { useFamilyStore } from '@/stores/family'

const noTasksSvg = noTasksSvgRaw
import { useCelebration } from '@/composables/useCelebration'
import { useBalancePolling } from '@/composables/useBalancePolling'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { useChildAuthStore } from '@numina/auth'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()
const { increment, decrement } = usePageLoading()
const childAuthStore = useChildAuthStore()

// Balance polling via composable (singleton auto-refreshes; no manual refresh needed)
const { balance } = useBalancePolling()
const reducedMotion = useReducedMotion()
const todayChores = ref<ChoreInstance[]>([])
const loadingChores = ref(true)
const refreshing = ref(false)

// ProgressRing derived data
const completedChores = computed(() => todayChores.value.filter(c => c.status === 'approved').length)
const pendingChores = computed(() => todayChores.value.filter(c => c.status === 'pending_approval').length)
const totalChoreCoins = computed(() => todayChores.value.reduce((sum, c) => sum + (c.coin_reward ?? 0), 0))
const topWish = ref<ChildWish | null>(null)

// Celebration state via composable
const {
  celebrationVisible,
  celebrationTaskCount,
  celebrationStarsEarned,
  onCelebrationDismiss,
  checkAndTriggerCelebration,
} = useCelebration()

// Streak tier helper: returns threshold value (7, 14, 30) or '0' for below 7
function streakTier(count: number): string {
  if (count >= 30) return '30'
  if (count >= 14) return '14'
  if (count >= 7) return '7'
  return '0'
}

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

async function load() {
  loadingChores.value = true
  try {
    const [bal, chores, wishData] = await Promise.all([
      getCoinBalance().catch(() => 0),
      getMyChores(todayDate()).catch(() => [] as ChoreInstance[]),
      listChildWishes().catch(() => null),
    ])
    balance.value = bal
    todayChores.value = chores
    const active = wishData?.active ?? []
    topWish.value = active.find(w => w.priority === 'high') ?? active[0] ?? null
    // Check for pending celebrations after data loads
    checkAndTriggerCelebration(chores)
  } finally {
    loadingChores.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

function fetchChildMonth(year: number, month: number) {
  return getChildCalendar(year, month)
}

onMounted(async () => {
  increment()
  try {
    await load()
  } finally {
    decrement()
  }
})
</script>

<style scoped>
/* ── Canvas ── */
.home-page {
  position: relative;
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Greeting (home-only, sits above the shared balance hero) ── */
.hero-greeting {
  text-align: center;
  margin-bottom: var(--space-md);
}

/* Progress ring — its own row below the hero */
.home-progress-ring {
  margin-bottom: var(--space-lg);
}

/* ── Sections ── */
.section { margin-bottom: var(--space-lg); }
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 12px;
}
.section-title {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted);
  margin: 0;
}
.section-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-brand-ochre);
  text-decoration: none;
}
.hint {
  font-size: 14px;
  color: var(--color-muted-soft);
  text-align: center;
  padding: 16px 0;
}

/* ── Chore preview cards — tap to manage on Tasks page ── */
.chore-list { display: flex; flex-direction: column; gap: 8px; }
.chore-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--color-hairline);
  min-height: 56px;
  text-decoration: none;
  transition: transform 0.1s;
}
.chore-card:active { transform: scale(0.98); }
.chore-card.approved { opacity: 0.55; }
.chore-emoji { font-size: 24px; flex-shrink: 0; }
.chore-info { flex: 1; min-width: 0; }
.chore-name {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chore-reward {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-brand-ochre);
  margin: 2px 0 0;
  font-weight: 500;
}

/* Streak badge */
.streak-badge {
  display: inline-block;
  margin-left: 6px;
  font-size: 12px;
  background: var(--color-brand-peach);
  color: var(--color-ink);
  border-radius: var(--radius-pill);
  padding: 1px 6px;
  font-weight: 600;
}
.streak-badge.flame-tier-7 { font-size: 13px; animation: flame-pulse 400ms /* durations.medium */ ease-in-out infinite; }
.streak-badge.flame-tier-14 { font-size: 14px; animation: flame-pulse 500ms ease-in-out infinite; }
.streak-badge.flame-tier-30 { font-size: 15px; animation: flame-pulse 600ms ease-in-out infinite; }
.streak-badge.reduced-motion { animation: none; }

@keyframes flame-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.03); /* scales.pulse */ }
}

/* Status badge — pill with Vant icon + label, color per state */
.chore-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  padding: 4px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-surface-card);
  color: var(--color-muted);
  flex-shrink: 0;
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

/* ── Settings entry — top-right gear, floats above the hero ── */
.home-settings-link {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-pill);
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  color: var(--color-muted);
  z-index: 5;
  transition: background 0.15s, color 0.15s;
}
.home-settings-link:active { transform: scale(0.92); color: var(--color-ink); }
</style>
