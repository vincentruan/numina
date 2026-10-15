<template>
  <div class="practice-result-summary">
    <div class="result-hero">
      <div class="result-emoji">{{ resultEmoji }}</div>
      <div class="result-score">{{ scorePercent }}%</div>
      <div class="result-count">
        {{ t('practice.result.correctOf', { correct: result.correct_count, total: result.total_count }) }}
      </div>
    </div>

    <div class="result-rewards">
      <div v-if="result.xp_earned > 0" class="reward-item">
        <span class="reward-icon">⚡</span>
        <span class="reward-text">+{{ result.xp_earned }} XP</span>
      </div>
      <div v-if="result.coins_earned > 0" class="reward-item">
        <span class="reward-icon">🪙</span>
        <span class="reward-text">+{{ result.coins_earned }}</span>
      </div>
      <div v-if="result.mastery_changed" class="reward-item reward-item--mastery">
        <span class="reward-icon">🌟</span>
        <span class="reward-text">{{ t(`learning.status.${result.new_mastery_level}`) }}</span>
      </div>
    </div>

    <div class="result-actions">
      <button class="btn-secondary" @click="$emit('again')">
        {{ t('practice.result.again') }}
      </button>
      <button class="btn-primary" @click="$emit('back')">
        {{ t('practice.result.backToMap') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PracticeResultResponse } from '@/api/practice'

const props = defineProps<{ result: PracticeResultResponse }>()

defineEmits<{ again: []; back: [] }>()

const { t } = useI18n()

const scorePercent = computed(() => Math.round(props.result.total_score * 100))

const resultEmoji = computed(() => {
  if (props.result.total_score >= 0.8) return '🎉'
  if (props.result.total_score >= 0.5) return '💪'
  return '🌱'
})
</script>

<style scoped>
.practice-result-summary {
  padding: 24px 16px;
  text-align: center;
}

.result-emoji {
  font-size: 56px;
  margin-bottom: 8px;
}

.result-score {
  font-size: 44px;
  font-weight: 700;
  color: var(--color-ink);
}

.result-count {
  margin-top: 4px;
  font-size: 15px;
  color: var(--color-body);
}

.result-rewards {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin: 20px 0;
  flex-wrap: wrap;
}

.reward-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 20px;
  background: var(--color-surface-card);
  font-size: 14px;
  color: var(--color-ink);
}

.reward-item--mastery {
  background: rgba(232, 185, 74, 0.15);
}

.result-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 24px;
}

.btn-primary,
.btn-secondary {
  min-height: 48px;
  border-radius: 14px;
  border: none;
  font-size: 16px;
  font-weight: 600;
}

.btn-primary {
  background: var(--color-primary);
  color: var(--color-canvas);
}

.btn-secondary {
  background: var(--color-surface-card);
  color: var(--color-ink);
  border: 1px solid var(--color-border, #e5e0d5);
}
</style>
