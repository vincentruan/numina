<template>
  <div
    class="continent-fog"
    :style="{ opacity: fogOpacity }"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  masteryRatio: number
}>()

/**
 * Map mastery ratio to fog opacity (KTD3):
 * 0% mastered → 0.7 (mostly obscured)
 * 1-49% → 0.4 (dimmed)
 * 50-79% → 0.15 (lightly veiled)
 * 80%+ → 0 (fully clear)
 */
function computeFogOpacity(ratio: number): number {
  const clamped = Math.max(0, Math.min(1, ratio))
  if (clamped >= 0.8) return 0
  if (clamped >= 0.5) return 0.15
  if (clamped > 0) return 0.4
  return 0.7
}

const fogOpacity = computed(() => computeFogOpacity(props.masteryRatio))
</script>

<style scoped>
.continent-fog {
  position: absolute;
  inset: 0;
  background: var(--continent-fog-color);
  border-radius: inherit;
  transition: var(--continent-fog-transition);
  z-index: 1;
  pointer-events: none;
}

/* Reduced motion — no fog transition */
@media (prefers-reduced-motion: reduce) {
  .continent-fog {
    transition: none;
  }
}
</style>
