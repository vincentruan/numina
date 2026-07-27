<template>
  <div class="day-detail-page">
    <PageHeader :title="pageTitle" :show-back="true" />

    <div v-if="loading" class="hint">{{ t('baby.dayDetail.loading') }}</div>

    <template v-else-if="detail">
      <!-- Chores -->
      <section v-if="detail.chores.length > 0" class="section">
        <p class="section-title">{{ t('baby.dayDetail.section.chores') }}</p>
        <div class="card-list">
          <div v-for="c in detail.chores" :key="c.id" class="event-card chore-card">
            <span class="event-emoji">{{ c.chore_emoji || '✅' }}</span>
            <div class="event-info">
              <p class="event-name">{{ c.chore_name }}</p>
              <p class="event-sub">
                +{{ c.coin_reward + c.streak_bonus }} ⭐
                <span v-if="c.streak_bonus > 0" class="streak-badge">{{ t('baby.dayDetail.streakBadge', { bonus: c.streak_bonus }) }}</span>
              </p>
            </div>
            <span class="status-tag" :class="c.status === 'approved' ? 'approved' : 'pending'">
              {{ c.status === 'approved' ? t('baby.dayDetail.status.approved') : t('baby.dayDetail.status.pending') }}
            </span>
          </div>
        </div>
      </section>

      <!-- Wishes -->
      <section v-if="detail.wishes.length > 0" class="section">
        <p class="section-title">{{ t('baby.dayDetail.section.wishes') }}</p>
        <div class="card-list">
          <div v-for="w in detail.wishes" :key="w.id" class="event-card wish-card">
            <span class="event-emoji">{{ w.emoji || '🎁' }}</span>
            <div class="event-info">
              <p class="event-name">{{ w.name }}</p>
              <p v-if="w.star_coin_cost" class="event-sub">{{ t('baby.dayDetail.wishCost', { cost: w.star_coin_cost }) }}</p>
            </div>
            <span class="status-tag realized">{{ t('baby.dayDetail.status.realized') }}</span>
          </div>
        </div>
      </section>

      <!-- Milestones -->
      <section v-if="detail.milestones.length > 0" class="section">
        <p class="section-title">{{ t('baby.dayDetail.section.milestones') }}</p>
        <div class="card-list">
          <div v-for="m in detail.milestones" :key="m.id" class="event-card milestone-card">
            <span class="event-emoji">{{ milestoneEmoji(m.milestone_type) }}</span>
            <div class="event-info">
              <p class="event-name">{{ milestoneLabel(m.milestone_type) }}</p>
            </div>
            <span class="status-tag milestone">{{ t('baby.dayDetail.status.milestone') }}</span>
          </div>
        </div>
      </section>

      <!-- Empty -->
      <EmptyState
        v-if="detail.chores.length === 0 && detail.wishes.length === 0 && detail.milestones.length === 0"
        :description="t('baby.dayDetail.emptyState')"
        image-size="80"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { getChildDayDetail, getFamilyChildDayDetail, type CalendarDayDetail } from '@/api/calendar'

const { t } = useI18n()

const route = useRoute()
const date = route.query.date as string
const childId = route.query.child_id as string | undefined

const detail = ref<CalendarDayDetail | null>(null)
const loading = ref(true)

const isParentView = computed(() => !!childId)

const pageTitle = computed(() => {
  if (!date) return t('baby.dayDetail.pageTitle')
  const d = new Date(date + 'T00:00:00')
  return t('baby.dayDetail.dateTitle', { month: d.getMonth() + 1, day: d.getDate() })
})

function milestoneLabel(type: string): string {
  const key = `milestone.${type.replace(/_/g, '')}`
  return t(key)
}

const MILESTONE_EMOJI: Record<string, string> = {
  first_chore: '🌱',
  first_wish_realized: '🎉',
  coins_50: '💰',
  coins_200: '💎',
  streak_7: '🔥',
  streak_14: '⚡',
  streak_30: '🏆',
}

function milestoneEmoji(type: string): string {
  return MILESTONE_EMOJI[type] ?? '🏅'
}

onMounted(async () => {
  if (!date) { loading.value = false; return }
  try {
    if (isParentView.value && childId) {
      detail.value = await getFamilyChildDayDetail(childId, date)
    } else {
      detail.value = await getChildDayDetail(date)
    }
  } catch {
    showFailToast(t('toast.operationFailed'))
    detail.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.day-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}

.hint {
  text-align: center;
  color: var(--text-tertiary);
  padding: 40px 0;
  font-size: 14px;
}

.section {
  margin: 12px 16px 0;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-tertiary);
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--card-bg);
  border-radius: 10px;
  padding: 12px 14px;
}

.event-emoji {
  font-size: 24px;
  flex-shrink: 0;
}

.event-info {
  flex: 1;
  min-width: 0;
}

.event-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-sub {
  font-size: 12px;
  color: var(--color-cost, #f5a623);
  margin: 2px 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.streak-badge {
  background: var(--badge-medium-bg, #fff3e0);
  color: var(--color-cost, #f5a623);
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 11px;
}

.status-tag {
  font-size: 11px;
  border-radius: 4px;
  padding: 2px 8px;
  flex-shrink: 0;
  font-weight: 500;
}
.status-tag.approved  { background: var(--tag-approved-bg, #e8f5e9); color: var(--tag-approved-text, #4caf50); }
.status-tag.pending   { background: var(--badge-medium-bg, #fff8e1); color: var(--color-cost, #f5a623); }
.status-tag.realized  { background: var(--badge-medium-bg, #fff3e0); color: var(--color-cost, #f5a623); }
.status-tag.milestone { background: var(--tag-milestone-bg, #f3e5f5); color: var(--tag-milestone-text, #9c27b0); }
</style>
