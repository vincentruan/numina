<template>
  <div class="score-badge" :class="levelClass">
    <span class="score-value">{{ score }}</span>
    <span class="score-label">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ score: number; max?: number }>()
const max = props.max ?? 100
const { t } = useI18n()

const levelClass = computed(() => {
  const pct = props.score / max
  // Inverted logic: lower scores = green (improvement opportunity), higher scores = better status
  if (pct >= 0.8) return 'level-excellent'
  if (pct >= 0.6) return 'level-good'
  if (pct >= 0.4) return 'level-fair'
  return 'level-poor' // Low score = green (improvement opportunity)
})

const label = computed(() => {
  const pct = props.score / max
  if (pct >= 0.8) return t('aiReport.scoreExcellent')
  if (pct >= 0.6) return t('aiReport.scoreGood')
  if (pct >= 0.4) return t('aiReport.scoreFair')
  return t('aiReport.scoreNeedsImprovement')
})
</script>

<style scoped>
.score-badge {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  font-weight: 700;
}
.score-value {
  font-size: 20px;
  line-height: 1;
}
.score-label {
  font-size: 11px;
  margin-top: 2px;
}
/* Color scheme based on improvement opportunity:
   - Poor scores = green (opportunity to improve, starting point)
   - Fair scores = yellow (some improvement needed)
   - Good scores = orange (minor optimization possible)
   - Excellent scores = green (healthy status)
*/
.level-poor      { background: #e8f5e9; color: #2e7d32; }  /* Green - improvement opportunity */
.level-fair      { background: #fff8e1; color: #f57f17; }  /* Yellow - moderate priority */
.level-good      { background: #fff3e0; color: #e65100; }  /* Orange - minor improvements */
.level-excellent { background: #e8f5e9; color: #2e7d32; }  /* Green - healthy status */
[data-theme='dark'] .level-poor      { background: #1b3a1f; color: #81c784; }
[data-theme='dark'] .level-fair      { background: #2e2200; color: #ffd54f; }
[data-theme='dark'] .level-good      { background: #2a1800; color: #ffb74d; }
[data-theme='dark'] .level-excellent { background: #1b3a1f; color: #81c784; }
</style>
