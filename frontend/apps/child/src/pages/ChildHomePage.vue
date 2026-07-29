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

      <!-- Balance hero — shared component (wrapper hosts star-flight target ref) -->
      <div ref="balanceCardRef">
        <BalanceHero :amount="balance" variant="home" coin-tiers-mode="collapsible" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" animate-changes :reacting="balanceReactMode" />
      </div>

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
        <div
          v-for="c in todayChores"
          :key="c.id"
          :ref="(el) => setChoreCardRef(c.id, el as HTMLElement | null)"
          class="chore-card"
          :class="c.status"
          @click="navigateToTask(c.id)"
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
          <button
            v-if="c.status === 'available' && !c.is_pool_unclaimed"
            class="btn-complete-home"
            :disabled="submittingId === c.id"
            @click.stop="showCompleteConfirm(c)"
          >{{ t('chore.complete') }}</button>
          <button
            v-else-if="c.status === 'available' && c.is_pool_unclaimed"
            class="btn-claim-home"
            :disabled="claimingId === c.id || submittingId === c.id"
            @click.stop="claim(c.id)"
          >{{ claimingId === c.id ? t('chore.claiming') : t('chore.claim') }}</button>
          <span v-else class="chore-status-badge" :class="c.status">
            <van-icon v-if="c.status === 'approved'" name="success" size="14" />
            <van-icon v-else-if="c.status === 'rejected'" name="warning-o" size="14" />
            <van-icon v-else-if="c.status === 'pending_approval'" name="clock-o" size="14" />
            <van-icon v-else name="arrow" size="14" />
            <span class="chore-status-text">{{ statusLabel(c.status) }}</span>
          </span>
        </div>
      </div>
    </div>

    <!-- Active challenges -->
    <ChallengeCard ref="challengeCard" />

    <!-- Badge wall entry -->
    <router-link to="/badges" class="badge-entry-card">
      <div class="badge-entry-info">
        <span class="badge-entry-icon">🏅</span>
        <div>
          <p class="badge-entry-title">{{ t('badges.entryTitle') }}</p>
          <p class="badge-entry-sub">{{ t('badges.entryEmpty') }}</p>
        </div>
      </div>
      <van-icon name="arrow" size="16" color="var(--color-muted-soft)" />
    </router-link>

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

    <!-- Complete confirmation sheet -->
    <van-popup
      v-model:show="completeSheetVisible"
      position="bottom"
      round
      :style="{ padding: '24px 20px 40px' }"
    >
      <p class="complete-sheet-title">{{ t('chore.completeTitle') }}</p>
      <div v-if="completeTarget" class="complete-sheet-chore">
        <span class="complete-sheet-emoji">{{ completeTarget.chore_emoji || '📋' }}</span>
        <div>
          <p class="complete-sheet-name">{{ completeTarget.chore_name }}</p>
          <p class="complete-sheet-reward">+{{ completeTarget.coin_reward }} ⭐</p>
        </div>
      </div>
      <button
        class="btn-keep-going seal-btn"
        :data-spinning="sealSpinning"
        @click="doComplete"
      >
        <span class="seal-icon">🔒</span>
        {{ t('celebration.sealTreasureChest') }}
      </button>
      <button class="btn-sheet-cancel" @click="completeSheetVisible = false; completeTarget = null">
        {{ t('chore.completeCancel') }}
      </button>
    </van-popup>

    <!-- Celebration animation -->
    <CelebrationAnimation
      :visible="celebrationVisible"
      :task-count="celebrationTaskCount"
      :stars-earned="celebrationStarsEarned"
      :streak-tier="celebrationStreakTier"
      :task-refs="choreCardRefs"
      :balance-ref="balanceCardRef"
      :task-ids="celebrationTaskIds"
      @dismiss="onCelebrationDismissWrapped"
      @balance-react="onBalanceReact"
      @balance-react-end="onBalanceReactEnd"
    />
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildHome' })
import { ref, computed, onMounted, watch } from 'vue'
import { usePageLoading } from '@/composables/usePageLoading'
import ProgressRing from '@/components/ProgressRing.vue'
import ChildHomeSkeleton from '@/components/skeletons/ChildHomeSkeleton.vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { useRouter } from 'vue-router'
import { getMyChores, markChoreComplete, claimChore, type ChoreInstance } from '@/api/chores'
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
import { tryVibrate } from '@/composables/useHaptic'
import { MOTION } from '@/utils/motionTokens'
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
  celebrationTaskIds,
  celebrationStreakTier,
  onCelebrationDismiss,
  checkAndTriggerCelebration,
} = useCelebration()

// Star-flight position refs
const choreCardRefs = ref<Map<string, HTMLElement>>(new Map())
const balanceCardRef = ref<HTMLElement | null>(null)
function setChoreCardRef(id: string, el: HTMLElement | null): void {
  if (el) {
    choreCardRefs.value.set(id, el)
  } else {
    choreCardRefs.value.delete(id)
  }
}

// Completion state
const completeSheetVisible = ref(false)
const completeTarget = ref<ChoreInstance | null>(null)
const submittingId = ref<string | null>(null)
const claimingId = ref<string | null>(null)
const sealSpinning = ref(false)
const balanceReactMode = ref<'pop' | 'invert' | null>(null)

function onBalanceReact(mode: 'pop' | 'invert'): void {
  balanceReactMode.value = mode
}
function onBalanceReactEnd(): void {
  balanceReactMode.value = null
}
function onCelebrationDismissWrapped(): void {
  onCelebrationDismiss()
  balanceReactMode.value = null
}

function navigateToTask(id: string) {
  router.push({ path: '/tasks', query: { highlight: id } })
}

function showCompleteConfirm(chore: ChoreInstance) {
  completeTarget.value = chore
  completeSheetVisible.value = true
}

async function doComplete() {
  if (!completeTarget.value) return
  const instanceId = completeTarget.value.id
  sealSpinning.value = true
  setTimeout(() => { sealSpinning.value = false }, 350)
  completeSheetVisible.value = false
  completeTarget.value = null
  await complete(instanceId)
}

async function complete(instanceId: string) {
  submittingId.value = instanceId
  try {
    const updated = await markChoreComplete(instanceId)
    const idx = todayChores.value.findIndex(c => c.id === instanceId)
    if (idx !== -1) todayChores.value[idx] = updated
    tryVibrate(MOTION.haptic.rewardPulse)
    if (topWish.value) {
      const chore = todayChores.value.find(c => c.id === instanceId)
      const stars = chore?.coin_reward ?? 0
      showSuccessToast(t('chore.wishProgressBump', { stars, wishName: topWish.value.name }))
    }
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    submittingId.value = null
  }
}

async function claim(instanceId: string) {
  const target = todayChores.value.find(c => c.id === instanceId)
  if (!target || target.status !== 'available' || !target.is_pool_unclaimed) return
  claimingId.value = instanceId
  const idx = todayChores.value.findIndex(c => c.id === instanceId)
  if (idx !== -1) todayChores.value[idx] = { ...todayChores.value[idx], is_pool_unclaimed: false }
  try {
    const updated = await claimChore(instanceId)
    if (idx !== -1) todayChores.value[idx] = updated
  } catch {
    if (idx !== -1) todayChores.value[idx] = { ...todayChores.value[idx], is_pool_unclaimed: true }
    showFailToast(t('chore.claimFailed'))
  } finally {
    claimingId.value = null
  }
}

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

// Trigger celebration when chores change (e.g., after completion)
watch(todayChores, (next) => {
  checkAndTriggerCelebration(next)
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

/* ── Chore preview cards — tap to navigate; button to act ── */
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
  cursor: pointer;
}
.chore-card:active { transform: scale(0.98); }
.chore-card.approved { opacity: 0.55; }
.chore-card.rejected { opacity: 0.45; }
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

/* ── Badge wall entry card ── */
.badge-entry-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  margin-bottom: var(--space-lg);
  text-decoration: none;
  border: 1px solid var(--color-hairline);
  transition: transform 0.15s;
}
.badge-entry-card:active { transform: scale(0.98); }
.badge-entry-info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.badge-entry-icon { font-size: 28px; flex-shrink: 0; }
.badge-entry-title {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 2px;
}
.badge-entry-sub {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  margin: 0;
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

/* ── Inline action buttons on chore cards ── */
.btn-complete-home {
  background: var(--color-brand-pink);
  color: var(--color-on-dark);
  border: none;
  border-radius: var(--radius-md);
  padding: 0 14px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  height: 36px;
  white-space: nowrap;
  flex-shrink: 0;
  transition: opacity 0.15s, transform 0.1s;
}
.btn-complete-home:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-complete-home:active:not(:disabled) { transform: scale(0.96); }

.btn-claim-home {
  background: var(--color-brand-mint);
  color: var(--color-ink);
  border: none;
  border-radius: var(--radius-md);
  padding: 0 14px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  height: 36px;
  white-space: nowrap;
  flex-shrink: 0;
  transition: opacity 0.15s, transform 0.1s;
}
.btn-claim-home:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-claim-home:active:not(:disabled) { transform: scale(0.96); }

/* ── Complete confirmation sheet ── */
.complete-sheet-title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 16px;
  text-align: center;
}
.complete-sheet-chore {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 16px;
}
.complete-sheet-emoji { font-size: 32px; }
.complete-sheet-name {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}
.complete-sheet-reward {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-brand-ochre);
  margin: 4px 0 0;
  font-weight: 500;
}
.btn-keep-going {
  width: 100%;
  background: var(--color-brand-pink);
  color: var(--color-on-dark);
  border: none;
  border-radius: var(--radius-md);
  padding: 14px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  transition: transform 0.1s;
}
.btn-keep-going:active { transform: scale(0.96); }
.seal-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.seal-btn .seal-icon {
  display: inline-block;
  font-size: 18px;
  line-height: 1;
  transform-origin: center;
  transition: transform 100ms ease-out;
}
.seal-btn[data-spinning='true'] {
  animation: seal-press 250ms cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.seal-btn[data-spinning='true'] .seal-icon {
  animation: seal-spin 300ms ease-out;
}
@keyframes seal-spin {
  from { transform: rotate(0); }
  to { transform: rotate(360deg); }
}
@keyframes seal-press {
  0% { transform: scale(1); }
  30% { transform: scale(0.95); }
  60% { transform: scale(1.05); }
  100% { transform: scale(1); }
}
.btn-sheet-cancel {
  width: 100%;
  background: var(--color-surface-soft);
  color: var(--color-muted);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 14px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  min-height: 44px;
  margin-top: 8px;
  transition: transform 0.1s;
}
.btn-sheet-cancel:active { transform: scale(0.96); }
</style>
