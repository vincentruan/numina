<template>
  <div class="score-badge" :class="levelClass">
    <span class="score-value">{{ score }}</span>
    <span class="score-label">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ score: number; max?: number }>()
const max = props.max ?? 100

const levelClass = computed(() => {
  const pct = props.score / max
  if (pct >= 0.8) return 'level-excellent'
  if (pct >= 0.6) return 'level-good'
  if (pct >= 0.4) return 'level-fair'
  return 'level-poor'
})

const label = computed(() => {
  const pct = props.score / max
  if (pct >= 0.8) return '优秀'
  if (pct >= 0.6) return '良好'
  if (pct >= 0.4) return '一般'
  return '待改善'
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
.level-excellent { background: #e8f5e9; color: #2e7d32; }
.level-good      { background: #e3f2fd; color: #1565c0; }
.level-fair      { background: #fff8e1; color: #f57f17; }
.level-poor      { background: #fce4ec; color: #c62828; }
[data-theme='dark'] .level-excellent { background: #1b3a1f; color: #81c784; }
[data-theme='dark'] .level-good      { background: #0d2137; color: #64b5f6; }
[data-theme='dark'] .level-fair      { background: #2e2200; color: #ffd54f; }
[data-theme='dark'] .level-poor      { background: #3b0a14; color: #ef9a9a; }
</style>
