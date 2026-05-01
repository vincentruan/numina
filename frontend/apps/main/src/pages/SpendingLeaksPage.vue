<template>
  <div class="spending-leaks-page">
    <PageHeader title="资金泄漏检测" />
    <SpendingLeaksCard />
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'
import SpendingLeaksCard from '@/components/ai/SpendingLeaksCard.vue'
</script>

<style scoped>
.spending-leaks-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
</style>
