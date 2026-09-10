<template>
  <div v-if="showStaleness" class="offline-staleness" role="status" aria-live="polite">
    <span class="offline-staleness__icon">&#x26A1;</span>
    <span class="offline-staleness__text">{{ t('pwa.offlineData', { time: staleness }) }}</span>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useOfflineCache } from '@/composables/useOfflineCache'

const { t } = useI18n()
const { showStaleness, staleness } = useOfflineCache()
</script>

<style scoped>
.offline-staleness {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--card-bg, #f5f5ff);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary, #616161);
}

.offline-staleness__icon {
  font-size: 14px;
}
</style>
