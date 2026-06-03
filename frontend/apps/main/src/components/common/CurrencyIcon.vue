<script setup lang="ts">
/**
 * Currency icon for settings.
 *
 * A coin/currency symbol for default currency settings.
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
    aria-label="Currency"
    role="img"
  >
    <!-- Coin circle -->
    <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.5" fill="none" />
    <!-- Inner circle -->
    <circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="1" fill="none" opacity="0.5" />
    <!-- Currency symbol (generic yen/yuan style) -->
    <path d="M8 8L12 12L16 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none" />
    <line x1="12" y1="12" x2="12" y2="16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
    <line x1="9" y1="14" x2="15" y2="14" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
  </svg>
</template>

<style scoped>
svg {
  display: block;
}
</style>