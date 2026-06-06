import { describe, it, expect, beforeEach } from 'vitest'

import { readDeviceId, writeDeviceId, clearDeviceId } from './deviceIdentity'

describe('deviceIdentity', () => {
  beforeEach(() => {
    document.cookie = 'numina_device_id=; path=/; max-age=0'
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
})
