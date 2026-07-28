<template>
  <van-cell-group inset class="report-section">
    <div class="section-header">
      <van-icon :name="icon" class="section-icon" />
      <span class="section-title">{{ title }}</span>
    </div>
    <div class="section-body">
      <slot />
    </div>
  </van-cell-group>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  icon: string
}>()
</script>

<style scoped>
.report-section {
  margin-bottom: 12px;
  font-family: Inter, sans-serif;
}

.section-header {
  display: flex;
  align-items: center;
  padding: 12px 16px 4px;
  gap: 6px;
}

.section-icon {
  font-size: 18px;
  color: var(--van-primary-color);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.section-body {
  padding: 4px 16px 12px;
}
</style>
