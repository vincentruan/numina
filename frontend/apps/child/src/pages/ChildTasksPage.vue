<template>
  <div class="chores-page">
    <!-- Skeleton during initial load -->
    <ChildTasksSkeleton v-if="loading && !refreshing && chores.length === 0" />

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
    <!-- Date navigation — flat card -->
    <div class="date-nav-card">
      <button
        class="nav-btn prev"
        :aria-label="t('chore.prevDay')"
        @click="prevDay"
      >
        <van-icon name="arrow-left" size="18" />
      </button>
      <div class="date-display">
        <p class="date-text">{{ dateLabel }}</p>
        <p v-if="isToday" class="today-badge">{{ t('chore.today') }}</p>
      </div>
      <button
        v-if="!isToday"
        class="nav-btn next"
        :aria-label="t('chore.nextDay')"
        @click="nextDay"
      >
        <van-icon name="arrow-right" size="18" />
      </button>
      <div v-else class="nav-btn-placeholder" />
    </div>

    <!-- Balance hero — shared component (wrapper hosts star-flight target ref) -->
    <div ref="balanceCardRef">
      <BalanceHero
        :amount="balance"
        variant="tasks"
        :icon-size="26"
        :copper-to-silver="familyStore.coinCopperToSilver"
        :silver-to-gold="familyStore.coinSilverToGold"
        animate-changes
        :reacting="balanceReactMode"
      />
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <EmptyState
      v-else-if="chores.length === 0"
      :illustration="noTasksSvg"
      :text="t('empty.noTasks')"
    />

    <EmptyState
      v-else-if="allDone"
      :illustration="allDoneSvg"
      :text="t('empty.allDone')"
    />

    <div v-else-if="!allDone" class="chore-list">
      <div
        v-for="chore in chores"
        :key="chore.id"
        :ref="(el) => setChoreCardRef(chore.id, el as HTMLElement | null)"
        class="chore-card"
        :class="[chore.status, { 'highlight-flash': highlightedChoreId === chore.id }]"
      >
        <span class="chore-emoji">{{ chore.chore_emoji || '📋' }}</span>
        <CandleFlame
          v-if="chore.status === 'pending_approval' || candleStates[chore.id]"
          :state="candleStates[chore.id] ?? 'flickering'"
          :ariaLabel="t('celebration.candleAriaLabel')"
          @bloom-end="onCandleAnimationEnd(chore.id)"
          @gutter-end="onCandleAnimationEnd(chore.id)"
        />
        <div class="chore-info">
          <p class="chore-name">{{ chore.chore_name }}</p>
          <p class="chore-reward">
            +{{ chore.coin_reward }} ⭐
            <span
              v-if="chore.streak_count > 1"
              class="streak-badge"
              :class="['flame-tier-' + streakTier(chore.streak_count), { 'reduced-motion': reducedMotion }]"
            >🔥{{ chore.streak_count }}</span>
          </p>
          <p v-if="daysToNextBonus(chore.streak_count) !== null" class="days-to-bonus">
            {{ t('chore.daysToBonus', { days: daysToNextBonus(chore.streak_count) }) }}
          </p>
        </div>
        <div class="chore-action">
          <button
            v-if="chore.is_pool_unclaimed"
            class="btn-complete"
            :disabled="!isClaimable(chore) || claimingId === chore.id || submittingId === chore.id"
            @click.stop="claim(chore.id)"
          >{{ claimingId === chore.id ? t('chore.claiming') : t('chore.claim') }}</button>
          <template v-else-if="chore.status === 'available'">
            <button
              class="btn-complete"
              :disabled="submittingId === chore.id"
              @click.stop="showCompleteConfirm(chore)"
            >{{ t('chore.complete') }}</button>
            <button
              class="btn-abandon"
              :disabled="submittingId === chore.id || claimingId === chore.id || abandoningId === chore.id"
              @click.stop="abandon(chore)"
            >{{ t('chore.abandon') }}</button>
          </template>
          <span v-else-if="chore.status === 'pending_approval'" class="status-badge pending">{{ t('chore.pendingApproval') }}</span>
          <span v-else-if="chore.status === 'approved'" class="status-badge approved">{{ t('chore.approved') }}</span>
          <span v-else-if="chore.status === 'rejected'" class="status-badge rejected">{{ t('chore.rejected') }}</span>
        </div>
        <p
          v-if="chore.is_pool_unclaimed && claimDisabledReason(chore)"
          class="claim-disabled-hint"
        >{{ claimDisabledReason(chore) }}</p>
      </div>
    </div>

    <!-- Complete confirmation sheet -->
    <van-popup
      v-model:show="completeSheetVisible"
      position="bottom"
      round
      :style="{ padding: '24px 20px 40px' }"
    >
      <p class="abandon-sheet-title">{{ t('chore.completeTitle') }}</p>
      <div v-if="completeTarget" class="abandon-sheet-chore">
        <span class="abandon-sheet-emoji">{{ completeTarget.chore_emoji || '📋' }}</span>
        <div>
          <p class="abandon-sheet-name">{{ completeTarget.chore_name }}</p>
          <p class="abandon-sheet-reward">+{{ completeTarget.coin_reward }} ⭐</p>
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
      <button
        class="btn-abandon-confirm"
        @click="completeSheetVisible = false; completeTarget = null"
      >
        {{ t('chore.completeCancel') }}
      </button>
    </van-popup>

    <!-- Motivational abandon sheet -->
    <van-popup
      v-model:show="abandonSheetVisible"
      position="bottom"
      round
      :style="{ padding: '24px 20px 40px' }"
    >
      <p class="abandon-sheet-title">{{ t('chore.abandonTitle') }}</p>
      <div v-if="abandonTarget" class="abandon-sheet-chore">
        <span class="abandon-sheet-emoji">{{ abandonTarget.chore_emoji || '📋' }}</span>
        <div>
          <p class="abandon-sheet-name">{{ abandonTarget.chore_name }}</p>
          <p class="abandon-sheet-reward">+{{ abandonTarget.coin_reward }} ⭐</p>
        </div>
      </div>
      <p v-if="topWish && topWish.star_coin_cost && topWish.star_coin_cost > balance" class="abandon-sheet-hint">
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

    <MilestoneCelebration
      :visible="celebrationVisible"
      :milestone-type="celebrationMilestone"
      @dismiss="dismissCelebration"
    />

    <div
      v-if="showAutoDrawOverlay"
      class="auto-draw-overlay"
      role="dialog"
      :aria-label="t('blindBox.navTitle')"
    >
      <DrawAnimation
        :animating="false"
        :revealed="true"
        :gift="autoDraw"
        @draw="() => {}"
      />
      <button
        class="btn-close-overlay"
        @click="showAutoDrawOverlay = false; autoDraw = null"
      >
        {{ t('blindBox.autoTriggeredClose') }}
      </button>
    </div>
    </van-pull-refresh>

    <!-- Celebration animation -->
    <CelebrationAnimation
      :visible="taskCelebrationVisible"
      :task-count="celebrationTaskCount"
      :stars-earned="celebrationStarsEarned"
      :streak-tier="celebrationStreakTier"
      :task-refs="choreCardRefs"
      :balance-ref="balanceCardRef"
      :task-ids="celebrationTaskIds"
      @dismiss="onCelebrationDismiss"
      @balance-react="onBalanceReact"
      @balance-react-end="onBalanceReactEnd"
    />
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildTasks' })
import { ref, computed, onMounted, onActivated, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePageLoading } from '@/composables/usePageLoading'
import ChildTasksSkeleton from '@/components/skeletons/ChildTasksSkeleton.vue'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { getUser } from '@numina/auth'
import { getMyChores, markChoreComplete, claimChore, abandonChore, type ChoreInstance } from '@/api/chores'
import { getMyMilestones } from '@/api/milestones'
import { listChildWishes, type ChildWish } from '@/api/childWishes'
import MilestoneCelebration from '@/components/MilestoneCelebration.vue'
import CelebrationAnimation from '@/components/CelebrationAnimation.vue'
import CandleFlame from '@/components/celebration/CandleFlame.vue'
import DrawAnimation from '@/components/blindBox/DrawAnimation.vue'
import BalanceHero from '@/components/BalanceHero.vue'
import { childBlindBoxApi } from '@/api/blindBox'
import type { BlindBoxDraw } from '@/types/blindBox'
import http from '@/api/index'
import { useCelebration } from '@/composables/useCelebration'
import { useBalancePolling } from '@/composables/useBalancePolling'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { tryVibrate } from '@/composables/useHaptic'
import { MOTION } from '@/utils/motionTokens'
import { useFamilyStore } from '@/stores/family'
import EmptyState from '@/components/EmptyState.vue'
import noTasksSvgRaw from '@/assets/empty-states/no-tasks.svg?raw'
import allDoneSvgRaw from '@/assets/empty-states/all-done.svg?raw'

const noTasksSvg = noTasksSvgRaw
const allDoneSvg = allDoneSvgRaw

const { t, locale } = useI18n()
const familyStore = useFamilyStore()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

// Highlight scroll-into-view from homepage task click
const highlightedChoreId = ref<string | null>(null)
let lastHandledHighlight = ''

function scrollToHighlight() {
  const id = route.query.highlight as string | undefined
  if (!id || id === lastHandledHighlight) return
  if (!chores.value.find(c => c.id === id)) return
  lastHandledHighlight = id
  highlightedChoreId.value = id
  nextTick(() => {
    const el = choreCardRefs.value.get(id)
    if (el) {
      el.scrollIntoView({ behavior: reducedMotion.value ? 'auto' : 'smooth', block: 'center' })
    }
    // Clear the query param silently
    const query = { ...route.query }
    delete query.highlight
    router.replace({ query })
    // Clear highlight after animation
    setTimeout(() => {
      highlightedChoreId.value = null
    }, 1500)
  })
}

const chores = ref<ChoreInstance[]>([])
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const submittingId = ref<string | null>(null)
const claimingId = ref<string | null>(null)
const abandoningId = ref<string | null>(null)
const completeSheetVisible = ref(false)
const completeTarget = ref<ChoreInstance | null>(null)
const abandonSheetVisible = ref(false)
const abandonTarget = ref<ChoreInstance | null>(null)
const topWish = ref<ChildWish | null>(null)
const celebrationVisible = ref(false)
const celebrationMilestone = ref('')
const milestoneQueue = ref<{ id: string; milestone_type: string }[]>([])
const autoDraw = ref<BlindBoxDraw | null>(null)
const showAutoDrawOverlay = ref(false)

// Balance polling via composable
const { balance, lastChange: balanceLastChange } = useBalancePolling()
const reducedMotion = useReducedMotion()

const allDone = computed(() =>
  chores.value.length > 0 && chores.value.every(c => c.status === 'approved'),
)

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

function isClaimable(c: ChoreInstance): boolean {
  return c.is_pool_unclaimed && c.status === 'available' && isToday.value
}

function claimDisabledReason(c: ChoreInstance): string {
  if (!c.is_pool_unclaimed) return ''
  if (!isToday.value) return t('chore.claimDisabledHistorical')
  if (c.status !== 'available') return t('chore.claimDisabledUnavailable')
  return ''
}

// Celebration state via composable (renamed to avoid conflict with milestone celebrationVisible)
const {
  celebrationVisible: taskCelebrationVisible,
  celebrationTaskCount,
  celebrationStarsEarned,
  celebrationTaskIds,
  celebrationStreakTier,
  onCelebrationDismiss: dismissTaskCelebration,
  checkAndTriggerCelebration,
} = useCelebration()

// Position-resolution refs for star flight
const choreCardRefs = ref<Map<string, HTMLElement>>(new Map())
const balanceCardRef = ref<HTMLElement | null>(null)
function setChoreCardRef(id: string, el: HTMLElement | null): void {
  if (el) {
    choreCardRefs.value.set(id, el)
  } else {
    choreCardRefs.value.delete(id)
  }
}

// Pending-approval candle states
const candleStates = ref<Record<string, 'flickering' | 'bloom' | 'gutter'>>({})
function onCandleAnimationEnd(id: string): void {
  delete candleStates.value[id]
}

// Lock-spin on confirm button + balance reaction
const sealSpinning = ref(false)
const balanceReactMode = ref<'pop' | 'invert' | null>(null)
function onBalanceReact(mode: 'pop' | 'invert'): void {
  balanceReactMode.value = mode
}
function onBalanceReactEnd(): void {
  balanceReactMode.value = null
}

function onCelebrationDismiss(): void {
  dismissTaskCelebration()
  balanceReactMode.value = null
}

let pollCancelled = false

const selectedDate = ref(new Date())

function formatDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const currentDateString = computed(() => formatDate(selectedDate.value))

const isToday = computed(() => {
  const now = new Date()
  return formatDate(selectedDate.value) === formatDate(now)
})

const dateLabel = computed(() => selectedDate.value.toLocaleDateString(locale.value, { month: 'long', day: 'numeric', weekday: 'short' }))

function prevDay() {
  const d = new Date(selectedDate.value)
  d.setDate(d.getDate() - 1)
  selectedDate.value = d
  load()
}

function nextDay() {
  if (isToday.value) return
  const d = new Date(selectedDate.value)
  d.setDate(d.getDate() + 1)
  // Don't go past today
  const today = new Date()
  if (d > today) return
  selectedDate.value = d
  load()
}

const SEEN_KEY = `seen_milestones_${getUser()?.id ?? 'anon'}`

function getSeenIds(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]'))
  } catch {
    return new Set()
  }
}

function markSeen(id: string) {
  const seen = getSeenIds()
  seen.add(id)
  const pruned = [...seen].slice(-200)
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(pruned))
  } catch {
    // Silently fail on quota/private browsing error
  }
}

async function checkNewMilestones() {
  try {
    const milestones = await getMyMilestones()
    const seen = getSeenIds()
    const unseen = milestones.filter(m => !seen.has(m.id))
    if (unseen.length > 0) {
      milestoneQueue.value = unseen.map(m => ({ id: m.id, milestone_type: m.milestone_type }))
      showNextMilestone()
    }
  } catch {
    // non-blocking
  }
}

function showNextMilestone() {
  if (milestoneQueue.value.length === 0) return
  celebrationMilestone.value = milestoneQueue.value[0].milestone_type
  celebrationVisible.value = true
}

let dismissTimer: ReturnType<typeof setTimeout> | null = null

function dismissCelebration() {
  if (!celebrationVisible.value) return
  celebrationVisible.value = false
  if (milestoneQueue.value.length > 0) {
    markSeen(milestoneQueue.value[0].id)
    milestoneQueue.value = milestoneQueue.value.slice(1)
  }
  if (milestoneQueue.value.length > 0) {
    dismissTimer = setTimeout(showNextMilestone, 300)
  }
}

async function checkAutoDraw() {
  try {
    const res = await childBlindBoxApi.getLatestAutoDraw()
    if (res.data) {
      autoDraw.value = res.data
      showAutoDrawOverlay.value = true
    }
  } catch {
    // silent — blind box is a bonus, not critical
  }
}

async function pollForApproval(instanceId: string) {
  const interval = 5_000
  const deadline = Date.now() + 600_000 // 10 minutes
  while (Date.now() < deadline && !pollCancelled) {
    await new Promise(r => setTimeout(r, interval))
    if (pollCancelled) return
    try {
      const res = await http.get<{ status: string }>(`/child/chores/${instanceId}/status`)
      if (res.data.status === 'approved') {
        await checkAutoDraw()
        return
      }
      if (res.data.status === 'rejected') return
    } catch {
      return
    }
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    chores.value = await getMyChores(currentDateString.value)
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

function showCompleteConfirm(chore: ChoreInstance) {
  completeTarget.value = chore
  completeSheetVisible.value = true
}

async function doComplete() {
  if (!completeTarget.value) return
  const instanceId = completeTarget.value.id
  sealSpinning.value = true
  setTimeout(() => {
    sealSpinning.value = false
  }, 350)
  completeSheetVisible.value = false
  completeTarget.value = null
  await complete(instanceId)
}

async function complete(instanceId: string) {
  submittingId.value = instanceId
  try {
    const updated = await markChoreComplete(instanceId)
    const idx = chores.value.findIndex(c => c.id === instanceId)
    if (idx !== -1) chores.value[idx] = updated
    // Haptic feedback after successful completion
    tryVibrate(MOTION.haptic.rewardPulse)
    // Wish progress bump toast if active wish exists
    if (topWish.value) {
      const chore = chores.value.find(c => c.id === instanceId)
      const stars = chore?.coin_reward ?? 0
      showSuccessToast(t('chore.wishProgressBump', { stars, wishName: topWish.value.name }))
    }
    // Check for auto-triggered blind box
    if (updated.status === 'approved') {
      await checkAutoDraw()
    } else if (updated.status === 'pending_approval') {
      pollForApproval(instanceId) // intentionally not awaited — runs in background
    }
  } catch {
    error.value = t('toast.submitFailed')
  } finally {
    submittingId.value = null
  }
}

async function claim(instanceId: string) {
  const target = chores.value.find(c => c.id === instanceId)
  if (!target || !isClaimable(target)) return
  claimingId.value = instanceId
  // Optimistic update
  const idx = chores.value.findIndex(c => c.id === instanceId)
  if (idx !== -1) chores.value[idx] = { ...chores.value[idx], is_pool_unclaimed: false }
  try {
    const updated = await claimChore(instanceId)
    if (idx !== -1) chores.value[idx] = updated
  } catch {
    // Revert optimistic update
    if (idx !== -1) chores.value[idx] = { ...chores.value[idx], is_pool_unclaimed: true }
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
    chores.value = chores.value.filter(c => c.id !== instanceId)
    abandonSheetVisible.value = false
    abandonTarget.value = null
  } catch {
    showFailToast(t('chore.abandonFailed'))
    abandonTarget.value = null
  } finally {
    abandoningId.value = null
  }
}

onMounted(async () => {
  increment()
  try {
    await load()
    await checkNewMilestones()
    try {
      const wishData = await listChildWishes().catch(() => null)
      const active = wishData?.active ?? []
      topWish.value = active.find(w => w.priority === 'high') ?? active[0] ?? null
    } catch {
      // non-blocking
    }

    // Check for pending celebrations after data loads
    checkAndTriggerCelebration(chores.value)
    // Scroll to highlighted chore from homepage
    scrollToHighlight()
  } finally {
    decrement()
  }
})

// KeepAlive: re-check highlight query param on re-activation
onActivated(() => {
  scrollToHighlight()
})

// Drive candle state transitions when chore status changes after polling.
watch(
  chores,
  (next, prev) => {
    if (!prev) return
    const prevById = new Map(prev.map(c => [c.id, c.status]))
    for (const c of next) {
      const oldStatus = prevById.get(c.id)
      if (oldStatus === 'pending_approval' && c.status === 'approved') {
        candleStates.value[c.id] = 'bloom'
      } else if (oldStatus === 'pending_approval' && c.status === 'rejected') {
        candleStates.value[c.id] = 'gutter'
      }
    }
  },
  { deep: true },
)

// When the page sees newly-approved chores via polling, surface the celebration.
watch(chores, (next) => {
  checkAndTriggerCelebration(next)
})

// Non-celebration balance changes (e.g., parent grant while child is on Tasks page):
// fire a single C1 pulse on the balance card. Skip when a celebration is mid-flight
// since the celebration owns the reaction.
let popResetTimer: ReturnType<typeof setTimeout> | null = null
watch(balanceLastChange, (change) => {
  if (!change) return
  if (taskCelebrationVisible.value) return
  balanceReactMode.value = 'pop'
  if (popResetTimer) clearTimeout(popResetTimer)
  popResetTimer = setTimeout(() => {
    if (balanceReactMode.value === 'pop') {
      balanceReactMode.value = null
    }
    popResetTimer = null
  }, 600)
})

onUnmounted(() => {
  pollCancelled = true
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
  if (popResetTimer) {
    clearTimeout(popResetTimer)
    popResetTimer = null
  }
})
</script>

<style scoped>
/* ── Canvas ── */
.chores-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Date navigation — flat card ── */
.date-nav-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-bottom: var(--space-lg);
  border: 1px solid var(--color-hairline);
  min-height: 48px;
}

/* ── Balance hero is now the shared <BalanceHero> component ── */

.date-display {
  flex: 1;
  text-align: center;
}

.date-text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.today-badge {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-brand-ochre);
  margin: 4px 0 0;
  font-weight: 500;
}

.nav-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-muted);
  transition: all 0.15s;
}

.nav-btn:active {
  transform: scale(0.95);
  background: var(--color-surface-strong);
}

.nav-btn-placeholder {
  width: 36px;
  height: 36px;
}

.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: var(--color-muted-soft);
  font-size: 16px;
  font-family: Inter, sans-serif;
}

/* ── Chore list ── */
.chore-list { display: flex; flex-direction: column; gap: 12px; }

.chore-card {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: 16px;
  gap: 12px;
  border: 1px solid var(--color-hairline);
  transition: transform 0.1s;
  min-height: 64px;
}
.chore-card.available { cursor: pointer; }
.chore-card.available:active { transform: scale(0.98); }
.chore-card.approved { opacity: 0.55; }
.chore-card.rejected { opacity: 0.45; }

/* Highlight flash when scrolling to a specific chore from homepage */
.chore-card.highlight-flash {
  animation: chore-highlight 1.5s ease-out forwards;
}

@keyframes chore-highlight {
  0%, 15% {
    box-shadow: 0 0 10px rgba(255, 183, 77, 0.5);
    border-color: var(--color-brand-ochre);
  }
  100% {
    box-shadow: none;
    border-color: var(--color-hairline);
  }
}

.chore-emoji { font-size: 28px; }

.chore-info { flex: 1; }
.chore-name {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}
.chore-reward {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-brand-ochre);
  margin: 4px 0 0;
  font-weight: 500;
}

.streak-badge {
  display: inline-block;
  margin-left: 6px;
  font-size: 12px;
  background: var(--color-brand-peach);
  color: var(--color-ink);
  border-radius: var(--radius-pill);
  padding: 1px 8px;
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

.days-to-bonus {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted-soft);
  margin: 2px 0 0;
}

.claim-disabled-hint {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted-soft);
  margin: 8px 0 0;
  padding-left: 40px;
  flex-basis: 100%;
}

/* ── Complete button — pink brand CTA ── */
.btn-complete {
  background: var(--color-brand-pink);
  color: var(--color-on-dark);
  border: none;
  border-radius: var(--radius-md);
  padding: 0 18px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 44px;
  white-space: nowrap;
  transition: opacity 0.15s, transform 0.1s;
}
.btn-complete:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-complete:active:not(:disabled) { transform: scale(0.96); }

/* ── Abandon button — secondary action ── */
.btn-abandon {
  background: var(--color-surface-soft);
  color: var(--color-muted);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 0 12px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  height: 44px;
  white-space: nowrap;
  transition: opacity 0.15s, transform 0.1s;
  margin-left: 8px;
}
.btn-abandon:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-abandon:active:not(:disabled) { transform: scale(0.96); }

/* ── Status badges ── */
.status-badge {
  font-family: Inter, sans-serif;
  font-size: 13px;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  font-weight: 500;
}
.status-badge.pending  { background: var(--color-brand-peach); color: var(--color-ink); }
.status-badge.approved { background: var(--color-brand-mint); color: var(--color-ink); }
.status-badge.rejected { background: var(--color-brand-coral); color: var(--color-on-dark); }

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-dark);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-bottom: 12px;
  font-family: Inter, sans-serif;
  font-size: 14px;
}

/* ── Auto-draw overlay ── */
.auto-draw-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-lg);
}

.btn-close-overlay {
  background: var(--color-brand-mint);
  color: var(--color-ink);
  border: none;
  border-radius: var(--radius-pill);
  padding: 12px 32px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

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

/* ── Seal button (lock-spin on tap) ── */
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