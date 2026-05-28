<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="copper-coin">
    <defs>
      <radialGradient id="copper-grad" cx="35%" cy="32%" r="70%">
        <stop class="stop-hi" offset="0%" />
        <stop class="stop-mid" offset="60%" />
        <stop class="stop-lo" offset="100%" />
      </radialGradient>
    </defs>
    <ellipse cx="24" cy="40" rx="16" ry="2" class="coin-shadow" opacity="0.12" />
    <circle cx="24" cy="23" r="20" fill="url(#copper-grad)" />
    <text x="24" y="29.5" text-anchor="middle" font-size="20" font-weight="900" fill="#FFE9D1" opacity="0.85">★</text>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 24 })
</script>

<style scoped>
.copper-coin .stop-hi  { stop-color: var(--color-coin-copper-hi); }
.copper-coin .stop-mid { stop-color: var(--color-coin-copper-mid); }
.copper-coin .stop-lo  { stop-color: var(--color-coin-copper-lo); }
.copper-coin .coin-shadow { fill: var(--color-coin-copper-lo); }
</style>
