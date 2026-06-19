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
      history.replaceState(null, '', window.location.pathname)
      return
    }
    activeThreadId.value = id
    history.replaceState(null, '', `?thread_id=${id}`)
  }

  function clearActiveThread() {
    activeThreadId.value = null
    history.replaceState(null, '', window.location.pathname)
  }

  function setSessions(list: ThreadSession[]) {
    sessions.value = [...list].sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })
  }

  return {
    activeThreadId, sessions, isWelcomeMode, activeSession,
    setActiveThread, clearActiveThread, setSessions,
  }
})
