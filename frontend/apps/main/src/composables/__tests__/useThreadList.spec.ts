import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n — useI18n requires a Vue app instance; mock it in unit tests
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

const mockSearchThreads = vi.fn()
const mockDeleteThread = vi.fn()
const mockUpdateThread = vi.fn()
vi.mock('@/api/ai-chat', () => ({
  searchThreads: (...args: any[]) => mockSearchThreads(...args),
  deleteThread: (...args: any[]) => mockDeleteThread(...args),
  updateThread: (...args: any[]) => mockUpdateThread(...args),
}))

describe('useThreadList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loadMore fetches and groups sessions', async () => {
    mockSearchThreads.mockResolvedValue({
      items: [
        { thread_id: 't1', title: 'Chat 1', status: 'idle', is_pinned: false,
          created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
      ],
      total: 1,
    })
    const { useThreadList } = await import('../useThreadList')
    const list = useThreadList()
    expect(list.isLoading.value).toBe(false)
    expect(list.hasMore.value).toBe(true)

    await list.loadMore()
    expect(list.sessions.value.length).toBe(1)
    expect(list.hasMore.value).toBe(false)
    expect(list.dateGroups.value.length).toBeGreaterThanOrEqual(1)
  })

  it('deleteSession calls API and removes from cache', async () => {
    mockSearchThreads.mockResolvedValue({ items: [], total: 0 })
    const { useThreadList } = await import('../useThreadList')
    const list = useThreadList()
    ;(list as any).sessions.value = [{
      thread_id: 't1', title: 'x', status: 'idle', is_pinned: false,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    }]
    mockDeleteThread.mockResolvedValue(undefined)
    await list.deleteSession('t1')
    expect(mockDeleteThread).toHaveBeenCalledWith('t1')
    expect(list.sessions.value).toEqual([])
  })

  it('renameSession calls updateThread', async () => {
    const { useThreadList } = await import('../useThreadList')
    const list = useThreadList()
    ;(list as any).sessions.value = [{
      thread_id: 't1', title: 'old', status: 'idle', is_pinned: false,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    }]
    mockUpdateThread.mockResolvedValue({ thread_id: 't1', title: 'new' })
    await list.renameSession('t1', 'new')
    expect(mockUpdateThread).toHaveBeenCalledWith('t1', { title: 'new' })
    expect(list.sessions.value[0].title).toBe('new')
  })

  it('togglePin flips is_pinned', async () => {
    const { useThreadList } = await import('../useThreadList')
    const list = useThreadList()
    ;(list as any).sessions.value = [{
      thread_id: 't1', title: 'x', status: 'idle', is_pinned: false,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    }]
    mockUpdateThread.mockResolvedValue({ thread_id: 't1', is_pinned: true })
    await list.togglePin('t1')
    expect(mockUpdateThread).toHaveBeenCalledWith('t1', { is_pinned: true })
  })

  it('refresh clears and reloads', async () => {
    mockSearchThreads.mockResolvedValue({ items: [], total: 0 })
    const { useThreadList } = await import('../useThreadList')
    const list = useThreadList()
    ;(list as any).sessions.value = [{ thread_id: 't1', title: 'x', status: 'idle', is_pinned: false,
      created_at: new Date().toISOString(), updated_at: new Date().toISOString() }]
    await list.refresh()
    expect(list.sessions.value).toEqual([])
  })
})
