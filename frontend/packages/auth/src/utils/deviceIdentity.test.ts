import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock IndexedDB
const mockIdbStore = new Map<string, string>()
const mockObjectStore = {
  get: vi.fn((key: string) => {
    const result = { result: mockIdbStore.get(key) ?? null, onsuccess: null as any, onerror: null as any }
    setTimeout(() => result.onsuccess?.())
    return result
  }),
  put: vi.fn((value: string, key: string) => {
    mockIdbStore.set(key, value)
  }),
  delete: vi.fn((key: string) => {
    mockIdbStore.delete(key)
  }),
}
const mockTransaction = { objectStore: () => mockObjectStore }
const mockDb = {
  transaction: () => mockTransaction,
  createObjectStore: vi.fn(),
}

vi.stubGlobal('indexedDB', {
  open: vi.fn(() => {
    const req = { result: mockDb, onupgradeneeded: null as any, onsuccess: null as any, onerror: null as any }
    setTimeout(() => req.onsuccess?.())
    return req
  }),
})

// Mock fetch for ETag recovery
vi.stubGlobal('fetch', vi.fn())

import { readDeviceId, writeDeviceId, clearDeviceId, recoverFromEtag } from './deviceIdentity'

describe('deviceIdentity', () => {
  beforeEach(() => {
    localStorage.clear()
    document.cookie = 'numina_device_id=; Path=/; Max-Age=0'
    mockIdbStore.clear()
    vi.clearAllMocks()
  })

  it('reads from cookie first and backfills localStorage + IDB', async () => {
    document.cookie = 'numina_device_id=test-uuid-1'
    const result = await readDeviceId()
    expect(result).toBe('test-uuid-1')
    expect(localStorage.getItem('_numina_device_id')).toBe('test-uuid-1')
  })

  it('falls back to localStorage when cookie is missing', async () => {
    localStorage.setItem('_numina_device_id', 'ls-uuid')
    const result = await readDeviceId()
    expect(result).toBe('ls-uuid')
  })

  it('falls back to IndexedDB when cookie and localStorage are missing', async () => {
    mockIdbStore.set('device_id', 'idb-uuid')
    const result = await readDeviceId()
    expect(result).toBe('idb-uuid')
    expect(localStorage.getItem('_numina_device_id')).toBe('idb-uuid')
  })

  it('returns null when all layers are empty', async () => {
    const result = await readDeviceId()
    expect(result).toBeNull()
  })

  it('writeDeviceId writes to localStorage and IDB', async () => {
    await writeDeviceId('write-uuid')
    expect(localStorage.getItem('_numina_device_id')).toBe('write-uuid')
    expect(mockIdbStore.get('device_id')).toBe('write-uuid')
  })

  it('clearDeviceId clears localStorage and cookie', () => {
    localStorage.setItem('_numina_device_id', 'clear-uuid')
    clearDeviceId()
    expect(localStorage.getItem('_numina_device_id')).toBeNull()
  })

  it('recoverFromEtag fetches device-ping and writes the recovered id', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ device_id: 'etag-uuid' }),
    } as Response)

    const result = await recoverFromEtag()
    expect(result).toBe('etag-uuid')
    expect(localStorage.getItem('_numina_device_id')).toBe('etag-uuid')
  })

  it('recoverFromEtag returns null when server has no device_id', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValue({
      json: () => Promise.resolve({ device_id: null }),
    } as Response)

    const result = await recoverFromEtag()
    expect(result).toBeNull()
  })
})
