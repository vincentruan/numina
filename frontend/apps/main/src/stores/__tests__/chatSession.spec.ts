import { setActivePinia, createPinia } from 'pinia'
import { useChatSessionStore } from '../chatSession'
import type { ThreadSession } from '@/types/ai-chat/session'
import { describe, it, expect, beforeEach } from 'vitest'

describe('useChatSessionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts in welcome mode', () => {
    const store = useChatSessionStore()
    expect(store.isWelcomeMode).toBe(true)
    expect(store.activeThreadId).toBeNull()
    expect(store.sessions).toEqual([])
  })

  it('setActiveThread sets thread and switches to chat mode', () => {
    const store = useChatSessionStore()
    store.setActiveThread('thread-123')
    expect(store.activeThreadId).toBe('thread-123')
    expect(store.isWelcomeMode).toBe(false)
  })

  it('clearActiveThread returns to welcome mode', () => {
    const store = useChatSessionStore()
    store.setActiveThread('thread-123')
    store.clearActiveThread()
    expect(store.activeThreadId).toBeNull()
    expect(store.isWelcomeMode).toBe(true)
  })

  it('setSessions stores and sorts by pinned + updated_at desc', () => {
    const store = useChatSessionStore()
    const now = new Date()
    const sessions = [
      { thread_id: 't2', title: 'old', status: 'idle', is_pinned: false,
        created_at: new Date(now.getTime() - 2000).toISOString(),
        updated_at: new Date(now.getTime() - 2000).toISOString() },
      { thread_id: 't1', title: 'pinned', status: 'idle', is_pinned: true,
        created_at: now.toISOString(),
        updated_at: new Date(now.getTime() - 1000).toISOString() },
    ] as ThreadSession[]
    store.setSessions(sessions)
    expect(store.sessions[0].thread_id).toBe('t1')
  })

  it('setActiveThread clears active if switching to same thread', () => {
    const store = useChatSessionStore()
    store.setActiveThread('same')
    store.setActiveThread('same')
    expect(store.isWelcomeMode).toBe(true)
    expect(store.activeThreadId).toBeNull()
  })
})
