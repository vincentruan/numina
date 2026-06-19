import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ThreadSession } from '@/types/ai-chat/session'

export const useChatSessionStore = defineStore('chatSession', () => {
  const activeThreadId = ref<string | null>(null)
  const sessions = ref<ThreadSession[]>([])

  const isWelcomeMode = computed(() => activeThreadId.value === null)
  const activeSession = computed(() =>
    sessions.value.find(s => s.thread_id === activeThreadId.value) ?? null
  )

  function setActiveThread(id: string) {
    if (activeThreadId.value === id) {
      activeThreadId.value = null
      return
    }
    activeThreadId.value = id
  }

  function clearActiveThread() {
    activeThreadId.value = null
  }

  function setSessions(list: ThreadSession[]) {
    sessions.value = [...list].sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })
  }

  function updateSessionInCache(update: Partial<ThreadSession> & { thread_id: string }) {
    const idx = sessions.value.findIndex(s => s.thread_id === update.thread_id)
    if (idx !== -1) {
      sessions.value[idx] = { ...sessions.value[idx], ...update }
    }
  }

  function removeSessionFromCache(id: string) {
    sessions.value = sessions.value.filter(s => s.thread_id !== id)
  }

  return {
    activeThreadId, sessions, isWelcomeMode, activeSession,
    setActiveThread, clearActiveThread, setSessions,
    updateSessionInCache, removeSessionFromCache,
  }
})
