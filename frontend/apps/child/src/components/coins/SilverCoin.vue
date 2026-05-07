<template>
  <svg :width="size" :height="size" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg" class="silver-coin">
    <defs>
      <radialGradient id="silver-grad" cx="35%" cy="30%">
        <stop class="stop-hi" offset="0%" />
        <stop class="stop-mid" offset="50%" />
        <stop class="stop-lo" offset="100%" />
      </radialGradient>
    </defs>
    <ellipse cx="20" cy="22" rx="17" ry="15" class="coin-shadow" opacity="0.4" />
    <circle cx="20" cy="19" r="17" fill="url(#silver-grad)" />
    <circle cx="20" cy="19" r="17" fill="none" class="coin-edge" stroke-width="1" opacity="0.6" />
    <text x="20" y="25" text-anchor="middle" font-size="14" fill="#FFF8E7" opacity="0.9">★</text>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 24 })
</script>

<style scoped>
.silver-coin .stop-hi  { stop-color: var(--color-coin-silver-hi); }
.silver-coin .stop-mid { stop-color: var(--color-coin-silver-mid); }
.silver-coin .stop-lo  { stop-color: var(--color-coin-silver-lo); }
.silver-coin .coin-shadow { fill: var(--color-coin-silver-lo); }
.silver-coin .coin-edge   { stroke: var(--color-coin-silver-hi); }
</style>
