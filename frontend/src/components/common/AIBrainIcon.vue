<template>
  <svg class="ai-brain-icon" :class="{ active: active }" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <defs>
      <linearGradient id="ai-brain-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#00d2ff" />
        <stop offset="50%" stop-color="#3a7bd5" />
        <stop offset="100%" stop-color="#8a2387" />
      </linearGradient>
      <linearGradient id="ai-brain-gradient-dark" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#00E5FF" />
        <stop offset="50%" stop-color="#2979FF" />
        <stop offset="100%" stop-color="#D500F9" />
      </linearGradient>
    </defs>
    <g class="brain-elements" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <!-- Brain outline (Tech style with circuits) -->
      <path d="M12 3.5C8 3.5 5 6 4.5 9.5C3.5 10.5 3 12 4 13.5C3.5 15 4 17.5 6 18C7 20 9 21 12 21" />
      <path d="M12 3.5C16 3.5 19 6 19.5 9.5C20.5 10.5 21 12 20 13.5C20.5 15 20 17.5 18 18C17 20 15 21 12 21" />
      
      <!-- Nodes -->
      <circle class="brain-node" cx="12" cy="6" r="1.5" fill="currentColor" stroke="none" />
      <circle class="brain-node" cx="7" cy="16" r="1" fill="currentColor" stroke="none" />
      <circle class="brain-node" cx="17" cy="16" r="1" fill="currentColor" stroke="none" />
      
      <!-- Circuit Links -->
      <path d="M12 7.5L12 9.5" stroke-dasharray="2 2" stroke-width="1.2" />
      <path d="M8 15L10 13.5" stroke-dasharray="2 2" stroke-width="1.2" />
      <path d="M16 15L14 13.5" stroke-dasharray="2 2" stroke-width="1.2" />

      <!-- "AI" text with tech font styling -->
      <!-- 'A' -->
      <path d="M10 15L11 10.5L12 15 M10.3 13.5L11.7 13.5" stroke-width="1.3" />
      <!-- 'I' -->
      <path d="M14 10.5L14 15" stroke-width="1.3" />
    </g>
  </svg>
</template>

<script setup lang="ts">
defineProps<{
  active?: boolean
}>()
</script>

<style scoped>
.ai-brain-icon {
  color: var(--van-tabbar-item-text-color, #7d7e80);
  transition: all 0.3s ease;
}
.ai-brain-icon.active {
  color: var(--van-tabbar-item-active-color, #1989fa); /* fallback */
}
.ai-brain-icon.active .brain-elements {
  stroke: url(#ai-brain-gradient);
}
.ai-brain-icon.active .brain-node {
  fill: url(#ai-brain-gradient);
}

@media (prefers-color-scheme: dark) {
  .ai-brain-icon.active .brain-elements {
    stroke: url(#ai-brain-gradient-dark);
  }
  .ai-brain-icon.active .brain-node {
    fill: url(#ai-brain-gradient-dark);
  }
}
</style>
