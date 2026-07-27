<script setup lang="ts">
/**
 * User icon for settings.
 *
 * A person silhouette icon for user-related settings entries.
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
    aria-label="User"
    role="img"
  >
    <!-- Head -->
    <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="1.5" fill="none" />
    <!-- Body -->
    <path
      d="M4 21V19C4 16.5 7 14 12 14C17 14 20 16.5 20 19V21"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      fill="none"
    />
  </svg>
</template>

<style scoped>
svg {
  display: inline-flex;
  vertical-align: middle;
}
</style>