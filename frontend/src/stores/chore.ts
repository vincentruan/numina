import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { showFailToast } from 'vant'
import * as choreApi from '@/api/chores'

export interface ChoreInstanceWithChild extends choreApi.ChoreInstance {
  child_user_id: string | null
  child_display_name: string | null
  child_avatar_color: string | null
}

export const useChoreStore = defineStore('chore', () => {
  const pendingApprovals = ref<ChoreInstanceWithChild[]>([])

  const pendingCount = computed(() => pendingApprovals.value.length)

  async function fetchPendingApprovals() {
    const items = await choreApi.getPendingApprovals()
    pendingApprovals.value = items as ChoreInstanceWithChild[]
  }

  async function approvePendingChore(id: string) {
    const idx = pendingApprovals.value.findIndex(i => i.id === id)
    if (idx === -1) return
    const removed = pendingApprovals.value.splice(idx, 1)[0]
    try {
      await choreApi.approveChore(id)
    } catch {
      pendingApprovals.value.splice(idx, 0, removed)
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
      pendingApprovals.value.splice(idx, 0, removed)
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
