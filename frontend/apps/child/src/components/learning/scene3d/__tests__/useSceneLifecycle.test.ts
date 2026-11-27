import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PerspectiveCamera, Scene, WebGLRenderer } from 'three'
import { tickDriver } from '@/motion/animeDriver'
import { useSceneLifecycle, type SceneLifecycleDeps } from '../useSceneLifecycle'

vi.mock('@/motion/animeDriver', () => ({ tickDriver: vi.fn() }))

const cancelRaf = vi.fn((id: number) => clearTimeout(id))

class MockResizeObserver implements ResizeObserver {
  readonly observe = vi.fn()
  readonly unobserve = vi.fn()
  readonly disconnect = vi.fn()

  constructor(readonly callback: ResizeObserverCallback) {
    observers.push(this)
  }

  trigger(): void {
    this.callback([], this)
  }
}

const observers: MockResizeObserver[] = []

function createDeps(overrides: Partial<SceneLifecycleDeps> = {}) {
  const onFrame = vi.fn()
  const onContextLost = vi.fn()
  const camera = { aspect: 1, updateProjectionMatrix: vi.fn() }
  const renderer = {
    setSize: vi.fn(),
    setPixelRatio: vi.fn(),
    render: vi.fn(),
    dispose: vi.fn(),
    forceContextLoss: vi.fn(),
  }
  const deps: SceneLifecycleDeps = {
    THREE: {} as unknown as typeof import('three'),
    scene: {} as unknown as Scene,
    camera: camera as unknown as PerspectiveCamera,
    renderer: renderer as unknown as WebGLRenderer,
    onFrame,
    onContextLost,
    ...overrides,
  }
  return { deps, onFrame, onContextLost, camera, renderer }
}

function setContainerSize(container: HTMLElement, width: number, height: number): void {
  Object.defineProperty(container, 'clientWidth', {
    configurable: true,
    value: width,
  })
  Object.defineProperty(container, 'clientHeight', {
    configurable: true,
    value: height,
  })
}

function createElements(width = 400, height = 300) {
  const canvas = document.createElement('canvas')
  const container = document.createElement('div')
  setContainerSize(container, width, height)
  return { canvas, container }
}

async function advanceFrames(count: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(16 * count)
}

describe('useSceneLifecycle', () => {
  beforeEach(() => {
    observers.length = 0
    cancelRaf.mockClear()
    vi.mocked(tickDriver).mockClear()
    vi.useFakeTimers()
    vi.stubGlobal(
      'requestAnimationFrame',
      (callback: FrameRequestCallback) =>
        setTimeout(() => callback(performance.now()), 16) as unknown as number,
    )
    vi.stubGlobal('cancelAnimationFrame', cancelRaf)
    vi.stubGlobal('ResizeObserver', MockResizeObserver)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('mount resizes renderer/camera, starts one rAF loop, and advances per frame', async () => {
    const { canvas, container } = createElements()
    const { deps, onFrame, camera, renderer } = createDeps()
    const handle = useSceneLifecycle()

    handle.mount(canvas, container, deps)

    expect(renderer.setSize).toHaveBeenCalledWith(400, 300)
    expect(renderer.setPixelRatio).toHaveBeenCalledWith(1)
    expect(camera.aspect).toBeCloseTo(400 / 300)
    expect(camera.updateProjectionMatrix).toHaveBeenCalledTimes(1)
    expect(handle.isPaused()).toBe(false)
    expect(handle.getFrameCount()).toBe(0)

    await advanceFrames(1)

    expect(onFrame).toHaveBeenCalledTimes(1)
    expect(onFrame.mock.calls[0]?.[0]).toBeTypeOf('number')
    expect(tickDriver).toHaveBeenCalledTimes(1)
    expect(tickDriver).toHaveBeenCalledWith(onFrame.mock.calls[0]?.[0])
    expect(renderer.render).toHaveBeenCalledTimes(1)
    expect(renderer.render).toHaveBeenCalledWith(deps.scene, deps.camera)
    expect(handle.getFrameCount()).toBe(1)

    await advanceFrames(2)

    expect(onFrame).toHaveBeenCalledTimes(3)
    expect(tickDriver).toHaveBeenCalledTimes(3)
    expect(renderer.render).toHaveBeenCalledTimes(3)
    expect(handle.getFrameCount()).toBe(3)

    handle.destroy()
  })

  it('pause cancels the loop and resume starts exactly one loop', async () => {
    const { canvas, container } = createElements()
    const { deps, onFrame } = createDeps()
    const handle = useSceneLifecycle()
    handle.mount(canvas, container, deps)
    await advanceFrames(1)

    handle.pause()
    expect(handle.isPaused()).toBe(true)
    await advanceFrames(4)

    expect(handle.getFrameCount()).toBe(1)
    expect(onFrame).toHaveBeenCalledTimes(1)
    expect(tickDriver).toHaveBeenCalledTimes(1)

    handle.resume()
    expect(handle.isPaused()).toBe(false)
    await advanceFrames(1)
    expect(handle.getFrameCount()).toBe(2)
    expect(onFrame).toHaveBeenCalledTimes(2)
    expect(tickDriver).toHaveBeenCalledTimes(2)

    await advanceFrames(1)
    expect(handle.getFrameCount()).toBe(3)
    expect(onFrame).toHaveBeenCalledTimes(3)
    expect(tickDriver).toHaveBeenCalledTimes(3)

    handle.destroy()
  })

  it('resize observer updates renderer/camera and is disconnected on destroy', async () => {
    vi.stubGlobal('devicePixelRatio', 3)
    const { canvas, container } = createElements()
    const { deps, camera, renderer } = createDeps()
    const handle = useSceneLifecycle()

    handle.mount(canvas, container, deps)

    expect(renderer.setPixelRatio).toHaveBeenCalledWith(2)
    expect(observers).toHaveLength(1)
    expect(observers[0]?.observe).toHaveBeenCalledWith(container)

    setContainerSize(container, 800, 200)
    observers[0]?.trigger()

    expect(renderer.setSize).toHaveBeenLastCalledWith(800, 200)
    expect(camera.aspect).toBeCloseTo(4)
    expect(camera.updateProjectionMatrix).toHaveBeenCalledTimes(2)

    handle.destroy()
    expect(observers[0]?.disconnect).toHaveBeenCalledTimes(1)
  })

  it('context lost handler stops the loop and calls onContextLost once', async () => {
    const { canvas, container } = createElements()
    const { deps, onContextLost } = createDeps()
    const handle = useSceneLifecycle()
    handle.mount(canvas, container, deps)
    await advanceFrames(1)

    const event = new Event('webglcontextlost', { cancelable: true })
    canvas.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(true)
    expect(onContextLost).toHaveBeenCalledTimes(1)
    expect(onContextLost).toHaveBeenCalledWith(event)
    expect(handle.isPaused()).toBe(true)

    await advanceFrames(4)
    expect(handle.getFrameCount()).toBe(1)
    expect(tickDriver).toHaveBeenCalledTimes(1)

    canvas.dispatchEvent(new Event('webglcontextlost', { cancelable: true }))
    expect(onContextLost).toHaveBeenCalledTimes(1)

    handle.destroy()
  })

  it('setDocumentVisibilityPaused composes with pause/resume: hidden stays paused after visible', async () => {
    const { canvas, container } = createElements()
    const { deps, onFrame } = createDeps()
    const handle = useSceneLifecycle()
    handle.mount(canvas, container, deps)
    await advanceFrames(1)

    handle.setDocumentVisibilityPaused(true)
    expect(handle.isPaused()).toBe(true)
    await advanceFrames(4)
    expect(handle.getFrameCount()).toBe(1)

    handle.resume()
    expect(handle.isPaused()).toBe(true)
    await advanceFrames(4)
    expect(handle.getFrameCount()).toBe(1)
    expect(onFrame).toHaveBeenCalledTimes(1)

    handle.setDocumentVisibilityPaused(false)
    expect(handle.isPaused()).toBe(false)
    await advanceFrames(1)
    expect(handle.getFrameCount()).toBe(2)
    expect(onFrame).toHaveBeenCalledTimes(2)

    handle.destroy()
  })

  it('20 mount/destroy cycles leave no rAF, listeners, or observer', () => {
    const cycles = Array.from({ length: 20 }, () => {
      const { canvas, container } = createElements()
      const { deps } = createDeps()
      const removeListener = vi.spyOn(canvas, 'removeEventListener')
      const handle = useSceneLifecycle()
      handle.mount(canvas, container, deps)
      return { handle, canvas, removeListener }
    })

    expect(observers).toHaveLength(20)
    expect(cancelRaf).not.toHaveBeenCalled()

    for (const cycle of cycles) {
      cycle.handle.destroy()
      expect(cycle.handle.getFrameCount()).toBe(0)
      expect(cycle.handle.isPaused()).toBe(true)
      expect(cycle.removeListener).toHaveBeenCalledWith('webglcontextlost', expect.any(Function))
    }

    expect(observers.every((observer) => observer.disconnect.mock.calls.length === 1)).toBe(true)
    expect(cancelRaf).toHaveBeenCalledTimes(20)
    expect(vi.getTimerCount()).toBe(0)

    for (const cycle of cycles) {
      cycle.canvas.dispatchEvent(new Event('webglcontextlost', { cancelable: true }))
    }
    expect(cycles.some((cycle) => cycle.handle.isPaused())).toBe(true)
  })
})
