<template>
  <div v-if="pendingCount > 0 || failedItems.length > 0" class="sync-status">
    <div v-if="isSyncing" class="sync-status__syncing">
      <van-loading size="16" />
      <span>{{ t('pwa.syncing', { count: pendingCount }) }}</span>
    </div>
    <div v-else-if="pendingCount > 0" class="sync-status__pending">
      <span class="sync-status__dot sync-status__dot--pending" />
      <span>{{ t('pwa.pendingSync', { count: pendingCount }) }}</span>
    </div>
    <div v-if="failedItems.length > 0" class="sync-status__failed">
      <span class="sync-status__dot sync-status__dot--failed" />
      <span>{{ t('pwa.syncFailedCount', { count: failedItems.length }) }}</span>
      <van-button size="mini" type="primary" plain @click="retryFailed">{{ t('pwa.retry') }}</van-button>
      <van-button size="mini" plain @click="discardFailed">{{ t('pwa.discard') }}</van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSyncQueue } from '@/composables/useSyncQueue'

const { t } = useI18n()
const { pendingCount, isSyncing, failedItems, retryFailed, discardFailed } = useSyncQueue()
</script>

<style scoped>
.sync-status {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--color-body, #3d3d3d);
}

.sync-status__syncing,
.sync-status__pending,
.sync-status__failed {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sync-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sync-status__dot--pending {
  background: #faad14;
}

.sync-status__dot--failed {
  background: #ff4d4f;
}
</style>
