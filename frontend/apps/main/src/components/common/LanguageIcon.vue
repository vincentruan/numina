<script setup lang="ts">
/**
 * Language icon for settings.
 *
 * A globe icon representing language/locale settings.
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
    aria-label="Language"
    role="img"
  >
    <!-- Globe outline -->
    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" fill="none" />
    <!-- Latitude lines -->
    <ellipse cx="12" cy="12" rx="9" ry="4" stroke="currentColor" stroke-width="1.2" fill="none" opacity="0.7" />
    <line x1="12" y1="3" x2="12" y2="21" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    <!-- Longitude curved lines -->
    <path d="M12 3C8 3 5 7 5 12C5 17 8 21 12 21" stroke="currentColor" stroke-width="1" fill="none" opacity="0.5" />
    <path d="M12 3C16 3 19 7 19 12C19 17 16 21 12 21" stroke="currentColor" stroke-width="1" fill="none" opacity="0.5" />
  </svg>
</template>

<style scoped>
svg {
  display: block;
}
</style>