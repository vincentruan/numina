import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { showFailToast } from 'vant'
import * as choreApi from '@/api/chores'

export const useChoreStore = defineStore('chore', () => {
  const pendingApprovals = ref<choreApi.ChoreInstance[]>([])

  const pendingCount = computed(() => pendingApprovals.value.length)

  async function fetchPendingApprovals() {
    const items = await choreApi.getPendingApprovals()
    pendingApprovals.value = items
  }

  async function approvePendingChore(id: string) {
    const idx = pendingApprovals.value.findIndex(i => i.id === id)
    if (idx === -1) return
    const removed = pendingApprovals.value.splice(idx, 1)[0]
    try {
      await choreApi.approveChore(id)
    } catch {
      // Re-find position in case concurrent operations shifted the array
      const restoreIdx = pendingApprovals.value.findIndex(i => i.id === removed.id)
      if (restoreIdx === -1) {
        pendingApprovals.value.splice(idx, 0, removed)
      }
      showFailToast('审批失败，请重试')
    }
  }

  async function rejectPendingChore(id: string, returnToRedo: boolean) {
    const idx = pendingApprovals.value.findIndex(i => i.id === id)
    if (idx === -1) return
    const removed = pendingApprovals.value.splice(idx, 1)[0]
    try {
      await choreApi.rejectChore(id, returnToRedo)
    } catch {
      // Re-find position in case concurrent operations shifted the array
      const restoreIdx = pendingApprovals.value.findIndex(i => i.id === removed.id)
      if (restoreIdx === -1) {
        pendingApprovals.value.splice(idx, 0, removed)
      }
      showFailToast('操作失败，请重试')
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
