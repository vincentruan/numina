<template>
  <svg :width="size" :height="size" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="silver-grad" cx="35%" cy="30%">
        <stop offset="0%" stop-color="#E8E8E8" />
        <stop offset="50%" stop-color="#C0C0C0" />
        <stop offset="100%" stop-color="#808080" />
      </radialGradient>
    </defs>
    <!-- 硬币主体 -->
    <ellipse cx="20" cy="22" rx="17" ry="15" fill="#808080" opacity="0.4" />
    <circle cx="20" cy="19" r="17" fill="url(#silver-grad)" />
    <!-- 边缘高光 -->
    <circle cx="20" cy="19" r="17" fill="none" stroke="#E8E8E8" stroke-width="1" opacity="0.6" />
    <!-- 五角星 -->
    <text x="20" y="25" text-anchor="middle" font-size="14" fill="#FFF8E7" opacity="0.9">★</text>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), {
  size: 24,
})
</script>
