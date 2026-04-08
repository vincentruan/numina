/**
 * Tests for useStarField composable
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref, nextTick } from 'vue'
import { useStarField } from '@/composables/useStarField'

// Mock requestAnimationFrame
function mockRAF() {
  const callbacks: Map<number, FrameRequestCallback> = new Map()
  let id = 0

  const raf = (callback: FrameRequestCallback): number => {
    const currentId = ++id
    callbacks.set(currentId, callback)
    return currentId
  }

  const cancelRAF = (id: number) => {
    callbacks.delete(id)
  }

  const runFrame = (time = 16.67) => {
    callbacks.forEach((cb, id) => {
      cb(time)
      callbacks.delete(id)
    })
  }

  return { raf, cancelRAF, runFrame }
}

// Mock canvas context
function createMockCanvas() {
  const ctx = {
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    createLinearGradient: vi.fn(() => ({
      addColorStop: vi.fn(),
    })),
    scale: vi.fn(),
    setTransform: vi.fn(),
  }

  const canvas = {
    getContext: vi.fn(() => ctx),
    getBoundingClientRect: vi.fn(() => ({ width: 800, height: 600 })),
    width: 800,
    height: 600,
  }

  return { canvas, ctx }
}

describe('useStarField', () => {
  let originalRAF: typeof requestAnimationFrame
  let originalCancelRAF: typeof cancelAnimationFrame
  let rafMock: ReturnType<typeof mockRAF>

  beforeEach(() => {
    rafMock = mockRAF()
    originalRAF = window.requestAnimationFrame
    originalCancelRAF = window.cancelAnimationFrame
    window.requestAnimationFrame = rafMock.raf
    window.cancelAnimationFrame = rafMock.cancelRAF

    vi.useFakeTimers()
  })

  afterEach(() => {
    window.requestAnimationFrame = originalRAF
    window.cancelAnimationFrame = originalCancelRAF
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('returns start, stop, and isRunning', () => {
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start, stop, isRunning } = useStarField(canvasRef)

    expect(typeof start).toBe('function')
    expect(typeof stop).toBe('function')
    expect(isRunning.value).toBe(false)
  })

  it('does not start if canvas ref is null', () => {
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start, isRunning } = useStarField(canvasRef)
    start()

    expect(isRunning.value).toBe(false)
  })

  it('starts animation when canvas is available', async () => {
    const { canvas } = createMockCanvas()
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start, isRunning } = useStarField(canvasRef)

    // Set canvas ref
    canvasRef.value = canvas as unknown as HTMLCanvasElement
    await nextTick()

    start()

    expect(isRunning.value).toBe(true)
    expect(canvas.getContext).toHaveBeenCalledWith('2d')
  })

  it('does not start twice if already running', async () => {
    const { canvas } = createMockCanvas()
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start, isRunning } = useStarField(canvasRef)

    canvasRef.value = canvas as unknown as HTMLCanvasElement
    await nextTick()

    start()
    expect(isRunning.value).toBe(true)

    // Second call should be a no-op
    start()
    expect(isRunning.value).toBe(true)
  })

  it('stops animation and cleans up', async () => {
    const { canvas } = createMockCanvas()
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start, stop, isRunning } = useStarField(canvasRef)

    canvasRef.value = canvas as unknown as HTMLCanvasElement
    await nextTick()

    start()
    expect(isRunning.value).toBe(true)

    stop()
    expect(isRunning.value).toBe(false)
  })

  it('handles canvas context failure gracefully', async () => {
    const canvas = {
      getContext: vi.fn(() => null),
      getBoundingClientRect: vi.fn(() => ({ width: 800, height: 600 })),
    }
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start, isRunning } = useStarField(canvasRef)

    canvasRef.value = canvas as unknown as HTMLCanvasElement
    await nextTick()

    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    start()

    expect(isRunning.value).toBe(false)
    expect(consoleSpy).toHaveBeenCalledWith('useStarField: Initialization failed')

    consoleSpy.mockRestore()
  })

  it('handles resize events', async () => {
    const { canvas } = createMockCanvas()
    const canvasRef = ref<HTMLCanvasElement | null>(null)

    const { start } = useStarField(canvasRef)

    canvasRef.value = canvas as unknown as HTMLCanvasElement
    await nextTick()

    start()

    // Trigger resize
    window.dispatchEvent(new Event('resize'))

    // Wait for debounce (150ms)
    vi.advanceTimersByTime(200)

    // getBoundingClientRect should be called again after debounce
    expect(canvas.getBoundingClientRect).toHaveBeenCalled()
  })
})