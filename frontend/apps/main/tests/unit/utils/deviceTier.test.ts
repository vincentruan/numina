/**
 * Tests for device tier detection utility
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getDeviceTier, getTier } from '@/utils/deviceTier'
import type { DeviceTier } from '@/composables/starField.config'

// Mock window and navigator
function mockWindow({
  innerWidth = 1024,
  matchMedia = false,
  hardwareConcurrency = 4,
  maxTouchPoints = 0,
  deviceMemory = undefined as number | undefined,
  ontouchstart = false,
}: {
  innerWidth?: number
  matchMedia?: boolean
  hardwareConcurrency?: number
  maxTouchPoints?: number
  deviceMemory?: number
  ontouchstart?: boolean
} = {}) {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: innerWidth,
  })

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' && matchMedia,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })

  Object.defineProperty(navigator, 'hardwareConcurrency', {
    writable: true,
    configurable: true,
    value: hardwareConcurrency,
  })

  Object.defineProperty(navigator, 'maxTouchPoints', {
    writable: true,
    configurable: true,
    value: maxTouchPoints,
  })

  // @ts-expect-error - deviceMemory is non-standard
  navigator.deviceMemory = deviceMemory

  if (ontouchstart) {
    // @ts-expect-error - adding ontouchstart
    window.ontouchstart = () => {}
  } else {
    // @ts-expect-error - removing ontouchstart
    delete window.ontouchstart
  }
}

describe('getDeviceTier', () => {
  beforeEach(() => {
    vi.stubGlobal('window', window)
    vi.stubGlobal('navigator', navigator)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns low tier when reduced-motion preference is set', () => {
    mockWindow({ matchMedia: true, hardwareConcurrency: 8 })

    const result = getDeviceTier()

    expect(result.tier).toBe('low')
    expect(result.isReducedMotion).toBe(true)
  })

  it('returns low tier when CPU cores <= 2', () => {
    mockWindow({ hardwareConcurrency: 2 })

    const result = getDeviceTier()

    expect(result.tier).toBe('low')
    expect(result.cpuCores).toBe(2)
  })

  it('returns low tier for narrow touch device (< 400px)', () => {
    mockWindow({ innerWidth: 375, maxTouchPoints: 5, ontouchstart: true })

    const result = getDeviceTier()

    expect(result.tier).toBe('low')
    expect(result.viewportWidth).toBe(375)
    expect(result.isTouchDevice).toBe(true)
  })

  it('returns low tier when device memory <= 2 GB', () => {
    mockWindow({ deviceMemory: 2, hardwareConcurrency: 4 })

    const result = getDeviceTier()

    expect(result.tier).toBe('low')
    expect(result.deviceMemory).toBe(2)
  })

  it('returns high tier for 6+ cores desktop (no touch)', () => {
    mockWindow({ hardwareConcurrency: 8, maxTouchPoints: 0, ontouchstart: false })

    const result = getDeviceTier()

    expect(result.tier).toBe('high')
    expect(result.cpuCores).toBe(8)
    expect(result.isTouchDevice).toBe(false)
  })

  it('returns high tier for 4+ cores on large screen desktop', () => {
    mockWindow({
      hardwareConcurrency: 4,
      innerWidth: 1024,
      maxTouchPoints: 0,
      ontouchstart: false,
    })

    const result = getDeviceTier()

    expect(result.tier).toBe('high')
  })

  it('returns medium tier as default for typical mobile', () => {
    mockWindow({ hardwareConcurrency: 4, innerWidth: 600, maxTouchPoints: 5 })

    const result = getDeviceTier()

    expect(result.tier).toBe('medium')
  })

  it('returns medium tier for 3-core device', () => {
    mockWindow({ hardwareConcurrency: 3 })

    const result = getDeviceTier()

    expect(result.tier).toBe('medium')
  })

  it('defaults to 4 cores when hardwareConcurrency is undefined', () => {
    mockWindow()
    Object.defineProperty(navigator, 'hardwareConcurrency', {
      writable: true,
      configurable: true,
      value: undefined,
    })

    const result = getDeviceTier()

    expect(result.cpuCores).toBe(4)
  })

  it('correctly detects touch device via maxTouchPoints', () => {
    mockWindow({ maxTouchPoints: 5, ontouchstart: false })

    const result = getDeviceTier()

    expect(result.isTouchDevice).toBe(true)
  })

  it('correctly detects touch device via ontouchstart', () => {
    mockWindow({ maxTouchPoints: 0, ontouchstart: true })

    const result = getDeviceTier()

    expect(result.isTouchDevice).toBe(true)
  })
})

describe('getTier', () => {
  it('returns just the tier string', () => {
    mockWindow({ hardwareConcurrency: 8, maxTouchPoints: 0 })

    const tier = getTier()

    expect(tier).toBe('high')
    expect(typeof tier).toBe('string')
  })
})