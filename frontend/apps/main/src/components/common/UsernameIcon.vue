<script setup lang="ts">
/**
 * Username/ID card icon for settings.
 *
 * An ID card with user silhouette for username settings entry.
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
    aria-label="Username"
    role="img"
  >
    <!-- Card outline -->
    <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.5" fill="none" />
    <!-- Small user avatar on card -->
    <circle cx="8" cy="10" r="2" stroke="currentColor" stroke-width="1.2" fill="none" />
    <path d="M5 15V14.5C5 13 6.5 12 8 12C9.5 12 11 13 11 14.5V15" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" fill="none" />
    <!-- Username lines -->
    <line x1="13" y1="10" x2="19" y2="10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.7" />
    <line x1="13" y1="13" x2="17" y2="13" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.5" />
  </svg>
</template>

<style scoped>
svg {
  display: inline-flex;
  vertical-align: middle;
}
</style>