import { ref, computed } from 'vue'
import { searchThreads, deleteThread, updateThread } from '@/api/ai-chat'
import type { ThreadSession, DateGroup, DateGroupLabel } from '@/types/ai-chat/session'

const PAGE_SIZE = 20

export function useThreadList() {
  const sessions = ref<ThreadSession[]>([])
  const isLoading = ref(false)
  const hasMore = ref(true)
  let offset = 0

  function getDateLabel(date: Date): DateGroupLabel {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today.getTime() - 86400000)

    if (date >= today) return 'today'
    if (date >= yesterday) return 'yesterday'
    return 'earlier'
  }

  const dateGroups = computed<DateGroup[]>(() => {
    const pinned = sessions.value.filter(s => s.is_pinned)
    const unpinned = sessions.value.filter(s => !s.is_pinned)

    const groups: DateGroup[] = []
    if (pinned.length > 0) {
      groups.push({ label: 'pinned', displayName: '已置顶', sessions: pinned })
    }

    const today: ThreadSession[] = []
    const yesterday: ThreadSession[] = []
    const earlier: ThreadSession[] = []

    for (const s of unpinned) {
      const label = getDateLabel(new Date(s.updated_at))
      if (label === 'today') today.push(s)
      else if (label === 'yesterday') yesterday.push(s)
      else earlier.push(s)
    }

    if (today.length > 0) groups.push({ label: 'today', displayName: '今天', sessions: today })
    if (yesterday.length > 0) groups.push({ label: 'yesterday', displayName: '昨天', sessions: yesterday })
    if (earlier.length > 0) groups.push({ label: 'earlier', displayName: '更早', sessions: earlier })

    return groups
  })

  async function loadMore() {
    if (isLoading.value || !hasMore.value) return
    isLoading.value = true
    try {
      const res = await searchThreads({ limit: PAGE_SIZE, offset })
      sessions.value = [...sessions.value, ...res.items]
      offset += res.items.length
      hasMore.value = offset < res.total
    } finally {
      isLoading.value = false
    }
  }

  async function refresh() {
    sessions.value = []
    offset = 0
    hasMore.value = true
    await loadMore()
  }

  async function deleteSession(id: string) {
    await deleteThread(id)
    sessions.value = sessions.value.filter(s => s.thread_id !== id)
  }

  async function renameSession(id: string, title: string) {
    const updated = await updateThread(id, { title })
    const idx = sessions.value.findIndex(s => s.thread_id === id)
    if (idx !== -1) {
      sessions.value[idx] = { ...sessions.value[idx], ...updated }
    }
  }

  async function togglePin(id: string) {
    const session = sessions.value.find(s => s.thread_id === id)
    if (!session) return
    const updated = await updateThread(id, { is_pinned: !session.is_pinned })
    const idx = sessions.value.findIndex(s => s.thread_id === id)
    if (idx !== -1) {
      sessions.value[idx] = { ...sessions.value[idx], ...updated }
    }
  }

  return {
    sessions, isLoading, hasMore, dateGroups,
    loadMore, refresh, deleteSession, renameSession, togglePin,
  }
}
