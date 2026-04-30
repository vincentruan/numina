<template>
  <div class="wishes-page">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Hero stats banner — peach feature card -->
      <div v-if="stats" class="hero-banner">
        <div class="hero-balance">
          <span class="hero-balance-num">{{ stats.balance }}</span>
          <span class="hero-balance-unit">{{ t('wishes.starUnit') }}</span>
        </div>
        <div class="hero-divider" />
        <div class="hero-stat">
          <span class="hero-stat-num">{{ stats.active_wish_count }}</span>
          <span class="hero-stat-label">{{ t('wishes.activeCount') }}</span>
        </div>
        <div class="hero-divider" />
        <div class="hero-stat">
          <span class="hero-stat-num">{{ totalWishes }}</span>
          <span class="hero-stat-label">{{ t('wishes.allWishes') }}</span>
        </div>
      </div>

      <div v-if="loading && !refreshing" class="loading">{{ t('common.loading') }}</div>

      <div v-if="error && !loading" class="error-msg">{{ error }}</div>

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
              <span class="progress-star" :style="{ left: '25%' }">⭐</span>
              <span class="progress-star" :style="{ left: '50%' }">⭐</span>
              <span class="progress-star" :style="{ left: '75%' }">⭐</span>
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
      <div v-if="!loading && totalWishes === 0" class="empty-state">
        <p class="empty-icon">🌠</p>
        <p class="empty-text">{{ t('wishes.emptyText') }}</p>
        <button class="btn-create-inline" @click="showCreate = true">{{ t('wishes.createBtn') }}</button>
      </div>
    </van-pull-refresh>

    <!-- FAB -->
    <button v-if="totalWishes > 0" class="fab" :aria-label="t('wishes.createBtn')" @click="showCreate = true">
      <van-icon name="plus" size="22" color="#fff" />
    </button>

    <!-- Create wish bottom sheet -->
    <van-popup v-model:show="showCreate" position="bottom" round style="padding: 24px 16px 40px">
      <p class="sheet-title">{{ t('wishes.sheetTitle') }}</p>
      <van-field
        v-model="form.name"
        :label="t('wishes.wishNameLabel')"
        :placeholder="t('wishes.wishNamePlaceholder')"
        maxlength="50"
        show-word-limit
        style="margin-bottom: 8px; border-radius: var(--radius-md); background: var(--color-surface-soft)"
      />
      <van-field
        v-model="form.emoji"
        :label="t('wishes.emojiLabel')"
        :placeholder="t('wishes.emojiPlaceholder')"
        maxlength="4"
        style="margin-bottom: 8px; border-radius: var(--radius-md); background: var(--color-surface-soft)"
      />
      <van-field
        v-model="form.description"
        :label="t('wishes.descLabel')"
        type="textarea"
        :placeholder="t('wishes.descPlaceholder')"
        maxlength="200"
        show-word-limit
        rows="2"
        autosize
        style="margin-bottom: 12px; border-radius: var(--radius-md); background: var(--color-surface-soft)"
      />
      <div class="priority-row">
        <span class="priority-label">{{ t('wishes.priorityLabel') }}</span>
        <div class="priority-chips">
          <button
            v-for="p in priorities"
            :key="p.value"
            class="priority-chip"
            :class="{ active: form.priority === p.value }"
            @click="form.priority = p.value"
          >{{ p.label }}</button>
        </div>
      </div>
      <van-button
        block
        type="primary"
        :loading="creating"
        :disabled="!form.name.trim()"
        style="margin-top: 16px; border-radius: var(--radius-md); background: var(--color-primary); border: none"
        @click="createWish"
      >{{ t('wishes.submitBtn') }}</van-button>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listChildWishes, getChildWishStats, createChildWish, requestRedemption,
  type ChildWishList, type ChildWishStats
} from '@/api/childWishes'
import { getCoinLedger, type CoinTransaction } from '@/api/coins'

const { t } = useI18n()

const wishList = ref<ChildWishList | null>(null)
const stats = ref<ChildWishStats | null>(null)
const ledger = ref<CoinTransaction[]>([])
const loading = ref(true)
const error = ref('')
const refreshing = ref(false)
const actioningId = ref<string | null>(null)

const showCreate = ref(false)
const creating = ref(false)
const form = ref({ name: '', emoji: '', description: '', priority: 'medium' as 'high' | 'medium' | 'low' })

const priorities = computed(() => [
  { value: 'high' as const, label: t('wishes.priorityHigh') },
  { value: 'medium' as const, label: t('wishes.priorityMedium') },
  { value: 'low' as const, label: t('wishes.priorityLow') },
])

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

  const now = Date.now()
  const cutoff7d = now - 7 * 24 * 60 * 60 * 1000

  const earnEntries = ledger.value.filter(tx => tx.amount > 0 && new Date(tx.created_at).getTime() >= cutoff7d)
  const earnDays = new Set<string>()
  let earnSum = 0
  for (const tx of earnEntries) {
    earnDays.add(new Date(tx.created_at).toDateString())
    earnSum += tx.amount
  }

  const distinctDays = earnDays.size
  if (distinctDays < 3) return map

  const dailyAvg = earnSum / distinctDays
  if (dailyAvg <= 0) return map

  for (const sim of stats.value.priority_simulation) {
    if (sim.star_coin_cost == null) {
      map.set(sim.wish_id, null)
      continue
    }
    const remaining = sim.star_coin_cost - stats.value.balance
    if (remaining <= 0) {
      map.set(sim.wish_id, null)
      continue
    }
    map.set(sim.wish_id, Math.ceil(remaining / dailyAvg))
  }
  return map
})

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
  } finally {
    actioningId.value = null
  }
}

async function createWish() {
  if (!form.value.name.trim()) return
  creating.value = true
  try {
    await createChildWish({
      name: form.value.name.trim(),
      emoji: form.value.emoji || undefined,
      description: form.value.description || undefined,
      priority: form.value.priority,
    })
    showCreate.value = false
    form.value = { name: '', emoji: '', description: '', priority: 'medium' }
    await load()
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* ── Canvas ── */
.wishes-page {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: 16px 16px 100px;
}

/* ── Hero banner — peach feature card ── */
.hero-banner {
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: var(--color-brand-peach);
  border-radius: var(--radius-xl);
  padding: 24px 16px;
  margin-bottom: 24px;
  color: var(--color-ink);
}
.hero-balance {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.hero-balance-num {
  font-family: Inter, sans-serif;
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
}
.hero-balance-unit {
  font-family: Inter, sans-serif;
  font-size: 13px;
  opacity: 0.7;
}
.hero-divider {
  width: 1px;
  height: 36px;
  background: rgba(10, 10, 10, 0.2);
}
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.hero-stat-num {
  font-family: Inter, sans-serif;
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}
.hero-stat-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  opacity: 0.7;
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

/* ── Wish cards ── */
.wish-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--color-hairline);
  margin-bottom: 12px;
}
.wish-card--active {
  border-left: 4px solid var(--color-brand-ochre);
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

/* Priority badges */
.priority-badge {
  font-family: Inter, sans-serif;
  font-size: 11px;
  padding: 2px 10px;
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
  font-size: 10px;
  z-index: 1;
  pointer-events: none;
  opacity: 0.5;
}
.progress-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-pct {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-muted-soft);
  min-width: 36px;
}
.progress-pct.pct-full { color: var(--color-brand-ochre); }
.progress-hint { font-family: Inter, sans-serif; font-size: 12px; }
.hint-full  { color: var(--color-brand-ochre); font-weight: 600; }
.hint-days  { color: var(--color-brand-mint); font-weight: 500; }
.progress-pending {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  margin-bottom: 4px;
}

/* Redeem button — primary CTA */
.btn-redeem {
  width: 100%;
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: none;
  border-radius: var(--radius-md);
  padding: 12px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 44px;
  animation: goldShimmer 1.5s ease-in-out infinite;
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
  font-size: 12px;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  display: inline-block;
  font-weight: 500;
}
.status-pending    { background: var(--color-surface-card); color: var(--color-muted); }
.status-redemption { background: var(--color-brand-mint); color: var(--color-ink); }
.status-realized   { background: var(--color-brand-mint); color: var(--color-ink); }
.status-rejected   { background: var(--color-brand-coral); color: var(--color-on-dark); }

.rejection-reason {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  margin: 4px 0 0;
}

/* Empty state */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-icon  { font-size: 56px; margin: 0 0 12px; }
.empty-text  {
  font-family: Inter, sans-serif;
  font-size: 16px;
  color: var(--color-muted-soft);
  margin: 0 0 20px;
}
.btn-create-inline {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: none;
  border-radius: var(--radius-md);
  padding: 12px 28px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 44px;
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

/* Create sheet */
.sheet-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  text-align: center;
  margin: 0 0 16px;
}
.priority-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
}
.priority-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  white-space: nowrap;
}
.priority-chips { display: flex; gap: 8px; }
.priority-chip {
  padding: 6px 14px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--color-body);
}
.priority-chip.active {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border-color: var(--color-primary);
}

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-primary);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin: 0 16px 16px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  text-align: center;
}
</style>
