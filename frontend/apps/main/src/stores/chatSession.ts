import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ThreadSession } from '@/types/ai-chat/session'

export interface PendingMessage {
  text: string
  agentId?: string
  deepThink?: boolean
  webSearch?: boolean
  source?: string
}

export const useChatSessionStore = defineStore('chatSession', () => {
  const activeThreadId = ref<string | null>(null)
  const sessions = ref<ThreadSession[]>([])
  const pendingMessage = ref<PendingMessage | null>(null)

  const isWelcomeMode = computed(() => activeThreadId.value === null)
  const activeSession = computed(() =>
    sessions.value.find(s => s.thread_id === activeThreadId.value) ?? null
  )

  // Initialize from URL parameters — now also reads the message payload
  // passed from AIHubPage (q, agentId, newSession, deepThink, webSearch, source)
  function initializeFromUrl() {
    const params = new URLSearchParams(window.location.search)
    const threadId = params.get('threadId') ?? params.get('thread_id')
    const newSession = params.get('newSession')
    const q = params.get('q')
    const agentId = params.get('agentId')
    const deepThink = params.get('deepThink')
    const webSearch = params.get('webSearch')
    const source = params.get('source')

    if (newSession === '1') {
      // Start a new session by clearing active thread
      clearActiveThread()
    } else if (threadId) {
      setActiveThread(threadId)
    }

    // If there's a message in the URL, stash it for AIChatBox to auto-send
    if (q) {
      pendingMessage.value = {
        text: q,
        agentId: agentId || undefined,
        deepThink: deepThink === '1',
        webSearch: webSearch === '1',
        source: source || undefined,
      }
    }
  }

  function setActiveThread(id: string) {
    // Always set the thread - removed toggle behavior that was clearing on same ID
    // This ensures ChatHistoryPage can re-select the same thread without losing state
    if (activeThreadId.value === id) {
      // Already active - no change needed, just update URL
      history.replaceState(null, '', `?thread_id=${id}`)
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
    activeThreadId, sessions, isWelcomeMode, activeSession, pendingMessage,
    initializeFromUrl, setActiveThread, clearActiveThread, setSessions,
  }
})
