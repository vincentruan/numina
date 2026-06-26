import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock family store so getAgentHeaders() doesn't require an active Pinia
vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    family: { id: 'family-1' },
  }),
}))

const mockFetch = vi.fn()
global.fetch = mockFetch as unknown as typeof fetch

describe('ai-chat API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('createThread calls POST /api/threads', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ thread_id: 't1', status: 'idle', created_at: '', updated_at: '', metadata: {}, values: {} }),
    })
    const { createThread } = await import('../ai-chat')
    const result = await createThread()
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/threads'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(result.thread_id).toBe('t1')
  })

  it('searchThreads calls POST /api/threads/search', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    })
    const { searchThreads } = await import('../ai-chat')
    const result = await searchThreads({})
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/threads/search'),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(result.items).toEqual([])
  })

  it('updateThread calls PATCH /api/threads/:id', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ thread_id: 't1', status: 'idle', created_at: '', updated_at: '', metadata: { title: 'new' }, values: {} }),
    })
    const { updateThread } = await import('../ai-chat')
    await updateThread('t1', { title: 'new' })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/threads/t1'),
      expect.objectContaining({ method: 'PATCH' }),
    )
  })

  it('deleteThread calls DELETE /api/threads/:id', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    })
    const { deleteThread } = await import('../ai-chat')
    await deleteThread('t1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/threads/t1'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})
