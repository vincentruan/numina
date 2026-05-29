import { describe, it, expect, beforeEach } from 'vitest'
import { readDeviceId, writeDeviceId, clearDeviceId } from './deviceIdentity'

describe('deviceIdentity', () => {
  beforeEach(() => {
    localStorage.clear()
    document.cookie = 'numina_device_id=; Path=/; Max-Age=0'
  })

  it('readDeviceId returns null when nothing stored', () => {
    expect(readDeviceId()).toBeNull()
  })

  it('readDeviceId reads from cookie and backfills localStorage', () => {
    document.cookie = 'numina_device_id=test-uuid-123; Path=/'
    const result = readDeviceId()
    expect(result).toBe('test-uuid-123')
    expect(localStorage.getItem('_numina_device_id')).toBe('test-uuid-123')
  })

  it('readDeviceId falls back to localStorage', () => {
    localStorage.setItem('_numina_device_id', 'ls-uuid-456')
    expect(readDeviceId()).toBe('ls-uuid-456')
  })

  it('writeDeviceId stores to localStorage', () => {
    writeDeviceId('written-uuid-789')
    expect(localStorage.getItem('_numina_device_id')).toBe('written-uuid-789')
  })

  it('clearDeviceId removes both cookie and localStorage', () => {
    localStorage.setItem('_numina_device_id', 'to-clear')
    document.cookie = 'numina_device_id=to-clear; Path=/'
    clearDeviceId()
    expect(localStorage.getItem('_numina_device_id')).toBeNull()
    expect(document.cookie).not.toContain('numina_device_id')
  })
})
