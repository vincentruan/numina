<script setup lang="ts">
/**
 * Butler/Assistant icon for AI settings.
 *
 * A service bell icon representing the "管家" (butler/housekeeper) concept
 * for the AI assistant settings entry.
 */
withDefaults(
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
    aria-label="Assistant"
    role="img"
  >
    <!-- Service bell body -->
    <path
      d="M12 4C8 4 5 7 5 11V14H19V11C19 7 16 4 12 4Z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linejoin="round"
    />
    <!-- Bell top button -->
    <circle cx="12" cy="4" r="1.5" fill="currentColor" />
    <!-- Bell base plate -->
    <rect x="3" y="14" width="18" height="3" rx="1" fill="none" stroke="currentColor" stroke-width="1.5" />
    <!-- Sound waves (assistant ready to help) -->
    <path d="M20 8C21.5 8 22.5 9 22.5 10.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.6" />
    <path d="M21.5 6C23.5 6.5 24.5 8 24.5 10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.4" />
  </svg>
</template>

<style scoped>
svg {
  display: inline-flex;
  vertical-align: middle;
}
</style>