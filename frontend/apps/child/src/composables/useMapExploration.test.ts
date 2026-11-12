import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'

vi.mock('@/api/learning', () => ({
  recordMapExploration: vi.fn(),
}))

import { recordMapExploration } from '@/api/learning'
import { useMapExploration } from './useMapExploration'

const mockRecord = vi.mocked(recordMapExploration)

// Host component pattern — composable used inside setup context
function mountHost() {
  let api: ReturnType<typeof useMapExploration> | null = null
  const Host = defineComponent({
    setup() {
      api = useMapExploration()
      return () => null
    },
  })
  mount(Host)
  return () => api!
}

describe('useMapExploration (R11, R12, AE4)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRecord.mockResolvedValue({} as never)
  })

  it('starts timing at mount', () => {
    const getApi = mountHost()
    const api = getApi()
    expect(api.startedAt).not.toBeNull()
  })

  it('records a topic selection exactly once, with elapsed duration (R11)', () => {
    vi.useFakeTimers()
    const getApi = mountHost()
    const api = getApi()
    vi.advanceTimersByTime(0)
    const t0 = Date.now()
    // Simulate 2s later
    vi.setSystemTime(t0 + 2000)
    api.recordTopicSelection('topic-1')
    const call = mockRecord.mock.calls[0][0]
    expect(call.duration_ms).toBeGreaterThanOrEqual(2000)
    expect(call.topic_selected).toBe(true)
    expect(call.selected_topic_id).toBe('topic-1')
    expect(call.max_zoom_level).toBe(0) // no zoom recorded yet
    expect(call.interaction_count).toBe(1) // the selection itself
    vi.useRealTimers()
  })

  it('does not double-record a second topic selection', async () => {
    const getApi = mountHost()
    const api = getApi()
    api.recordTopicSelection('topic-1')
    api.recordTopicSelection('topic-2')
    expect(mockRecord).toHaveBeenCalledTimes(1)
    expect(mockRecord.mock.calls[0][0].selected_topic_id).toBe('topic-1')
  })

  it('records zoom level reached (R12)', () => {
    const getApi = mountHost()
    const api = getApi()
    api.recordZoom(1)
    api.recordZoom(2)
    api.recordZoom(0) // zooming back out doesn't lower max
    api.recordTopicSelection('t')
    const call = mockRecord.mock.calls[0][0]
    expect(call.max_zoom_level).toBe(2)
  })

  it('counts pan/tap interactions (R12)', () => {
    const getApi = mountHost()
    const api = getApi()
    api.recordInteraction()
    api.recordInteraction()
    api.recordTopicSelection('t') // +1 (selection counts)
    const call = mockRecord.mock.calls[0][0]
    expect(call.interaction_count).toBe(3)
  })

  it('flushes on leave with topic_selected=false when no selection happened (AE4)', async () => {
    const getApi = mountHost()
    const api = getApi()
    api.recordZoom(1)
    api.recordInteraction()
    api.recordInteraction()
    api.flush()
    await flushPromises()
    expect(mockRecord).toHaveBeenCalledTimes(1)
    const call = mockRecord.mock.calls[0][0]
    expect(call.topic_selected).toBe(false)
    expect(call.max_zoom_level).toBe(1)
    expect(call.interaction_count).toBe(2)
    expect(call.selected_topic_id).toBeUndefined()
  })

  it('does not flush twice (leave after selection already recorded)', async () => {
    const getApi = mountHost()
    const api = getApi()
    api.recordTopicSelection('t')
    api.flush()
    await flushPromises()
    expect(mockRecord).toHaveBeenCalledTimes(1)
  })

  it('re-arms after flush (next map visit records anew)', async () => {
    const getApi = mountHost()
    const api = getApi()
    api.flush()
    await flushPromises()
    expect(mockRecord).toHaveBeenCalledTimes(1)
    api.start() // next visit
    api.recordZoom(2)
    api.flush()
    await flushPromises()
    expect(mockRecord).toHaveBeenCalledTimes(2)
    expect(mockRecord.mock.calls[1][0].max_zoom_level).toBe(2)
  })

  it('still flushes if the API call fails (never throws to the caller)', async () => {
    mockRecord.mockRejectedValueOnce(new Error('network'))
    const getApi = mountHost()
    const api = getApi()
    api.flush()
    await flushPromises()
    // No unhandled rejection thrown into the caller
    expect(mockRecord).toHaveBeenCalledTimes(1)
  })
})
