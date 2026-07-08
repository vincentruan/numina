import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock family store so getAgentHeaders() doesn't require an active Pinia
vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    family: { id: 'family-1' },
  }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { family_id: 'family-1' },
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

  it('getThread uses metadata.title when present', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ thread_id: 't1', status: 'idle', created_at: '', updated_at: '', metadata: { title: 'LLM Summary' }, values: { title: '[SKILL:chat]' } }),
    })
    const { getThread } = await import('../ai-chat')
    const result = await getThread('t1')
    expect(result.title).toBe('LLM Summary')
  })

  it('getThread ignores values.title when it is a [SKILL:chat] wrapper', async () => {
    // Sync stream path: metadata.title is empty (LLM title not generated yet),
    // values.title is the raw [SKILL:chat] prompt wrapper - must NOT leak as title.
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ thread_id: 't1', status: 'idle', created_at: '', updated_at: '', metadata: {}, values: { title: '[SKILL:chat]\n{"family_id":"123"}' } }),
    })
    const { getThread } = await import('../ai-chat')
    const result = await getThread('t1')
    expect(result.title).toBe('')
  })

  it('getThread falls back to values.title when it is a proper title (async path)', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ thread_id: 't1', status: 'idle', created_at: '', updated_at: '', metadata: {}, values: { title: 'Async Middleware Title' } }),
    })
    const { getThread } = await import('../ai-chat')
    const result = await getThread('t1')
    expect(result.title).toBe('Async Middleware Title')
  })

})
