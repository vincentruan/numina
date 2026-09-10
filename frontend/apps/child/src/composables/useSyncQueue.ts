import { ref, onMounted, onUnmounted } from 'vue'
import { showSuccessToast, showFailToast, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import http from '@/api'
import { useNetwork } from './useNetwork'
import {
  listPending,
  listFailed,
  updateStatus,
  remove,
  type PendingMutation,
} from '@/utils/offlineQueue'

const MAX_RETRIES = 3

export function useSyncQueue() {
  const { t } = useI18n()
  const { isOnline } = useNetwork()

  const pendingCount = ref(0)
  const isSyncing = ref(false)
  const failedItems = ref<PendingMutation[]>([])

  async function refreshPendingCount() {
    const pending = await listPending()
    pendingCount.value = pending.length
    const failed = await listFailed()
    failedItems.value = failed
  }

  async function drain() {
    if (!isOnline.value || isSyncing.value) return
    isSyncing.value = true

    try {
      const pending = await listPending()
      pendingCount.value = pending.length

      for (const mutation of pending) {
        await updateStatus(mutation.key, 'syncing')

        try {
          const config: Record<string, unknown> = {
            method: mutation.method,
            url: mutation.url,
            data: mutation.body,
          }
          if (mutation.tempId) {
            config.headers = { 'X-Idempotency-Key': mutation.idempotencyKey }
          }

          await http(config)
          await remove(mutation.key)
        } catch (error) {
          const status = (error as { response?: { status?: number } })?.response
            ?.status

          if (status === 409) {
            // Conflict — server data changed, discard local mutation
            await remove(mutation.key)
            showToast({
              message: t('pwa.syncConflict'),
              icon: 'warning-o',
            })
          } else if (mutation.retryCount >= MAX_RETRIES) {
            await updateStatus(mutation.key, 'failed')
          } else {
            await updateStatus(
              mutation.key,
              'pending',
              mutation.retryCount + 1,
            )
          }
        }
      }

      await refreshPendingCount()
      if (pendingCount.value === 0 && failedItems.value.length === 0) {
        showSuccessToast(t('pwa.syncComplete'))
      } else if (failedItems.value.length > 0) {
        showFailToast(t('pwa.syncFailedCount', { count: failedItems.value.length }))
      }
    } finally {
      isSyncing.value = false
    }
  }

  async function retryFailed() {
    const failed = [...failedItems.value]
    for (const item of failed) {
      await updateStatus(item.key, 'pending', 0)
    }
    failedItems.value = []
    await drain()
  }

  async function discardFailed() {
    for (const item of failedItems.value) {
      await remove(item.key)
    }
    failedItems.value = []
    pendingCount.value = 0
  }

  function handleOnline() {
    drain()
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'visible' && isOnline.value) {
      drain()
    }
  }

  onMounted(() => {
    refreshPendingCount()
    window.addEventListener('online', handleOnline)
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  return {
    pendingCount,
    isSyncing,
    failedItems,
    drain,
    retryFailed,
    discardFailed,
    refreshPendingCount,
  }
}
