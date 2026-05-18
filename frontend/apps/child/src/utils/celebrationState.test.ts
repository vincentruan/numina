import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getCelebratedIds,
  markCelebrated,
  findPendingCelebrations,
  clearCelebratedIds,
} from '@/utils/celebrationState'
import type { ChoreInstance } from '@/api/chores'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
})

// Helper to create mock chore
function mockChore(id: string, status: ChoreInstance['status']): ChoreInstance {
  return {
    id,
    status,
    chore_name: 'Test Chore',
    chore_emoji: '✅',
    coin_reward: 5,
    streak_bonus: 0,
    streak_count: 1,
    is_pool_unclaimed: false,
  } as ChoreInstance
}

describe('celebrationState', () => {
  beforeEach(() => {
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  describe('getCelebratedIds', () => {
    it('returns empty set when localStorage is empty', () => {
      const result = getCelebratedIds()
      expect(result).toBeInstanceOf(Set)
      expect(result.size).toBe(0)
    })

    it('returns empty set when localStorage contains invalid JSON', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', 'not-json')
      const result = getCelebratedIds()
      expect(result.size).toBe(0)
    })

    it('returns empty set when localStorage contains non-array', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', '{"foo":"bar"}')
      const result = getCelebratedIds()
      expect(result.size).toBe(0)
    })

    it('returns set of strings from valid array', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', '["id1","id2","id3"]')
      const result = getCelebratedIds()
      expect(result.size).toBe(3)
      expect(result.has('id1')).toBe(true)
      expect(result.has('id2')).toBe(true)
      expect(result.has('id3')).toBe(true)
    })

    it('filters out non-string items from array', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', '["id1",42,null,"id2"]')
      const result = getCelebratedIds()
      expect(result.size).toBe(2)
      expect(result.has('id1')).toBe(true)
      expect(result.has('id2')).toBe(true)
    })
  })

  describe('markCelebrated', () => {
    it('adds new IDs to existing set', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', '["id1"]')
      markCelebrated(['id2', 'id3'])
      const result = getCelebratedIds()
      expect(result.has('id1')).toBe(true)
      expect(result.has('id2')).toBe(true)
      expect(result.has('id3')).toBe(true)
    })

    it('deduplicates IDs', () => {
      markCelebrated(['id1', 'id1', 'id2'])
      const result = getCelebratedIds()
      expect(result.size).toBe(2)
    })

    it('prunes to max 50 IDs when exceeding limit', () => {
      // Add 60 IDs
      const ids = Array.from({ length: 60 }, (_, i) => `id${i}`)
      markCelebrated(ids)
      const result = getCelebratedIds()
      expect(result.size).toBe(50)
      // Should keep last 50 (most recent)
      expect(result.has('id9')).toBe(true) // 10th from end
      expect(result.has('id0')).toBe(false) // First one pruned
    })

    it('silently fails on localStorage quota error', () => {
      localStorageMock.setItem.mockImplementationOnce(() => {
        throw new Error('QuotaExceededError')
      })
      // Should not throw
      markCelebrated(['id1'])
      expect(localStorageMock.setItem).toHaveBeenCalled()
    })
  })

  describe('findPendingCelebrations', () => {
    it('returns empty array when no approved tasks', () => {
      const chores = [
        mockChore('id1', 'available'),
        mockChore('id2', 'pending_approval'),
      ]
      const result = findPendingCelebrations(chores)
      expect(result).toHaveLength(0)
    })

    it('returns approved tasks not in celebrated set', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', '["id1"]')
      const chores = [
        mockChore('id1', 'approved'), // already celebrated
        mockChore('id2', 'approved'), // pending
        mockChore('id3', 'pending_approval'), // not approved
      ]
      const result = findPendingCelebrations(chores)
      expect(result).toHaveLength(1)
      expect(result[0].id).toBe('id2')
    })

    it('returns all approved tasks when celebrated set is empty', () => {
      const chores = [
        mockChore('id1', 'approved'),
        mockChore('id2', 'approved'),
      ]
      const result = findPendingCelebrations(chores)
      expect(result).toHaveLength(2)
    })
  })

  describe('clearCelebratedIds', () => {
    it('removes the storage key', () => {
      localStorageMock.setItem('numina-child-celebrated-tasks', '["id1"]')
      clearCelebratedIds()
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('numina-child-celebrated-tasks')
      const result = getCelebratedIds()
      expect(result.size).toBe(0)
    })
  })
})