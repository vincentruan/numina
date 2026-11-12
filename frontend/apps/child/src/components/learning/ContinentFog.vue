<template>
  <div
    class="continent-fog"
    :style="{ opacity: fogOpacity }"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { fogOpacityForRatio } from '@/utils/continentFog'

const props = defineProps<{
  masteryRatio: number
}>()

const fogOpacity = computed(() => fogOpacityForRatio(props.masteryRatio))
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
