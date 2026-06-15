/**
 * useArtifacts.ts unit tests — DeerFlow artifact management parity
 *
 * 参考: frontend/src/components/workspace/artifacts/context.tsx
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { useArtifacts, loadArtifactContent, useArtifactContent } from '@/composables/ai-chat/useArtifacts'
import type { Artifact } from '@/types/agent-stream'

// Mock fetch for loadArtifactContent tests
const mockFetch = vi.fn()
global.fetch = mockFetch

// Mock familyStore for Pinia dependency
vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    currentFamily: { id: 'family-1' },
  }),
}))

describe('useArtifacts', () => {
  beforeEach(() => {
    // Clear global state before each test
    const { clearArtifacts } = useArtifacts()
    clearArtifacts()
    vi.clearAllMocks()
  })

  describe('setArtifacts', () => {
    it('creates artifact dict from array', async () => {
      const { setArtifacts, artifacts, artifactList } = useArtifacts()

      const newArtifacts: Artifact[] = [
        { id: 'art1', path: '/file1.md', kind: 'markdown' },
        { id: 'art2', path: '/file2.py', kind: 'code' },
      ]

      setArtifacts(newArtifacts)
      await nextTick()

      expect(Object.keys(artifacts.value)).toEqual(['art1', 'art2'])
      expect(artifactList.value.length).toBe(2)
    })

    it('uses path as key when id is missing', async () => {
      const { setArtifacts, artifacts } = useArtifacts()

      const newArtifacts: Artifact[] = [
        { path: '/file1.md', kind: 'markdown' },
      ]

      setArtifacts(newArtifacts)
      await nextTick()

      expect(artifacts.value['/file1.md']).toBeDefined()
    })

    it('skips artifacts without id or path', async () => {
      const { setArtifacts, artifacts } = useArtifacts()

      const newArtifacts: Artifact[] = [
        { id: 'art1', path: '/file1.md' },
        { kind: 'markdown' }, // no id, no path
      ]

      setArtifacts(newArtifacts)
      await nextTick()

      expect(Object.keys(artifacts.value)).toEqual(['art1'])
    })
  })

  describe('addArtifact', () => {
    it('adds single artifact to existing dict', async () => {
      const { setArtifacts, addArtifact, artifacts } = useArtifacts()

      setArtifacts([{ id: 'art1', path: '/file1.md' }])
      await nextTick()

      addArtifact({ id: 'art2', path: '/file2.py' })
      await nextTick()

      expect(Object.keys(artifacts.value)).toEqual(['art1', 'art2'])
    })

    it('does nothing when artifact has no id or path', async () => {
      const { setArtifacts, addArtifact, artifacts } = useArtifacts()

      setArtifacts([{ id: 'art1', path: '/file1.md' }])
      await nextTick()

      addArtifact({ kind: 'markdown' }) // no id, no path
      await nextTick()

      expect(Object.keys(artifacts.value)).toEqual(['art1'])
    })
  })

  describe('select / deselect', () => {
    it('selects artifact and opens preview', async () => {
      const { setArtifacts, select, selectedArtifact, open } = useArtifacts()

      const artifact: Artifact = { id: 'art1', path: '/file.md' }
      setArtifacts([artifact])
      await nextTick()

      select(artifact)
      await nextTick()

      expect(selectedArtifact.value).toStrictEqual(artifact)
      expect(open.value).toBe(true)
    })

    it('deselect closes preview and clears selection', async () => {
      const { setArtifacts, select, deselect, selectedArtifact, open } = useArtifacts()

      const artifact: Artifact = { id: 'art1', path: '/file.md' }
      setArtifacts([artifact])
      select(artifact)
      await nextTick()

      deselect()
      await nextTick()

      expect(selectedArtifact.value).toBeNull()
      expect(open.value).toBe(false)
    })
  })

  describe('selectByPath', () => {
    it('selects artifact by filepath', async () => {
      const { setArtifacts, selectByPath, selectedArtifact, open } = useArtifacts()

      setArtifacts([{ path: '/report.md', kind: 'markdown' }])
      await nextTick()

      selectByPath('/report.md')
      await nextTick()

      expect(selectedArtifact.value?.path).toBe('/report.md')
      expect(open.value).toBe(true)
    })

    it('does nothing when path not found', async () => {
      const { setArtifacts, selectByPath, selectedArtifact } = useArtifacts()

      setArtifacts([{ path: '/report.md' }])
      await nextTick()

      selectByPath('/nonexistent.md')
      await nextTick()

      expect(selectedArtifact.value).toBeNull()
    })
  })

  describe('autoSelect / autoOpen', () => {
    it('autoSelect picks last artifact', async () => {
      const { setArtifacts, autoSelect, selectedArtifact } = useArtifacts()

      setArtifacts([
        { id: 'art1', path: '/file1.md' },
        { id: 'art2', path: '/file2.md' },
        { id: 'art3', path: '/file3.md' },
      ])
      await nextTick()

      autoSelect()
      await nextTick()

      // Last key is 'art3'
      expect(selectedArtifact.value?.id).toBe('art3')
    })

    it('autoOpen opens preview when artifacts exist', async () => {
      const { setArtifacts, autoOpen, open, selectedArtifact } = useArtifacts()

      setArtifacts([{ id: 'art1', path: '/file.md' }])
      await nextTick()

      autoOpen()
      await nextTick()

      expect(open.value).toBe(true)
      expect(selectedArtifact.value).toBeDefined()
    })

    it('autoOpen does nothing when no artifacts', async () => {
      const { autoOpen, open } = useArtifacts()

      autoOpen()
      await nextTick()

      expect(open.value).toBe(false)
    })

    it('autoOpen does nothing when already open', async () => {
      const { setArtifacts, select, autoOpen, open } = useArtifacts()

      const artifact: Artifact = { id: 'art1', path: '/file.md' }
      setArtifacts([artifact])
      select(artifact)
      await nextTick()

      // Add another artifact and try autoOpen
      setArtifacts([{ id: 'art2', path: '/file2.md' }])
      await nextTick()

      autoOpen()
      await nextTick()

      // Should not change selection since already open
      expect(open.value).toBe(true)
    })
  })

  describe('setOpen', () => {
    it('sets open state', async () => {
      const { setOpen, open } = useArtifacts()

      setOpen(true)
      await nextTick()

      expect(open.value).toBe(true)

      setOpen(false)
      await nextTick()

      expect(open.value).toBe(false)
    })

    it('clears selection when closing', async () => {
      const { setArtifacts, select, setOpen, open, selectedArtifact } = useArtifacts()

      const artifact: Artifact = { id: 'art1', path: '/file.md' }
      setArtifacts([artifact])
      select(artifact)
      await nextTick()

      setOpen(false)
      await nextTick()

      expect(open.value).toBe(false)
      expect(selectedArtifact.value).toBeNull()
    })
  })

  describe('clearArtifacts', () => {
    it('clears all state', async () => {
      const { setArtifacts, select, clearArtifacts, artifacts, selectedArtifact, open } =
        useArtifacts()

      const artifact: Artifact = { id: 'art1', path: '/file.md' }
      setArtifacts([artifact])
      select(artifact)
      await nextTick()

      clearArtifacts()
      await nextTick()

      expect(Object.keys(artifacts.value)).toEqual([])
      expect(selectedArtifact.value).toBeNull()
      expect(open.value).toBe(false)
    })
  })

  describe('readonly refs', () => {
    it('artifacts is readonly - mutation prevented', async () => {
      const { artifacts, setArtifacts } = useArtifacts()

      setArtifacts([{ id: 'art1', path: '/file.md' }])
      await nextTick()

      // Vue readonly doesn't throw, it silently prevents mutation
      // Try to mutate directly - value should not change
      const originalValue = artifacts.value['art1']
      artifacts.value['art1'] = { id: 'modified' }
      await nextTick()

      expect(artifacts.value['art1']).toStrictEqual(originalValue)
    })

    it('selectedArtifact is readonly - mutation prevented', async () => {
      const { setArtifacts, select, selectedArtifact } = useArtifacts()

      const artifact: Artifact = { id: 'art1', path: '/file.md' }
      setArtifacts([artifact])
      select(artifact)
      await nextTick()

      // Vue readonly doesn't throw, it silently prevents mutation
      const originalValue = selectedArtifact.value
      selectedArtifact.value = { id: 'modified' }
      await nextTick()

      expect(selectedArtifact.value).toStrictEqual(originalValue)
    })

    it('open is readonly - mutation prevented', async () => {
      const { open } = useArtifacts()

      // Vue readonly doesn't throw, it silently prevents mutation
      const originalValue = open.value
      open.value = true
      await nextTick()

      expect(open.value).toBe(originalValue)
    })
  })
})

describe('loadArtifactContent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('encodes filepath in URL', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: () => Promise.resolve('content'),
    })

    await loadArtifactContent('foo bar/中文.md', 'sess-1')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('foo%20bar%2F%E4%B8%AD%E6%96%87.md'),
      expect.objectContaining({ headers: { 'X-Family-Id': 'family-1' } }),
    )
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found',
    })

    await expect(loadArtifactContent('file.md', 'sess-1')).rejects.toThrow('Failed to load artifact')
  })
})

describe('useArtifactContent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns content, loading, error, load', () => {
    const { content, loading, error, load } = useArtifactContent('file.md', 'sess-unique-1')

    expect(content.value).toBeNull()
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    expect(typeof load).toBe('function')
  })

  it('fetches content on load', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: () => Promise.resolve('file content'),
    })

    const { content, loading, load } = useArtifactContent('file.md', 'sess-unique-2')

    await load()

    expect(content.value).toBe('file content')
    expect(loading.value).toBe(false)
  })

  it('encodes filepath in URL', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: () => Promise.resolve('content'),
    })

    const { load } = useArtifactContent('foo bar/中文.md', 'sess-unique-3')

    await load()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('foo%20bar%2F%E4%B8%AD%E6%96%87.md'),
      expect.objectContaining({ headers: { 'X-Family-Id': 'family-1' } }),
    )
  })

  it('sets error on fetch failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found',
    })

    const { error, content, load } = useArtifactContent('file.md', 'sess-unique-4')

    await load()

    expect(error.value).toContain('Failed to load artifact')
    expect(content.value).toBeNull()
  })

  it('sets error on network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))

    const { error, content, load } = useArtifactContent('file.md', 'sess-unique-5')

    await load()

    expect(error.value).toBe('Network error')
    expect(content.value).toBeNull()
  })

  it('sets loading during fetch', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: () => Promise.resolve('content'),
    })

    const { loading, load } = useArtifactContent('file.md', 'sess-unique-6')

    // Before load
    expect(loading.value).toBe(false)

    await load()

    // After load
    expect(loading.value).toBe(false)
  })
})