<template>
  <div class="xp-progress">
    <div class="xp-header">
      <span class="xp-level">{{ emoji }} {{ levelName }}</span>
      <span class="xp-count">{{ currentXp }} XP</span>
    </div>
    <van-progress
      :percentage="percentage"
      :show-pivot="false"
      stroke-width="8"
      color="var(--color-primary)"
      track-color="var(--color-hairline)"
    />
    <p v-if="xpToNext !== null" class="xp-hint">
      {{ t('learning.stats.xpProgress', { xp: xpToNext }) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  currentXp: number
  level: number
  levelName: string
  emoji: string
  nextThreshold: number | null
}>()

const { t } = useI18n()

const percentage = computed(() => {
  if (!props.nextThreshold) return 100
  const currentLevelStart = props.currentXp > 0 ? Math.max(0, props.currentXp - 50) : 0
  const range = props.nextThreshold - currentLevelStart
  if (range <= 0) return 100
  return Math.min(100, Math.round(((props.currentXp - currentLevelStart) / range) * 100))
})

const xpToNext = computed(() => {
  if (!props.nextThreshold) return null
  return Math.max(0, props.nextThreshold - props.currentXp)
})
</script>

<style scoped>
.xp-progress {
  padding: 12px 0;
}

.xp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.xp-level {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
}

.xp-count {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
}

.xp-hint {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin: 6px 0 0;
}
</style>
