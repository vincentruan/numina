import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockRequest = vi.fn()
vi.mock('@/api/index', () => ({
  default: { request: mockRequest },
}))

describe('ai-chat API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('createThread calls POST /api/threads', async () => {
    mockRequest.mockResolvedValue({ data: { thread_id: 't1' } })
    const { createThread } = await import('../ai-chat')
    const result = await createThread()
    expect(mockRequest).toHaveBeenCalledWith({
      method: 'POST', url: '/api/threads', data: {},
    })
    expect(result.thread_id).toBe('t1')
  })

  it('searchThreads calls GET /api/threads/search', async () => {
    mockRequest.mockResolvedValue({ data: { items: [] } })
    const { searchThreads } = await import('../ai-chat')
    const result = await searchThreads({})
    expect(mockRequest).toHaveBeenCalledWith({
      method: 'GET', url: '/api/threads/search', params: {},
    })
    expect(result.items).toEqual([])
  })

  it('updateThread calls PUT /api/threads/:id', async () => {
    mockRequest.mockResolvedValue({ data: {} })
    const { updateThread } = await import('../ai-chat')
    await updateThread('t1', { title: 'new' })
    expect(mockRequest).toHaveBeenCalledWith({
      method: 'PUT', url: '/api/threads/t1', data: { title: 'new' },
    })
  })

  it('deleteThread calls DELETE /api/threads/:id', async () => {
    mockRequest.mockResolvedValue({})
    const { deleteThread } = await import('../ai-chat')
    await deleteThread('t1')
    expect(mockRequest).toHaveBeenCalledWith({
      method: 'DELETE', url: '/api/threads/t1',
    })
  })

  it('forkThread calls POST /api/threads/:id/fork', async () => {
    mockRequest.mockResolvedValue({ data: { thread_id: 't2' } })
    const { forkThread } = await import('../ai-chat')
    const result = await forkThread('t1')
    expect(mockRequest).toHaveBeenCalledWith({
      method: 'POST', url: '/api/threads/t1/fork',
    })
    expect(result.thread_id).toBe('t2')
  })
})
