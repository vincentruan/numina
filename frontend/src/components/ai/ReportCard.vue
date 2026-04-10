<template>
  <div class="report-card">
    <div class="card-header">
      <div class="card-title-row">
        <span class="card-icon">{{ icon }}</span>
        <span class="card-title">{{ title }}</span>
      </div>
      <ReportScoreBadge :score="score" :max="5" />
    </div>
    <p class="card-narrative">{{ narrative }}</p>
    <slot />
  </div>
</template>

<script setup lang="ts">
import ReportScoreBadge from './ReportScoreBadge.vue'

defineProps<{
  icon: string
  title: string
  score: number
  narrative: string
}>()
</script>

<style scoped>
.report-card {
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-icon {
  font-size: 20px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-narrative {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}
</style>
