<script setup lang="ts">
/**
 * Theme icon for settings.
 *
 * A sun/moon hybrid icon representing theme mode settings.
 */
const props = withDefaults(
  defineProps<{
    size?: number
  }>(),
  { size: 24 },
)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-label="Theme"
    role="img"
  >
    <!-- Sun rays -->
    <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.5" fill="none" />
    <!-- Rays -->
    <line x1="12" y1="2" x2="12" y2="5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="12" y1="19" x2="12" y2="22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="2" y1="12" x2="5" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="19" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="4.93" y1="4.93" x2="7.17" y2="7.17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="16.83" y1="16.83" x2="19.07" y2="19.07" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="4.93" y1="19.07" x2="7.17" y2="16.83" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="16.83" y1="7.17" x2="19.07" y2="4.93" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
  </svg>
</template>

<style scoped>
svg {
  display: block;
}
</style>