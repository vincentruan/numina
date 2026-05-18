<template>
  <div class="chores-page">
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

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <div v-else-if="chores.length === 0" class="empty">
      <p>{{ t('chore.noChoresTitle') }}</p>
    </div>

    <div v-else class="chore-list">
      <div
        v-for="chore in chores"
        :key="chore.id"
        class="chore-card"
        :class="chore.status"
      >
        <span class="chore-emoji">{{ chore.chore_emoji || '📋' }}</span>
        <div class="chore-info">
          <p class="chore-name">{{ chore.chore_name }}</p>
          <p class="chore-reward">
            +{{ chore.coin_reward }} ⭐
            <span v-if="chore.streak_count > 1" class="streak-badge">🔥{{ chore.streak_count }}</span>
          </p>
        </div>
        <div class="chore-action">
          <button
            v-if="chore.is_pool_unclaimed"
            class="btn-complete"
            :disabled="claimingId === chore.id || submittingId === chore.id"
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
      <button class="btn-keep-going" @click="doComplete">
        {{ t('chore.completeConfirm') }}
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

    <!-- Celebration animation -->
    <CelebrationAnimation
      :visible="taskCelebrationVisible"
      :task-count="celebrationTaskCount"
      :stars-earned="celebrationStarsEarned"
      @dismiss="onCelebrationDismiss"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { getUser } from '@numina/auth'
import { getMyChores, markChoreComplete, claimChore, abandonChore, type ChoreInstance } from '@/api/chores'
import { getMyMilestones } from '@/api/milestones'
import { getCoinBalance } from '@/api/coins'
import { listChildWishes, type ChildWish } from '@/api/childWishes'
import MilestoneCelebration from '@/components/MilestoneCelebration.vue'
import CelebrationAnimation from '@/components/CelebrationAnimation.vue'
import DrawAnimation from '@/components/blindBox/DrawAnimation.vue'
import { childBlindBoxApi } from '@/api/blindBox'
import type { BlindBoxDraw } from '@/types/blindBox'
import http from '@/api/index'
import { useCelebration } from '@/composables/useCelebration'

const { t, locale } = useI18n()

const chores = ref<ChoreInstance[]>([])
const loading = ref(true)
const error = ref('')
const submittingId = ref<string | null>(null)
const claimingId = ref<string | null>(null)
const abandoningId = ref<string | null>(null)
const completeSheetVisible = ref(false)
const completeTarget = ref<ChoreInstance | null>(null)
const abandonSheetVisible = ref(false)
const abandonTarget = ref<ChoreInstance | null>(null)
const balance = ref(0)
const topWish = ref<ChildWish | null>(null)
const celebrationVisible = ref(false)
const celebrationMilestone = ref('')
const milestoneQueue = ref<{ id: string; milestone_type: string }[]>([])
const autoDraw = ref<BlindBoxDraw | null>(null)
const showAutoDrawOverlay = ref(false)

// Celebration state via composable (renamed to avoid conflict with milestone celebrationVisible)
const {
  celebrationVisible: taskCelebrationVisible,
  celebrationTaskCount,
  celebrationStarsEarned,
  onCelebrationDismiss,
  checkAndTriggerCelebration,
} = useCelebration()

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

function showCompleteConfirm(chore: ChoreInstance) {
  completeTarget.value = chore
  completeSheetVisible.value = true
}

async function doComplete() {
  if (!completeTarget.value) return
  const instanceId = completeTarget.value.id
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
    showToast(t('chore.claimFailed'))
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
    showToast(t('chore.abandonFailed'))
    abandonTarget.value = null
  } finally {
    abandoningId.value = null
  }
}

onMounted(async () => {
  await load()
  await checkNewMilestones()
  try {
    const [bal, wishData] = await Promise.all([
      getCoinBalance().catch(() => 0),
      listChildWishes().catch(() => null),
    ])
    balance.value = bal
    const active = wishData?.active ?? []
    topWish.value = active.find(w => w.priority === 'high') ?? active[0] ?? null
  } catch {
    // non-blocking
  }

  // Check for pending celebrations after data loads
  checkAndTriggerCelebration(chores.value)
})

onUnmounted(() => {
  pollCancelled = true
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
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
  display: flex;
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