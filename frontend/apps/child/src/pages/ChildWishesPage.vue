<template>
  <div class="wishes-page">
    <!-- Skeleton during initial load -->
    <ChildWishesSkeleton v-if="loading && !refreshing && wishList === null" />

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
      <!-- Balance hero — shared component -->
      <BalanceHero :amount="polledBalance" variant="wishes" />

      <!-- Wish stats — moved out of the hero per unified-hero design -->
      <div v-if="stats" class="stats-strip">
        <div class="stats-item">
          <span class="stats-num">{{ stats.active_wish_count }}</span>
          <span class="stats-label">{{ t('wishes.activeCount') }}</span>
        </div>
        <div class="stats-divider" />
        <div class="stats-item">
          <span class="stats-num">{{ totalWishes }}</span>
          <span class="stats-label">{{ t('wishes.allWishes') }}</span>
        </div>
      </div>

      <div v-if="loading && !refreshing" class="loading">{{ t('common.loading') }}</div>

      <div v-if="error && !loading" class="error-msg">{{ error }}</div>

      <!-- Constellation grid (active wishes only) -->
      <WishConstellationGrid
        v-if="!loading && activeWishes.length > 0"
        :wishes="activeWishes"
        :stats="stats"
        :days-estimate-map="wishDaysMap"
        :tint-map="wishTintMap"
        :peek-active-wish-id="peekActiveWishId"
        :peek-deltas="peekDeltas"
        :reduced-motion="reducedMotion"
        @tap="goToDetail"
        @peek-start="onPeekStart"
        @peek-end="onPeekEnd"
      />

      <!-- Active wishes -->
      <div v-if="!loading && activeWishes.length > 0" class="section">
        <p class="section-title">{{ t('wishes.sectionActive') }}</p>
        <div v-for="wish in activeWishes" :key="wish.id" class="wish-card wish-card--active">
          <div class="wish-header">
            <div class="wish-emoji-wrap">
              <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
            </div>
            <div class="wish-meta">
              <p class="wish-name">{{ wish.name }}</p>
              <span class="priority-badge" :class="wish.priority">{{ priorityLabel(wish.priority) }}</span>
            </div>
          </div>

          <div v-if="wish.has_cost_set && wish.progress !== null" class="progress-section">
            <div class="progress-track">
              <div
                class="progress-fill"
                :class="jarClass(wish.progress)"
                :style="{ width: Math.min((wish.progress ?? 0) * 100, 100) + '%' }"
              />
              <span
                v-for="(pos, i) in [0.25, 0.5, 0.75]"
                :key="i"
                class="progress-star"
                :class="{ lit: (wish.progress ?? 0) >= pos }"
                :style="{ left: pos * 100 + '%' }"
                :aria-hidden="true"
              >⭐</span>
            </div>
            <div class="progress-footer">
              <span class="progress-pct" :class="{ 'pct-full': (wish.progress ?? 0) >= 1 }">
                {{ Math.min(Math.round((wish.progress ?? 0) * 100), 100) }}%
              </span>
              <span v-if="(wish.progress ?? 0) >= 1" class="progress-hint hint-full">
                {{ t('wishes.progressFull') }}
              </span>
              <span v-else-if="daysToWish(wish.id) !== null" class="progress-hint hint-days">
                {{ t('wishes.progressDays', { days: daysToWish(wish.id) }) }}
              </span>
            </div>
          </div>
          <div v-else class="progress-pending">{{ t('wishes.waitingGoal') }}</div>

          <button
            v-if="wish.status === 'active' && wish.progress !== null && wish.progress >= 1"
            class="btn-redeem"
            :disabled="actioningId === wish.id"
            @click="redeem(wish.id)"
          >
            {{ t('wishes.redeemBtn') }}
          </button>
        </div>
      </div>

      <!-- Redemption requested -->
      <div v-if="!loading && redemptionWishes.length > 0" class="section">
        <p class="section-title">{{ t('wishes.sectionRedemption') }}</p>
        <div v-for="wish in redemptionWishes" :key="wish.id" class="wish-card wish-card--simple">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
          <div class="wish-meta">
            <p class="wish-name">{{ wish.name }}</p>
            <span class="status-badge status-redemption">{{ t('wishes.waitingRedemption') }}</span>
          </div>
        </div>
      </div>

      <!-- Pending review -->
      <div v-if="!loading && pendingWishes.length > 0" class="section">
        <p class="section-title">{{ t('wishes.sectionPending') }}</p>
        <div v-for="wish in pendingWishes" :key="wish.id" class="wish-card wish-card--simple">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
          <div class="wish-meta">
            <p class="wish-name">{{ wish.name }}</p>
            <span class="status-badge status-pending">{{ t('wishes.waitingReview') }}</span>
          </div>
        </div>
      </div>

      <!-- Realized -->
      <div v-if="!loading && realizedWishes.length > 0" class="section">
        <p class="section-title">{{ t('wishes.sectionRealized') }}</p>
        <div v-for="wish in realizedWishes" :key="wish.id" class="wish-card wish-card--simple wish-card--dim">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
          <div class="wish-meta">
            <p class="wish-name">{{ wish.name }}</p>
            <span class="status-badge status-realized">{{ t('wishes.realized') }}</span>
          </div>
        </div>
      </div>

      <!-- Rejected -->
      <div v-if="!loading && rejectedWishes.length > 0" class="section">
        <p class="section-title">{{ t('wishes.sectionRejected') }}</p>
        <div v-for="wish in rejectedWishes" :key="wish.id" class="wish-card wish-card--simple wish-card--dim">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
          <div class="wish-meta">
            <p class="wish-name">{{ wish.name }}</p>
            <span class="status-badge status-rejected">{{ t('wishes.rejected') }}</span>
            <p v-if="wish.rejection_reason" class="rejection-reason">{{ wish.rejection_reason }}</p>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <EmptyState
        v-if="!loading && totalWishes === 0"
        :illustration="noWishesSvg"
        :text="t('empty.noWishes')"
        :action-text="t('wishes.createBtn')"
        action-to="/wishes/new"
      />
    </van-pull-refresh>

    <!-- FAB -->
    <button v-if="totalWishes > 0" class="fab" :aria-label="t('wishes.createBtn')" @click="router.push({ name: 'ChildWishCreate' })">
      <van-icon name="plus" size="22" color="var(--color-on-primary)" />
    </button>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildWishes' })
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { usePageLoading } from '@/composables/usePageLoading'
import ChildWishesSkeleton from '@/components/skeletons/ChildWishesSkeleton.vue'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  listChildWishes, getChildWishStats, requestRedemption,
  type ChildWishList, type ChildWishStats
} from '@/api/childWishes'
import { getCoinLedger, type CoinTransaction } from '@/api/coins'
import { useBalancePolling } from '@/composables/useBalancePolling'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { daysEstimate, reachabilityTint, previewSpend, type ReachabilityTint, type SpendDelta } from '@numina/math'
import BalanceHero from '@/components/BalanceHero.vue'
import WishConstellationGrid from '@/components/wishes/WishConstellationGrid.vue'
import EmptyState from '@/components/EmptyState.vue'
import noWishesSvgRaw from '@/assets/empty-states/no-wishes.svg?raw'

const noWishesSvg = noWishesSvgRaw

const { t } = useI18n()
const router = useRouter()
const { increment, decrement } = usePageLoading()

// Balance polling via composable (separate from wish stats)
const { balance: polledBalance } = useBalancePolling()

const wishList = ref<ChildWishList | null>(null)
const stats = ref<ChildWishStats | null>(null)
const ledger = ref<CoinTransaction[]>([])
const loading = ref(true)
const error = ref('')
const refreshing = ref(false)
const actioningId = ref<string | null>(null)

const activeWishes = computed(() => wishList.value?.active ?? [])
const pendingWishes = computed(() => wishList.value?.pending_review ?? [])
const redemptionWishes = computed(() => wishList.value?.redemption_requested ?? [])
const realizedWishes = computed(() => wishList.value?.realized ?? [])
const rejectedWishes = computed(() => wishList.value?.rejected ?? [])
const totalWishes = computed(() =>
  activeWishes.value.length + pendingWishes.value.length + redemptionWishes.value.length +
  realizedWishes.value.length + rejectedWishes.value.length
)

const wishDaysMap = computed(() => {
  const map = new Map<string, number | null>()
  if (!stats.value?.priority_simulation) return map
  for (const sim of stats.value.priority_simulation) {
    map.set(sim.wish_id, daysEstimate(stats.value.balance, sim, ledger.value))
  }
  return map
})

const wishTintMap = computed(() => {
  const map = new Map<string, ReachabilityTint>()
  if (!stats.value?.priority_simulation) return map
  for (const sim of stats.value.priority_simulation) {
    map.set(sim.wish_id, reachabilityTint(sim, wishDaysMap.value.get(sim.wish_id) ?? null))
  }
  return map
})

function goToDetail(wishId: string) {
  router.push({ name: 'ChildWishDetail', params: { id: wishId } })
}

const PEEK_TIMEOUT_MS = 1500
const PEEK_TIMEOUT_REDUCED_MS = 3000

const reducedMotion = useReducedMotion()
const peekActiveWishId = ref<string | null>(null)
const peekDeltas = ref<SpendDelta[]>([])
let peekTimer: ReturnType<typeof setTimeout> | null = null

function clearPeekTimer() {
  if (peekTimer) {
    clearTimeout(peekTimer)
    peekTimer = null
  }
}

function endPeek() {
  clearPeekTimer()
  peekActiveWishId.value = null
  peekDeltas.value = []
}

function onPeekStart(wishId: string) {
  if (!stats.value) return
  clearPeekTimer()
  const result = previewSpend(wishId, stats.value.balance, stats.value.priority_simulation, ledger.value)
  peekActiveWishId.value = wishId
  peekDeltas.value = result.deltas
  const timeoutMs = reducedMotion.value ? PEEK_TIMEOUT_REDUCED_MS : PEEK_TIMEOUT_MS
  peekTimer = setTimeout(endPeek, timeoutMs)
}

function onPeekEnd(_wishId: string) {
  endPeek()
}

onBeforeUnmount(clearPeekTimer)

function daysToWish(wishId: string): number | null {
  return wishDaysMap.value.get(wishId) ?? null
}

function priorityLabel(p: string) {
  return p === 'high' ? t('wishes.priorityLabelHigh') : p === 'medium' ? t('wishes.priorityLabelMedium') : t('wishes.priorityLabelLow')
}

function jarClass(progress: number) {
  if (progress >= 1) return 'full'
  if (progress >= 0.5) return 'half'
  return 'low'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [list, s, l] = await Promise.all([listChildWishes(), getChildWishStats(), getCoinLedger()])
    wishList.value = list
    stats.value = s
    ledger.value = l
  } catch {
    error.value = t('errors.LOAD_FAILED')
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

async function redeem(wishId: string) {
  actioningId.value = wishId
  try {
    await requestRedemption(wishId)
    await load()
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    actioningId.value = null
  }
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
.wishes-page {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md) var(--space-md) 140px;
}

/* ── Stats strip — wish counts, below the shared balance hero ── */
.stats-strip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: var(--space-lg);
}
.stats-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.stats-num {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.stats-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
}
.stats-divider {
  width: 1px;
  height: 28px;
  background: var(--color-hairline);
}

/* ── Sections ── */
.section { margin-bottom: var(--space-lg); }
.section-title {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted);
  margin: 0 0 12px;
}

/* ── Wish cards ── */
.wish-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  border: 1px solid var(--color-hairline);
  margin-bottom: 12px;
}
.wish-card--active {
  border-left: 4px solid var(--color-brand-ochre);
  background: var(--color-surface-soft);
  background: color-mix(in srgb, var(--color-brand-ochre) 6%, var(--color-surface-soft));
}
.wish-card--simple {
  display: flex;
  align-items: center;
  gap: 12px;
}
.wish-card--dim { opacity: 0.6; }

.wish-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.wish-emoji-wrap {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.wish-emoji { font-size: 26px; }
.wish-meta { flex: 1; min-width: 0; }
.wish-name {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Want-level badges */
.priority-badge {
  font-family: Inter, sans-serif;
  font-size: 14px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  display: inline-block;
  font-weight: 600;
}
.priority-badge.high     { background: var(--color-brand-pink); color: var(--color-on-dark); }
.priority-badge.medium   { background: var(--color-brand-ochre); color: var(--color-ink); }
.priority-badge.low      { background: var(--color-brand-lavender); color: var(--color-ink); }

/* Progress track */
.progress-section { margin-bottom: 12px; }
.progress-track {
  position: relative;
  height: 12px;
  background: var(--color-surface-strong);
  border-radius: 6px;
  overflow: visible;
  margin-bottom: 8px;
}
.progress-fill {
  position: absolute;
  top: 0; left: 0;
  height: 100%;
  border-radius: 6px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  max-width: 100%;
}
.progress-fill.low  { background: var(--color-brand-lavender); }
.progress-fill.half { background: var(--color-brand-peach); }
.progress-fill.full {
  background: var(--color-brand-ochre);
  animation: goldShimmer 1.5s ease-in-out infinite;
}
@keyframes goldShimmer {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.progress-star {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  z-index: 1;
  pointer-events: none;
  /* Unlit milestone marker: dim and desaturated so it reads as "not yet",
     not as real data. Lights up gold once progress crosses its threshold. */
  filter: grayscale(1);
  opacity: 0.35;
  transition: filter 0.3s ease, opacity 0.3s ease, transform 0.3s ease;
}
.progress-star.lit {
  filter: none;
  opacity: 1;
  transform: translate(-50%, -50%) scale(1.12);
}
.progress-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-pct {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted-soft);
  min-width: 36px;
}
.progress-pct.pct-full { color: var(--color-brand-ochre); }
.progress-hint { font-family: Inter, sans-serif; font-size: 14px; }
.hint-full  { color: var(--color-brand-ochre); font-weight: 600; }
.hint-days  { color: var(--color-brand-mint); font-weight: 500; }
.progress-pending {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted-soft);
  margin-bottom: 4px;
}

/* Redeem button — ochre celebration CTA. One-shot entrance pulse when it
   appears (wish is fully funded → "you can redeem now!"), then stays static
   so it doesn't bleed attention. No permanent shimmer. */
.btn-redeem {
  width: 100%;
  background: var(--color-brand-ochre);
  color: var(--color-ink);
  border: none;
  border-radius: var(--radius-md);
  padding: 0 12px;
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  height: 52px;
  animation: redeem-pulse 0.5s ease-out 1;
  transition: transform 0.1s;
}
@keyframes redeem-pulse {
  0%   { transform: scale(0.96); opacity: 0.6; }
  60%  { transform: scale(1.04); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .btn-redeem { animation: none; }
}
.btn-redeem:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  animation: none;
}
.btn-redeem:active:not(:disabled) { transform: scale(0.97); animation: none; }

/* Status badges */
.status-badge {
  font-family: Inter, sans-serif;
  font-size: 14px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  display: inline-block;
  font-weight: 500;
}
.status-pending    { background: var(--color-brand-peach); color: var(--color-ink); }
.status-redemption { background: var(--color-brand-mint); color: var(--color-ink); }
.status-realized   { background: var(--color-brand-mint); color: var(--color-ink); }
.status-rejected   { background: var(--color-brand-coral); color: var(--color-on-dark); }

.rejection-reason {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted-soft);
  margin: 4px 0 0;
}

.loading {
  text-align: center;
  padding: 40px 0;
  color: var(--color-muted-soft);
  font-family: Inter, sans-serif;
  font-size: 15px;
}

/* FAB */
.fab {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 52px;
  height: 52px;
  border-radius: var(--radius-pill);
  background: var(--color-primary);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  transition: transform 0.15s;
}
.fab:active { transform: scale(0.92); }


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
