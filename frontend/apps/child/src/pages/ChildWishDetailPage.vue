<template>
  <div class="wish-detail-page">
    <ChildInlineError v-model:visible="inlineError.visible" :message="inlineError.message" />
    <!-- Skeleton during initial load -->
    <ChildWishDetailSkeleton v-if="loading" />

    <!-- Actual content -->
    <template v-else>
    <PageHeader :title="t('wishes.sectionActive')" />

    <div v-if="!wish" class="empty-state">
      <p class="empty-icon">🌠</p>
      <p class="empty-text">{{ t('wishes.constellation.detailUnknown') }}</p>
      <button class="btn-back" @click="router.replace({ name: 'ChildWishes' })">{{ t('common.back') }}</button>
    </div>

    <div v-else class="wish-card">
      <div class="wish-header">
        <div class="wish-emoji-wrap">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
        </div>
        <div class="wish-meta">
          <p class="wish-name">{{ wish.name }}</p>
          <span class="priority-badge" :class="wish.priority">{{ priorityLabel(wish.priority) }}</span>
        </div>
      </div>

      <div v-if="wish.description" class="wish-desc">{{ wish.description }}</div>

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
          <span v-else-if="daysLineValue !== null" class="progress-hint hint-days">
            {{ t('wishes.timeUnitDays', { days: daysLineValue }) }}
          </span>
          <span v-else class="progress-hint hint-placeholder">
            {{ t('wishes.timeUnitPlaceholder') }}
          </span>
        </div>
      </div>
      <div v-else class="progress-pending">{{ t('wishes.waitingGoal') }}</div>

      <button
        v-if="wish.status === 'active' && wish.progress !== null && wish.progress >= 1"
        class="btn-redeem"
        :disabled="actioning"
        @click="redeem"
      >
        {{ t('wishes.redeemBtn') }}
      </button>
      <span v-else-if="wish.status === 'redemption_requested'" class="status-line">{{ t('wishes.waitingRedemption') }}</span>
      <span v-else-if="wish.status === 'pending_review'" class="status-line">{{ t('wishes.waitingReview') }}</span>
      <div v-else-if="wish.status === 'realized'" class="realized-section">
        <p v-if="wish.fulfilled_at" class="fulfilled-date">
          {{ t('wishes.fulfilledAt', { date: parseApiDate(wish.fulfilled_at).toLocaleDateString(locale, { year: 'numeric', month: '2-digit', day: '2-digit' }) }) }}
        </p>
        <router-link v-if="wish.realized_asset_id" :to="{ name: 'ChildAssetDetail', params: { id: wish.realized_asset_id } }" class="link-asset">
          {{ t('wishes.viewAsset') }}
        </router-link>
        <span v-else class="status-line">{{ t('wishes.realized') }}</span>
      </div>
      <span v-else-if="wish.status === 'rejected'" class="status-line">{{ t('wishes.rejected') }}</span>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePageLoading } from '@/composables/usePageLoading'
import ChildWishDetailSkeleton from '@/components/skeletons/ChildWishDetailSkeleton.vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import {
  listChildWishes, getChildWishStats, requestRedemption,
  type ChildWish, type ChildWishStats,
} from '@/api/childWishes'
import { getCoinLedger, type CoinTransaction } from '@/api/coins'
import { daysEstimate } from '@numina/math'
import { parseApiDate } from '@/utils/format'
import PageHeader from '@/components/common/PageHeader.vue'
import ChildInlineError from '@/components/ChildInlineError.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const allWishes = ref<ChildWish[]>([])
const stats = ref<ChildWishStats | null>(null)
const ledger = ref<CoinTransaction[]>([])
const loading = ref(true)
const actioning = ref(false)
const inlineError = ref({ visible: false, message: '' })

const wishId = computed(() => String(route.params.id))

const wish = computed<ChildWish | null>(() => {
  return allWishes.value.find(w => w.id === wishId.value) ?? null
})

const daysLineValue = computed<number | null>(() => {
  if (!stats.value || !wish.value) return null
  const sim = stats.value.priority_simulation.find(s => s.wish_id === wishId.value)
  if (!sim) return null
  return daysEstimate(stats.value.balance, sim, ledger.value)
})

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
  try {
    const [list, s, l] = await Promise.all([listChildWishes(), getChildWishStats(), getCoinLedger()])
    allWishes.value = [
      ...list.active, ...list.pending_review, ...list.redemption_requested,
      ...list.realized, ...list.rejected,
    ]
    stats.value = s
    ledger.value = l
  } finally {
    loading.value = false
  }
}

async function redeem() {
  if (!wish.value) return
  actioning.value = true
  try {
    await requestRedemption(wish.value.id)
    await load()
  } catch {
    inlineError.value = { visible: true, message: t('toast.submitFailed') }
  } finally {
    actioning.value = false
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
.wish-detail-page {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md);
}

.loading {
  text-align: center;
  padding: 40px 0;
  color: var(--color-muted-soft);
  font-family: Inter, sans-serif;
  font-size: 15px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}
.empty-icon { font-size: 56px; margin: 0 0 12px; }
.empty-text {
  font-family: Inter, sans-serif;
  font-size: 16px;
  color: var(--color-muted-soft);
  margin: 0 0 20px;
}
.btn-back {
  background: var(--color-brand-peach);
  color: var(--color-ink);
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 28px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.wish-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  border: 1px solid var(--color-hairline);
  border-left: 4px solid var(--color-brand-ochre);
  margin-top: var(--space-md);
}

.wish-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.wish-emoji-wrap {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  background: var(--color-surface-card);
  display: flex;
  align-items: center;
  justify-content: center;
}
.wish-emoji { font-size: 30px; }
.wish-meta { flex: 1; min-width: 0; }
.wish-name {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 6px;
}

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

.wish-desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  margin: 0 0 16px;
  line-height: 1.5;
}

.progress-section { margin-bottom: 16px; }
.progress-track {
  position: relative;
  height: 14px;
  background: var(--color-surface-strong);
  border-radius: 7px;
  overflow: visible;
  margin-bottom: 8px;
}
.progress-fill {
  position: absolute;
  top: 0; left: 0;
  height: 100%;
  border-radius: 7px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  max-width: 100%;
}
.progress-fill.low  { background: var(--color-brand-lavender); }
.progress-fill.half { background: var(--color-brand-peach); }
.progress-fill.full { background: var(--color-brand-ochre); }
.progress-star {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  z-index: 1;
  pointer-events: none;
  opacity: 0.6;
}
.progress-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
.hint-full        { color: var(--color-brand-ochre); font-weight: 600; }
.hint-days        { color: var(--color-brand-mint); font-weight: 500; }
.hint-placeholder { color: var(--color-muted-soft); }
.progress-pending {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted-soft);
  margin-bottom: 12px;
}

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
}
.btn-redeem:disabled { opacity: 0.4; cursor: not-allowed; }

.realized-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.fulfilled-date {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  margin: 0;
}

.link-asset {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  text-decoration: none;
}
.link-asset:active { opacity: 0.7; }

.status-line {
  display: block;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  text-align: center;
  margin-top: 8px;
}
</style>
