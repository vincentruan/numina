<template>
  <div class="practice-result-summary">
    <!-- Discovery statement — primary feedback (R6, R7) -->
    <div class="result-discovery">
      <div class="result-discovery__icon">{{ discoveryEmoji }}</div>
      <p class="result-discovery__text">{{ discoveryText }}</p>
    </div>

    <!-- Score — secondary, reduced visual weight -->
    <div class="result-score-section">
      <div class="result-score">{{ scorePercent }}%</div>
      <div class="result-count">
        {{ t('practice.result.correctOf', { correct: result.correct_count, total: result.total_count }) }}
      </div>
    </div>

    <!-- Rewards — subtle, background signals -->
    <div v-if="hasRewards" class="result-rewards">
      <div v-if="result.xp_earned > 0" class="reward-item">
        <span class="reward-text">+{{ result.xp_earned }} XP</span>
      </div>
      <div v-if="result.coins_earned > 0" class="reward-item">
        <span class="reward-text">+{{ result.coins_earned }}</span>
      </div>
      <div v-if="result.mastery_changed" class="reward-item reward-item--mastery">
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

const discoveryEmoji = computed(() => {
  if (props.result.mastery_changed) return '🌟'
  if (props.result.total_score >= 0.8) return '🎉'
  if (props.result.total_score >= 0.5) return '💪'
  return '🌱'
})

const discoveryText = computed(() => {
  if (props.result.mastery_changed) return t('practice.result.discoveryMastery')
  if (props.result.total_score >= 0.8) return t('practice.result.discoveryHighScore')
  return t('practice.result.discoveryKeepGoing')
})

const hasRewards = computed(() =>
  props.result.xp_earned > 0 || props.result.coins_earned > 0 || props.result.mastery_changed,
)
</script>

<style scoped>
.practice-result-summary {
  padding: 24px 16px;
  text-align: center;
}

/* Discovery — primary feedback, largest visual weight */
.result-discovery {
  margin-bottom: 20px;
}

.result-discovery__icon {
  font-size: 56px;
  margin-bottom: 12px;
}

.result-discovery__text {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.5;
}

/* Score — secondary, muted */
.result-score-section {
  margin-bottom: 16px;
}

.result-score {
  font-size: 28px;
  font-weight: 600;
  color: var(--color-body);
}

.result-count {
  margin-top: 4px;
  font-size: 14px;
  color: var(--color-muted);
}

/* Rewards — subtle, small text */
.result-rewards {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin: 12px 0;
  flex-wrap: wrap;
}

.reward-item {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 10px;
  border-radius: 12px;
  background: var(--color-surface-soft);
  font-size: 12px;
  color: var(--color-muted);
}

.reward-item--mastery {
  background: rgba(var(--color-brand-ochre-rgb), 0.1);
  color: var(--color-body);
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
