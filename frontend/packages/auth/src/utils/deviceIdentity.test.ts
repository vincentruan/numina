import { describe, it, expect, beforeEach } from 'vitest'

import { readDeviceId, writeDeviceId, clearDeviceId } from './deviceIdentity'

describe('deviceIdentity', () => {
  beforeEach(() => {
    document.cookie = 'numina_device_id=; path=/; max-age=0'
    localStorage.clear()
  })

  it('returns null when cookie is absent', () => {
    expect(readDeviceId()).toBeNull()
  })

  it('reads the device id from cookie', () => {
    document.cookie = 'numina_device_id=test-uuid-1'
    expect(readDeviceId()).toBe('test-uuid-1')
  })

  it('writeDeviceId sets the cookie', () => {
    writeDeviceId('write-uuid')
    expect(readDeviceId()).toBe('write-uuid')
  })

  it('clearDeviceId removes the cookie', () => {
    writeDeviceId('clear-uuid')
    clearDeviceId()
    expect(readDeviceId()).toBeNull()
  })

  it('handles encoded values in cookie', () => {
    writeDeviceId('uuid-with-special')
    expect(readDeviceId()).toBe('uuid-with-special')
  })

  // --- localStorage fallback tests ---

  it('writeDeviceId also writes to localStorage', () => {
    writeDeviceId('dual-write-uuid')
    expect(localStorage.getItem('numina_device_id')).toBe('dual-write-uuid')
  })

  it('readDeviceId returns cookie value when both cookie and localStorage exist', () => {
    writeDeviceId('cookie-value')
    localStorage.setItem('numina_device_id', 'ls-value')
    expect(readDeviceId()).toBe('cookie-value')
  })

  it('readDeviceId falls back to localStorage when cookie is absent', () => {
    localStorage.setItem('numina_device_id', 'ls-fallback-value')
    expect(readDeviceId()).toBe('ls-fallback-value')
  })

  it('readDeviceId returns null when both cookie and localStorage are empty', () => {
    expect(readDeviceId()).toBeNull()
  })

  it('clearDeviceId removes both cookie and localStorage', () => {
    writeDeviceId('to-clear')
    clearDeviceId()
    expect(readDeviceId()).toBeNull()
    expect(localStorage.getItem('numina_device_id')).toBeNull()
  })

  it('writeDeviceId does not throw when localStorage.setItem fails', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded')
    })
    expect(() => writeDeviceId('quota-uuid')).not.toThrow()
    expect(readDeviceId()).toBe('quota-uuid') // cookie still works
    spy.mockRestore()
  })
})
