import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { showFailToast } from 'vant'
import i18n from '@/i18n'
import * as choreApi from '@/api/chores'

export const useChoreStore = defineStore('chore', () => {
  const pendingApprovals = ref<choreApi.PendingApprovalInstance[]>([])
  const { t } = i18n.global

  const pendingCount = computed(() => pendingApprovals.value.length)

  async function fetchPendingApprovals() {
    try {
      const items = await choreApi.getPendingApprovals()
      pendingApprovals.value = items
    } catch {
      showFailToast(t('choreStore.loadFailed'))
    }
  }

  async function approvePendingChore(id: string) {
    const idx = pendingApprovals.value.findIndex(i => i.id === id)
    if (idx === -1) return
    const removed = pendingApprovals.value.splice(idx, 1)[0]
    try {
      await choreApi.approveChore(id)
    } catch {
      // Resync from server to avoid stale state after concurrent fetch
      try {
        await fetchPendingApprovals()
      } catch {
        // If resync also fails, restore the item so the user can retry
        if (!pendingApprovals.value.find(i => i.id === removed.id)) {
          pendingApprovals.value.splice(idx, 0, removed)
        }
      }
      showFailToast(t('choreStore.approveFailed'))
    }
  }

  async function rejectPendingChore(id: string, returnToRedo: boolean) {
    const idx = pendingApprovals.value.findIndex(i => i.id === id)
    if (idx === -1) return
    const removed = pendingApprovals.value.splice(idx, 1)[0]
    try {
      await choreApi.rejectChore(id, returnToRedo)
    } catch {
      // Resync from server to avoid stale state after concurrent fetch
      try {
        await fetchPendingApprovals()
      } catch {
        // If resync also fails, restore the item so the user can retry
        if (!pendingApprovals.value.find(i => i.id === removed.id)) {
          pendingApprovals.value.splice(idx, 0, removed)
        }
      }
      showFailToast(t('choreStore.operationFailed'))
    }
  }

  return {
    pendingApprovals,
    pendingCount,
    fetchPendingApprovals,
    approvePendingChore,
    rejectPendingChore,
  }
})
