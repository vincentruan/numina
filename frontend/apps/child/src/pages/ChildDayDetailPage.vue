<template>
  <div class="day-detail-page">
    <PageHeader :title="pageTitle" :show-back="true" />

    <div v-if="loading" class="hint">{{ t('common.loading') }}</div>

    <template v-else-if="detail">
      <!-- Chores -->
      <section v-if="detail.chores.length > 0" class="section">
        <p class="section-title">{{ t('dayDetail.sectionChores') }}</p>
        <div class="card-list">
          <div v-for="c in detail.chores" :key="c.id" class="event-card chore-card">
            <span class="event-emoji">{{ c.chore_emoji || '✅' }}</span>
            <div class="event-info">
              <p class="event-name">{{ c.chore_name }}</p>
              <p class="event-sub">
                +{{ c.coin_reward + c.streak_bonus }} ⭐
                <span v-if="c.streak_bonus > 0" class="streak-badge">{{ t('dayDetail.streakBonus', { bonus: c.streak_bonus }) }}</span>
              </p>
            </div>
            <span class="status-tag" :class="c.status === 'approved' ? 'approved' : 'pending'">
              {{ c.status === 'approved' ? t('dayDetail.statusApproved') : t('dayDetail.statusPending') }}
            </span>
          </div>
        </div>
      </section>

      <!-- Wishes -->
      <section v-if="detail.wishes.length > 0" class="section">
        <p class="section-title">{{ t('dayDetail.sectionWishes') }}</p>
        <div class="card-list">
          <div v-for="w in detail.wishes" :key="w.id" class="event-card wish-card">
            <span class="event-emoji">{{ w.emoji || '🎁' }}</span>
            <div class="event-info">
              <p class="event-name">{{ w.name }}</p>
              <p v-if="w.star_coin_cost" class="event-sub">{{ t('dayDetail.wishCost', { cost: w.star_coin_cost }) }}</p>
            </div>
            <span class="status-tag realized">{{ t('dayDetail.statusRealized') }}</span>
          </div>
        </div>
      </section>

      <!-- Milestones -->
      <section v-if="detail.milestones.length > 0" class="section">
        <p class="section-title">{{ t('dayDetail.sectionMilestones') }}</p>
        <div class="card-list">
          <div v-for="m in detail.milestones" :key="m.id" class="event-card milestone-card">
            <span class="event-emoji">{{ milestoneEmoji(m.milestone_type) }}</span>
            <div class="event-info">
              <p class="event-name">{{ milestoneLabel(m.milestone_type) }}</p>
            </div>
            <span class="status-tag milestone">{{ t('dayDetail.statusMilestone') }}</span>
          </div>
        </div>
      </section>

      <!-- Empty -->
      <van-empty
        v-if="detail.chores.length === 0 && detail.wishes.length === 0 && detail.milestones.length === 0"
        :description="t('dayDetail.empty')"
        image-size="80"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import { getChildDayDetail, getFamilyChildDayDetail, type CalendarDayDetail } from '@/api/calendar'

const { t } = useI18n()
const route = useRoute()
const date = route.query.date as string
const childId = route.query.child_id as string | undefined

const detail = ref<CalendarDayDetail | null>(null)
const loading = ref(true)

const isParentView = computed(() => !!childId)

const pageTitle = computed(() => {
  if (!date) return t('dayDetail.defaultTitle')
  const d = new Date(date + 'T00:00:00')
  return t('dayDetail.dateTitle', { month: d.getMonth() + 1, day: d.getDate() })
})

const MILESTONE_EMOJI: Record<string, string> = {
  first_chore: '🌱',
  first_wish_realized: '🎉',
  coins_50: '💰',
  coins_200: '💎',
  streak_7: '🔥',
  streak_14: '⚡',
  streak_30: '🏆',
}

function milestoneLabel(type: string): string {
  const key = `milestone.${type}` as Parameters<typeof t>[0]
  const result = t(key)
  return result !== key ? result : type
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
    detail.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.day-detail-page {
  background: #f7f7f7;
  min-height: 100vh;
  padding-bottom: 24px;
}

.hint {
  text-align: center;
  color: #999;
  padding: 40px 0;
  font-size: 14px;
}

.section {
  margin: 12px 16px 0;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #888;
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
  background: #fff;
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
  color: #1a1a1a;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-sub {
  font-size: 12px;
  color: #f5a623;
  margin: 2px 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.streak-badge {
  background: #fff3e0;
  color: #f5a623;
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
.status-tag.approved  { background: #e8f5e9; color: #4caf50; }
.status-tag.pending   { background: #fff8e1; color: #f5a623; }
.status-tag.realized  { background: #fff3e0; color: #f5a623; }
.status-tag.milestone { background: #f3e5f5; color: #9c27b0; }
</style>
