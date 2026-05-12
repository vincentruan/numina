<template>
  <div class="spending-leaks-page">
    <PageHeader :title="t('spendingLeaks.title')" />
    <SpendingLeaksCard />
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import SpendingLeaksCard from '@/components/ai/SpendingLeaksCard.vue'

const { t } = useI18n()
</script>

<style scoped>
.spending-leaks-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
</style>
