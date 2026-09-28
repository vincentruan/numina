<template>
  <div class="level-badge">
    <span class="level-emoji">{{ emoji }}</span>
    <span class="level-name">{{ name }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  emoji: string
  name: string
}>()
</script>

<style scoped>
.level-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--color-surface-card);
  border-radius: 16px;
  border: 1px solid var(--color-hairline);
}

.level-emoji {
  font-size: 16px;
}

.level-name {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}
</style>
