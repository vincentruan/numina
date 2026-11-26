/**
 * materials.test.ts — tests for clay.css token → three.js Color bridge.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock three.js Color — needs to be a constructor
const mockClone = vi.fn()
const MockColor = vi.fn().mockImplementation(function (this: { input: string | number; isColor: boolean; clone: () => unknown }, value: string | number) {
  this.input = value
  this.isColor = true
  this.clone = mockClone.mockReturnValue(this)
  return this
})

vi.mock('three', () => ({
  Color: MockColor,
}))

describe('materials', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    MockColor.mockClear()
    mockClone.mockClear()

    // Set up CSS variables on documentElement
    const style: Record<string, string> = {
      '--color-primary': '#e8b94a',
      '--color-canvas': '#fffaf0',
      '--color-ink': '#0a0a0a',
      '--color-body': '#3d3d3d',
      '--color-brand-pink': '#ff6b9d',
      '--ocean-sea-color': '#4a90d9',
    }

    vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      getPropertyValue: (prop: string) => style[prop] || '',
    } as unknown as CSSStyleDeclaration)
  })

  it('clayColor returns a Color from a valid token', async () => {
    const { clayColor } = await import('./materials')
    const result = clayColor('primary')

    expect(result).toBeDefined()
    expect(result.isColor).toBe(true)
    expect(MockColor).toHaveBeenCalledWith('#e8b94a')
  })

  it('clayColor reads CSS variable for each known token', async () => {
    const { clayColor } = await import('./materials')

    clayColor('canvas')
    expect(MockColor).toHaveBeenCalledWith('#fffaf0')

    clayColor('ink')
    expect(MockColor).toHaveBeenCalledWith('#0a0a0a')

    clayColor('brand-pink')
    expect(MockColor).toHaveBeenCalledWith('#ff6b9d')

    clayColor('ocean-sea')
    expect(MockColor).toHaveBeenCalledWith('#4a90d9')
  })

  it('clayColor returns gray fallback for unknown token', async () => {
    const { clayColor } = await import('./materials')
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    clayColor('nonexistent-token')

    // Should fall back to gray (0x808080)
    expect(MockColor).toHaveBeenCalledWith(0x808080)
    expect(warnSpy).toHaveBeenCalledWith('[materials] Unknown clay token: "nonexistent-token"')

    warnSpy.mockRestore()
  })

  it('clayColor returns gray fallback when CSS var is empty', async () => {
    // Override getComputedStyle to return empty
    vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      getPropertyValue: () => '',
    } as unknown as CSSStyleDeclaration)

    const { clayColor } = await import('./materials')
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    clayColor('primary')

    // Should fall back to gray (0x808080)
    expect(MockColor).toHaveBeenCalledWith(0x808080)
    expect(warnSpy).toHaveBeenCalledWith('[materials] CSS var "--color-primary" is empty')

    warnSpy.mockRestore()
  })

  it('clayColor caches results for repeated calls', async () => {
    const { clayColor } = await import('./materials')

    clayColor('primary')
    clayColor('primary')
    clayColor('primary')

    // Color constructor should only be called once due to caching
    expect(MockColor).toHaveBeenCalledTimes(1)
  })

  it('clayColor returns cloned Color to prevent mutation', async () => {
    const { clayColor } = await import('./materials')

    clayColor('primary')
    clayColor('primary')

    // clone() should be called each time
    expect(mockClone).toHaveBeenCalledTimes(2)
  })

  it('invalidateCache clears the cache', async () => {
    const { clayColor, invalidateCache } = await import('./materials')

    // Populate cache
    clayColor('primary')
    expect(MockColor).toHaveBeenCalledTimes(1)

    // Invalidate
    invalidateCache()

    // Next call should re-create
    clayColor('primary')
    expect(MockColor).toHaveBeenCalledTimes(2)
  })

  it('invalidateCache does not throw when cache is empty', async () => {
    const { invalidateCache } = await import('./materials')
    expect(() => invalidateCache()).not.toThrow()
  })
})
