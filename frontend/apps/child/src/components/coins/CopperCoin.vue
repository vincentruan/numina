<template>
  <svg :width="size" :height="size" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="copper-grad" cx="35%" cy="30%">
        <stop offset="0%" stop-color="#E8A060" />
        <stop offset="50%" stop-color="#CD7F32" />
        <stop offset="100%" stop-color="#8B4513" />
      </radialGradient>
    </defs>
    <!-- 硬币主体 -->
    <ellipse cx="20" cy="22" rx="17" ry="15" fill="#8B4513" opacity="0.4" />
    <circle cx="20" cy="19" r="17" fill="url(#copper-grad)" />
    <!-- 边缘高光 -->
    <circle cx="20" cy="19" r="17" fill="none" stroke="#E8A060" stroke-width="1" opacity="0.6" />
    <!-- 五角星 -->
    <text x="20" y="25" text-anchor="middle" font-size="14" fill="#FFF8E7" opacity="0.9">★</text>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), {
  size: 24,
})
</script>
