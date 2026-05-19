<template>
  <div class="challenge-list">
    <p class="list-title">{{ t('challenge.sectionTitle') }}</p>

    <div v-if="loading" class="loading-state">
      <van-loading size="24" />
    </div>

    <div v-else-if="challenges.length === 0" class="empty-state">
      <p class="empty-text">{{ t('challenge.listEmpty') }}</p>
    </div>

    <div v-else class="challenge-items">
      <div v-for="ch in challenges" :key="ch.id" class="challenge-item" :class="ch.status">
        <div class="item-header">
          <span class="item-icon">{{ typeIcon(ch.target_type) }}</span>
          <div class="item-info">
            <p class="item-child">{{ childName(ch.child_user_id) }}</p>
            <p class="item-type">{{ typeLabel(ch.target_type) }}: {{ ch.target_value }}</p>
          </div>
          <span class="item-status" :class="ch.status">{{ statusLabel(ch.status) }}</span>
        </div>
        <div class="item-progress">
          <van-progress
            :percentage="progressPercent(ch)"
            :stroke-width="6"
            :show-pivot="false"
            color="var(--color-brand-ochre)"
          />
          <span class="progress-num">{{ ch.current_progress }}/{{ ch.target_value }}</span>
        </div>
        <div class="item-footer">
          <span class="item-deadline">{{ formatDate(ch.deadline) }}</span>
          <button
            v-if="ch.status === 'active'"
            class="cancel-btn"
            @click="cancelChallenge(ch)"
          >
            {{ t('common.cancel') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog } from 'vant'
import { listFamilyChallenges, cancelChallenge as apiCancelChallenge, type ChallengeGrant } from '@/api/challengeGrant'
import { listChildren, type ChildResponse } from '@/api/children'

const { t } = useI18n()

const challenges = ref<ChallengeGrant[]>([])
const children = ref<ChildResponse[]>([])
const loading = ref(true)

const childMap = computed(() => new Map(children.value.map(c => [c.id, c.display_name])))

function childName(id: string): string {
  return childMap.value.get(id) || '未知'
}

function typeIcon(type: ChallengeGrant['target_type']): string {
  switch (type) {
    case 'task_count': return '📋'
    case 'streak_length': return '🔥'
    case 'specific_chore': return '✅'
    case 'star_earnings': return '⭐'
    default: return '🎯'
  }
}

function typeLabel(type: ChallengeGrant['target_type']): string {
  switch (type) {
    case 'task_count': return t('challenge.taskCount')
    case 'streak_length': return t('challenge.streakLength')
    case 'specific_chore': return t('challenge.specificChore')
    case 'star_earnings': return t('challenge.starEarnings')
    default: return ''
  }
}

function statusLabel(status: ChallengeGrant['status']): string {
  switch (status) {
    case 'active': return t('challenge.statusActive')
    case 'completed': return t('challenge.statusCompleted')
    case 'expired': return t('challenge.statusExpired')
    case 'cancelled': return t('challenge.statusCancelled')
    default: return ''
  }
}

function progressPercent(ch: ChallengeGrant): number {
  return Math.min(100, Math.round((ch.current_progress / ch.target_value) * 100))
}

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString('zh-CN')
}

async function cancelChallenge(ch: ChallengeGrant) {
  try {
    await showConfirmDialog({
      title: t('challenge.cancelConfirm'),
    })
    await apiCancelChallenge(ch.id)
    showToast(t('challenge.cancelled'))
    await load()
  } catch {
    // cancelled or failed
  }
}

async function load() {
  loading.value = true
  try {
    challenges.value = await listFamilyChallenges()
  } catch {
    // non-blocking
  } finally {
    loading.value = false
  }

  try {
    children.value = await listChildren()
  } catch {
    // non-blocking
  }
}

onMounted(load)

defineExpose({ load })
</script>

<style scoped>
.challenge-list {
  padding: var(--space-md);
}

.list-title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.empty-state {
  text-align: center;
  padding: 16px;
  color: var(--color-muted-soft);
}

.empty-text {
  margin: 0;
}

.challenge-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.challenge-item {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--color-hairline);
}

.challenge-item.completed {
  background: var(--color-brand-mint);
}

.challenge-item.expired,
.challenge-item.cancelled {
  opacity: 0.6;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.item-icon {
  font-size: 24px;
}

.item-info {
  flex: 1;
}

.item-child {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.item-type {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
  margin: 4px 0 0;
}

.item-status {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: var(--color-brand-peach);
  color: var(--color-ink);
}

.item-status.completed {
  background: var(--color-brand-mint);
}

.item-status.expired,
.item-status.cancelled {
  background: var(--color-surface-soft);
  color: var(--color-muted);
}

.item-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-progress .van-progress {
  flex: 1;
}

.progress-num {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  white-space: nowrap;
}

.item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.item-deadline {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
}

.cancel-btn {
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 6px 12px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
  cursor: pointer;
}
</style>