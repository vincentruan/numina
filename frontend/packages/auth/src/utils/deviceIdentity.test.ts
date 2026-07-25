import { describe, it, expect, beforeEach, vi } from 'vitest'

import { readDeviceId, readDeviceIdSync, writeDeviceId, clearDeviceId } from './deviceIdentity'

// Mock IndexedDB for jsdom environment
const mockIdbStore = new Map<string, string>()

function createMockTx() {
  let oncompleteCb: (() => void) | null = null
  let onerrorCb: (() => void) | null = null
  let onabortCb: (() => void) | null = null
  const tx = {
    objectStore: vi.fn(() => ({
      get: vi.fn((key: string) => {
        const req = { result: mockIdbStore.get(key), onsuccess: null as any, onerror: null as any }
        queueMicrotask(() => req.onsuccess?.(req))
        return req
      }),
      put: vi.fn((value: string, key: string) => {
        mockIdbStore.set(key, value)
        return { onsuccess: null, onerror: null }
      }),
      delete: vi.fn((key: string) => {
        mockIdbStore.delete(key)
        return { onsuccess: null, onerror: null }
      }),
    })),
    get oncomplete() { return oncompleteCb },
    set oncomplete(cb: any) { oncompleteCb = cb; queueMicrotask(() => cb?.()) },
    get onerror() { return onerrorCb },
    set onerror(cb: any) { onerrorCb = cb },
    get onabort() { return onabortCb },
    set onabort(cb: any) { onabortCb = cb },
  }
  return tx
}

const mockIdb = {
  transaction: vi.fn(() => createMockTx()),
  close: vi.fn(),
}

vi.stubGlobal('indexedDB', {
  open: vi.fn(() => {
    const req = { result: mockIdb, onsuccess: null as any, onerror: null as any }
    queueMicrotask(() => req.onsuccess?.(req))
    return req
  }),
})

describe('deviceIdentity', () => {
  beforeEach(async () => {
    document.cookie = 'numina_device_id=; path=/; max-age=0'
    localStorage.clear()
    mockIdbStore.clear()
    await clearDeviceId()
  })

  it('returns null when cookie is absent', () => {
    expect(readDeviceIdSync()).toBeNull()
  })

  it('reads the device id from cookie (sync)', () => {
    document.cookie = 'numina_device_id=test-uuid-1'
    expect(readDeviceIdSync()).toBe('test-uuid-1')
  })

  it('writeDeviceId sets the cookie', () => {
    writeDeviceId('write-uuid')
    expect(readDeviceIdSync()).toBe('write-uuid')
  })

  it('clearDeviceId removes the cookie', async () => {
    writeDeviceId('clear-uuid')
    await clearDeviceId()
    expect(readDeviceIdSync()).toBeNull()
  })

  it('handles encoded values in cookie', () => {
    writeDeviceId('uuid-with-special')
    expect(readDeviceIdSync()).toBe('uuid-with-special')
  })

  // --- localStorage fallback tests ---

  it('writeDeviceId also writes to localStorage', () => {
    writeDeviceId('dual-write-uuid')
    expect(localStorage.getItem('numina_device_id')).toBe('dual-write-uuid')
  })

  it('readDeviceId returns cookie value when both cookie and localStorage exist', async () => {
    writeDeviceId('cookie-value')
    localStorage.setItem('numina_device_id', 'ls-value')
    expect(await readDeviceId()).toBe('cookie-value')
  })

  it('readDeviceId falls back to localStorage when cookie is absent', async () => {
    localStorage.setItem('numina_device_id', 'ls-fallback-value')
    expect(await readDeviceId()).toBe('ls-fallback-value')
  })

  it('readDeviceId returns null when both cookie and localStorage are empty', async () => {
    expect(await readDeviceId()).toBeNull()
  })

  it('clearDeviceId removes both cookie and localStorage', async () => {
    writeDeviceId('to-clear')
    await clearDeviceId()
    expect(readDeviceIdSync()).toBeNull()
    expect(localStorage.getItem('numina_device_id')).toBeNull()
  })

  it('writeDeviceId does not throw when localStorage.setItem fails', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded')
    })
    expect(() => writeDeviceId('quota-uuid')).not.toThrow()
    expect(readDeviceIdSync()).toBe('quota-uuid') // cookie still works
    spy.mockRestore()
  })

  // --- IndexedDB tests ---

  it('writeDeviceId also writes to IndexedDB', async () => {
    writeDeviceId('idb-uuid')
    // Wait for async IndexedDB write
    await new Promise((r) => setTimeout(r, 50))
    const idbValue = await readDeviceId()
    expect(idbValue).toBe('idb-uuid')
  })

  it('readDeviceId falls back to IndexedDB when cookie and localStorage are absent', async () => {
    // Write to all layers
    writeDeviceId('idb-only-uuid')
    // Wait for async IndexedDB write to complete
    await new Promise((r) => setTimeout(r, 100))
    // Clear cookie and localStorage
    document.cookie = 'numina_device_id=; path=/; max-age=0'
    localStorage.clear()
    // Should recover from IndexedDB
    const value = await readDeviceId()
    expect(value).toBe('idb-only-uuid')
  })

  it('readDeviceId from IndexedDB backfills localStorage', async () => {
    writeDeviceId('backfill-uuid')
    // Wait for async IndexedDB write to complete
    await new Promise((r) => setTimeout(r, 100))
    document.cookie = 'numina_device_id=; path=/; max-age=0'
    localStorage.clear()
    await readDeviceId()
    expect(localStorage.getItem('numina_device_id')).toBe('backfill-uuid')
  })

  it('clearDeviceId clears IndexedDB', async () => {
    writeDeviceId('to-clear-idb')
    await new Promise((r) => setTimeout(r, 50))
    await clearDeviceId()
    expect(await readDeviceId()).toBeNull()
  })
})
