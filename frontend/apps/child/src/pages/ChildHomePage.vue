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
      <!-- Balance hero — progress ring card -->
      <div class="hero-card">
        <HackerGreeting
          :name="childAuthStore.childUser?.display_name ?? ''"
          :balance="balance"
          class="hero-greeting"
        />
        <p class="hero-label">{{ t('home.myStars') }}</p>
        <CoinDisplay :amount="balance" :icon-size="32" class="hero-balance" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" />
        <ProgressRing
          v-if="!loadingChores && todayChores.length > 0"
          :completed="completedChores"
          :pending="pendingChores"
          :total="todayChores.length"
          :total-coins="totalChoreCoins"
          :loading="loadingChores"
          class="hero-ring"
        />
      </div>

    <!-- Today's chores -->
    <div class="section">
      <p class="section-title">{{ t('home.todayTasks') }}</p>
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
          class="chore-card"
          :class="c.status"
        >
          <div class="chore-card-row">
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
              <p v-if="daysToNextBonus(c.streak_count) !== null" class="days-to-bonus">
                {{ t('chore.daysToBonus', { days: daysToNextBonus(c.streak_count) }) }}
              </p>
            </div>
            <button
              v-if="c.is_pool_unclaimed"
              class="btn-complete"
              :disabled="!isClaimable(c) || claimingId === c.id || submittingId === c.id"
              @click="claim(c.id)"
            >{{ claimingId === c.id ? t('chore.claiming') : t('chore.claim') }}</button>
            <template v-else-if="c.status === 'available'">
              <button
                class="btn-complete"
                :disabled="submittingId === c.id"
                @click="complete(c.id)"
              >{{ t('chore.complete') }}</button>
              <button
                class="btn-abandon"
                :disabled="submittingId === c.id || claimingId === c.id || abandoningId === c.id"
                @click="abandon(c)"
              >{{ t('chore.abandon') }}</button>
            </template>
            <span v-else class="chore-status-badge" :class="c.status">{{ statusLabel(c.status) }}</span>
          </div>
          <p
            v-if="c.is_pool_unclaimed && claimDisabledReason(c)"
            class="claim-disabled-hint"
          >{{ claimDisabledReason(c) }}</p>
        </div>
      </div>
    </div>

    <!-- Motivational abandon sheet -->
    <van-popup
      v-model:show="abandonSheetVisible"
      position="bottom"
      round
      :style="{ padding: '24px 20px 40px' }"
    >
      <p class="abandon-sheet-title">{{ t('chore.abandonTitle') }}</p>
      <div v-if="abandonTarget" class="abandon-sheet-chore">
        <span class="abandon-sheet-emoji">{{ abandonTarget.chore_emoji || '✅' }}</span>
        <div>
          <p class="abandon-sheet-name">{{ abandonTarget.chore_name }}</p>
          <p class="abandon-sheet-reward">+{{ abandonTarget.coin_reward }} ⭐</p>
        </div>
      </div>
      <p v-if="topWish && topWish.star_coin_cost" class="abandon-sheet-hint">
        {{ t('chore.abandonWishHint', { wishName: topWish.name, remaining: Math.max(0, topWish.star_coin_cost - balance) }) }}
      </p>
      <button class="btn-keep-going" @click="abandonSheetVisible = false">
        {{ t('chore.abandonKeepGoing') }}
      </button>
      <button
        class="btn-abandon-confirm"
        :disabled="abandoningId !== null"
        @click="doAbandon"
      >
        {{ t('chore.abandonConfirm') }}
      </button>
    </van-popup>

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
        <p class="settings-label">{{ t('home.settingsLanguage') }}</p>
        <div class="theme-options">
          <button
            v-for="opt in languageOptions"
            :key="opt.value"
            class="theme-btn"
            :class="{ active: currentLocale === opt.value }"
            @click="setLocale(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
        <button class="logout-btn" @click="handleLogout">
          {{ t('home.logout') }}
        </button>
      </div>
    </div>

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
import { showConfirmDialog, showToast, showSuccessToast, showFailToast } from 'vant'
import { getMyChores, markChoreComplete, claimChore, abandonChore, type ChoreInstance } from '@/api/chores'
import { getChildCalendar } from '@/api/calendar'
import { listChildWishes, type ChildWish } from '@/api/childWishes'
import { getCoinBalance } from '@/api/coins'
import CoinDisplay from '@/components/coins/CoinDisplay.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import CelebrationAnimation from '@/components/CelebrationAnimation.vue'
import ChallengeCard from '@/components/ChallengeCard.vue'
import HackerGreeting from '@/components/HackerGreeting.vue'
import EmptyState from '@/components/EmptyState.vue'
import noTasksSvgRaw from '@/assets/empty-states/no-tasks.svg?raw'
import { useFamilyStore } from '@/stores/family'

const noTasksSvg = noTasksSvgRaw
import { useDarkMode } from '@/utils/darkMode'
import { useLocale } from '@/utils/locale'
import { useCelebration } from '@/composables/useCelebration'
import { useBalancePolling } from '@/composables/useBalancePolling'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { tryVibrate } from '@/composables/useHaptic'
import { MOTION } from '@/utils/motionTokens'
import { useChildAuthStore } from '@numina/auth'
import { getMainBaseUrl } from '@/utils/mainApp'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()
const { complete: completeLoading } = usePageLoading()
const { themeMode, setMode } = useDarkMode()
const { currentLocale, setLocale } = useLocale()
const childAuthStore = useChildAuthStore()

// Balance polling via composable
const { balance, refresh: refreshBalance } = useBalancePolling()
const reducedMotion = useReducedMotion()
const todayChores = ref<ChoreInstance[]>([])
const loadingChores = ref(true)
const refreshing = ref(false)

// ProgressRing derived data
const completedChores = computed(() => todayChores.value.filter(c => c.status === 'approved').length)
const pendingChores = computed(() => todayChores.value.filter(c => c.status === 'pending_approval').length)
const totalChoreCoins = computed(() => todayChores.value.reduce((sum, c) => sum + (c.coin_reward ?? 0), 0))
const submittingId = ref<string | null>(null)
const claimingId = ref<string | null>(null)
const abandoningId = ref<string | null>(null)
const abandonSheetVisible = ref(false)
const abandonTarget = ref<ChoreInstance | null>(null)
const topWish = ref<ChildWish | null>(null)
const settingsExpanded = ref(false)

// Celebration state via composable
const {
  celebrationVisible,
  celebrationTaskCount,
  celebrationStarsEarned,
  onCelebrationDismiss,
  checkAndTriggerCelebration,
} = useCelebration()

const themeOptions = computed(() => [
  { value: 'system' as const, label: t('home.themeSystem') },
  { value: 'light' as const, label: t('home.themeLight') },
  { value: 'dark' as const, label: t('home.themeDark') },
])

const languageOptions = computed(() => [
  { value: 'zh-CN' as const, label: t('home.langZhCN') },
  { value: 'en-US' as const, label: t('home.langEnUS') },
])

// Streak tier helper: returns threshold value (7, 14, 30) or '0' for below 7
function streakTier(count: number): string {
  if (count >= 30) return '30'
  if (count >= 14) return '14'
  if (count >= 7) return '7'
  return '0'
}

// Days to next streak bonus tier
function daysToNextBonus(streakCount: number): number | null {
  if (streakCount <= 1) return null // No streak yet
  if (streakCount >= 30) return null // Already at max tier
  const thresholds = [7, 14, 30]
  const nextThreshold = thresholds.find(t => streakCount < t)
  return nextThreshold ? nextThreshold - streakCount : null
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

function isClaimable(c: ChoreInstance): boolean {
  return c.is_pool_unclaimed && c.status === 'available'
}

function claimDisabledReason(c: ChoreInstance): string {
  if (!c.is_pool_unclaimed) return ''
  if (c.status !== 'available') return t('chore.claimDisabledUnavailable')
  return ''
}

async function complete(instanceId: string) {
  submittingId.value = instanceId
  try {
    const updated = await markChoreComplete(instanceId)
    const idx = todayChores.value.findIndex(c => c.id === instanceId)
    if (idx !== -1) todayChores.value[idx] = updated
    // Haptic feedback after successful completion
    tryVibrate(MOTION.haptic.rewardPulse)
    // Wish progress bump toast if active wish exists
    if (topWish.value) {
      const chore = todayChores.value.find(c => c.id === instanceId)
      const stars = chore?.coin_reward ?? 0
      showSuccessToast(t('chore.wishProgressBump', { stars, wishName: topWish.value.name }))
    }
    // Refresh balance after completing a chore
    await refreshBalance()
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    submittingId.value = null
  }
}

async function claim(instanceId: string) {
  const target = todayChores.value.find(c => c.id === instanceId)
  if (!target || !isClaimable(target)) return
  claimingId.value = instanceId
  // Optimistic update
  const idx = todayChores.value.findIndex(c => c.id === instanceId)
  if (idx !== -1) todayChores.value[idx] = { ...todayChores.value[idx], is_pool_unclaimed: false }
  try {
    const updated = await claimChore(instanceId)
    if (idx !== -1) todayChores.value[idx] = updated
  } catch {
    // Revert optimistic update
    if (idx !== -1) todayChores.value[idx] = { ...todayChores.value[idx], is_pool_unclaimed: true }
    showFailToast(t('chore.claimFailed'))
  } finally {
    claimingId.value = null
  }
}

function abandon(chore: ChoreInstance) {
  abandonTarget.value = chore
  abandonSheetVisible.value = true
}

async function doAbandon() {
  if (!abandonTarget.value) return
  const instanceId = abandonTarget.value.id
  abandoningId.value = instanceId
  try {
    await abandonChore(instanceId)
    todayChores.value = todayChores.value.filter(c => c.id !== instanceId)
    abandonSheetVisible.value = false
    abandonTarget.value = null
  } catch {
    showFailToast(t('chore.abandonFailed'))
    abandonTarget.value = null
  } finally {
    abandoningId.value = null
  }
}

async function handleLogout() {
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('home.logoutConfirm'),
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    await childAuthStore.childLogout()
    showToast(t('toast.logoutSuccess'))
    // Redirect to main app login page (child app has no auth routes)
    // Use getMainBaseUrl() so dev mode (port 5174) redirects to main app (5173);
    // VITE_MAIN_APP_URL alone is empty in dev, which would hit /login on the child server → 404.
    const baseUrl = getMainBaseUrl()
    window.location.href = `${baseUrl}/login`
  } catch {
    // User cancelled or logout failed
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
    // Complete page loading - skeleton takes over visual feedback
    completeLoading()
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

function fetchChildMonth(year: number, month: number) {
  return getChildCalendar(year, month)
}

onMounted(load)
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
  --coin-text-gold:   var(--color-ink);
  --coin-text-silver: var(--color-ink);
  --coin-text-copper: var(--color-ink);
}
[data-theme="dark"] .hero-card {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-ochre-rgb), 0.16), rgba(var(--color-brand-ochre-rgb), 0.08)),
    var(--color-surface-card);
  color: var(--color-on-feature-ochre);
  --coin-text-gold:   var(--color-on-feature-ochre);
  --coin-text-silver: var(--color-on-feature-ochre);
  --coin-text-copper: var(--color-on-feature-ochre);
}
.hero-label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 8px;
  opacity: 0.75;
}
.hero-greeting {
  margin-bottom: 4px;
}
.hero-balance {
  font-size: 32px;
  font-weight: 600;
}
.hero-ring {
  margin-top: 20px;
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
  flex-direction: column;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--color-hairline);
  min-height: 56px;
}
.chore-card-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.chore-card.approved { opacity: 0.55; }
.chore-emoji { font-size: 24px; }
.chore-info { flex: 1; }
.claim-disabled-hint {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted-soft);
  margin: 6px 0 0;
  padding-left: 36px;
}
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

/* Days to bonus hint */
.days-to-bonus {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted-soft);
  margin: 2px 0 0;
}

/* Complete button */
.btn-complete {
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
  transition: opacity 0.15s, transform 0.1s;
}
.btn-complete:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-complete:active:not(:disabled) { transform: scale(0.96); }

/* Abandon button */
.btn-abandon {
  background: var(--color-surface-soft);
  color: var(--color-muted);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 0 10px;
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  height: 36px;
  white-space: nowrap;
  transition: opacity 0.15s, transform 0.1s;
  margin-left: 8px;
}
.btn-abandon:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-abandon:active:not(:disabled) { transform: scale(0.96); }

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
.logout-btn {
  width: 100%;
  margin-top: 16px;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-hairline);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-muted);
  cursor: pointer;
  transition: all 0.15s;
  min-height: 44px;
}
.logout-btn:active { transform: scale(0.96); }

/* ── Abandon sheet ── */
.abandon-sheet-title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 16px;
  text-align: center;
}

.abandon-sheet-chore {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 16px;
}

.abandon-sheet-emoji {
  font-size: 32px;
}

.abandon-sheet-name {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.abandon-sheet-reward {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-brand-ochre);
  margin: 4px 0 0;
  font-weight: 500;
}

.abandon-sheet-hint {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
  margin: 0 0 20px;
  text-align: center;
  line-height: 1.5;
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

.btn-abandon-confirm {
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
.btn-abandon-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-abandon-confirm:active:not(:disabled) { transform: scale(0.96); }
</style>
