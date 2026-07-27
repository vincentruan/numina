<template>
  <div class="challenge-section">
    <div v-if="loading" class="loading-state">
      <van-loading size="24" />
    </div>
    <div v-else-if="error" class="error-state">
      <p class="error-text">{{ t('toast.loadFailed') }}</p>
      <button class="retry-btn" @click="load">{{ t('common.retry') }}</button>
    </div>
    <div v-else-if="challenges.length === 0" class="empty-state">
      <p class="empty-text">{{ t('challenge.emptyState') }}</p>
    </div>
    <div v-else class="challenge-list">
      <div v-for="ch in challenges" :key="ch.id" class="challenge-card" :class="ch.status">
        <div class="challenge-header">
          <span class="challenge-icon"><van-icon :name="typeIcon(ch.target_type)" size="22" /></span>
          <div class="challenge-info">
            <p class="challenge-type">{{ typeLabel(ch.target_type) }}</p>
            <p v-if="ch.message" class="challenge-message">{{ ch.message }}</p>
          </div>
        </div>
        <div class="challenge-progress">
          <van-progress
            :percentage="progressPercent(ch)"
            :stroke-width="8"
            :show-pivot="false"
            color="var(--color-brand-ochre)"
          />
          <span class="progress-text">{{ ch.current_progress }}/{{ ch.target_value }}</span>
        </div>
        <p v-if="ch.status === 'active'" class="deadline-hint">
          {{ t('challenge.daysLeft', { n: daysLeft(ch.deadline) }) }}
        </p>
        <p v-else-if="ch.status === 'completed'" class="completed-label">
          {{ t('challenge.completed') }}
        </p>
        <p v-else-if="ch.status === 'expired'" class="expired-label">
          {{ t('challenge.expired') }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getActiveChildChallenges } from '@/api/challengeGrant'
import { parseApiDate } from '@/utils/format'
import type { ChildChallenge } from '@/types/challengeGrant'

const { t } = useI18n()

const challenges = ref<ChildChallenge[]>([])
const loading = ref(true)
const error = ref(false)

async function load() {
  loading.value = true
  error.value = false
  try {
    challenges.value = await getActiveChildChallenges()
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function typeIcon(type: ChildChallenge['target_type']): string {
  switch (type) {
    case 'task_count': return 'todo-list-o'
    case 'streak_length': return 'fire-o'
    case 'specific_chore': return 'checked'
    case 'star_earnings': return 'star-o'
    default: return 'aim'
  }
}

function typeLabel(type: ChildChallenge['target_type']): string {
  switch (type) {
    case 'task_count': return t('challenge.taskCount')
    case 'streak_length': return t('challenge.streakLength')
    case 'specific_chore': return t('challenge.specificChore')
    case 'star_earnings': return t('challenge.starEarnings')
    default: return ''
  }
}

function progressPercent(ch: ChildChallenge): number {
  return Math.min(100, Math.round((ch.current_progress / ch.target_value) * 100))
}

function daysLeft(deadline: string): number {
  const diff = parseApiDate(deadline).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / (24 * 60 * 60 * 1000)))
}

onMounted(load)

defineExpose({ load })
</script>

<style scoped>
.challenge-section {
  margin-top: var(--space-lg);
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.error-state {
  text-align: center;
  padding: 16px;
}

.error-text {
  color: var(--color-brand-coral);
  font-size: 14px;
  margin: 0 0 8px;
}

.retry-btn {
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
}

.empty-state {
  text-align: center;
  padding: 16px;
  color: var(--color-muted-soft);
  font-size: 14px;
}

.empty-text {
  margin: 0;
}

.challenge-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.challenge-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--color-hairline);
}

.challenge-card.completed {
  background: var(--color-brand-mint);
}

.challenge-card.expired {
  opacity: 0.6;
}

.challenge-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.challenge-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  color: var(--color-brand-ochre);
}

.challenge-info {
  flex: 1;
}

.challenge-type {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.challenge-message {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
  margin: 4px 0 0;
}

.challenge-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.challenge-progress .van-progress {
  flex: 1;
}

.progress-text {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  white-space: nowrap;
}

.deadline-hint {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
  margin: 8px 0 0;
}

.completed-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 8px 0 0;
}

.expired-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  margin: 8px 0 0;
}
</style>