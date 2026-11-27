/**
 * Shared single-loop lifecycle for 3D scenes.
 *
 * The handle owns the only rAF loop, so it is the only caller of `tickDriver`.
 * Pause (manual/deactivation) and document visibility are independent flags:
 * the loop runs only when both are clear and the handle is mounted.
 */
import type { PerspectiveCamera, Scene, WebGLRenderer } from 'three'
import { tickDriver } from '@/motion/animeDriver'

export interface SceneLifecycleDeps {
  THREE: typeof import('three')
  scene: Scene
  camera: PerspectiveCamera
  renderer: WebGLRenderer
  onFrame?: (now: number) => void
  onContextLost?: (event: Event) => void
}

export interface SceneLifecycleHandle {
  mount(canvas: HTMLCanvasElement, container: HTMLElement, deps: SceneLifecycleDeps): void
  pause(): void
  resume(): void
  destroy(): void
  setDocumentVisibilityPaused(paused: boolean): void
  isPaused(): boolean
  getFrameCount(): number
}

export function useSceneLifecycle(): SceneLifecycleHandle {
  let currentDeps: SceneLifecycleDeps | null = null
  let mounted = false
  let destroyed = false
  let manualPaused = false
  let documentHiddenPaused = false
  let frameId = 0
  let frameCount = 0
  let observer: ResizeObserver | null = null
  let canvas: HTMLCanvasElement | null = null
  let contextLostHandler: ((event: Event) => void) | null = null

  function canRun(): boolean {
    return mounted && !destroyed && !manualPaused && !documentHiddenPaused
  }

  function stopLoop(): void {
    if (frameId) {
      cancelAnimationFrame(frameId)
      frameId = 0
    }
  }

  function resize(width: number, height: number): void {
    const deps = currentDeps
    if (!deps || width <= 0 || height <= 0) return

    deps.renderer.setSize(width, height)
    deps.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    deps.camera.aspect = width / height
    deps.camera.updateProjectionMatrix()
  }

  function renderLoop(now: number): void {
    frameId = 0
    if (!canRun()) return

    const deps = currentDeps
    if (!deps) return

    frameCount++
    deps.onFrame?.(now)
    tickDriver(now)
    deps.renderer.render(deps.scene, deps.camera)

    if (canRun()) {
      frameId = requestAnimationFrame(renderLoop)
    }
  }

  function startLoop(): void {
    if (!canRun() || frameId) return
    frameId = requestAnimationFrame(renderLoop)
  }

  function mount(
    targetCanvas: HTMLCanvasElement,
    container: HTMLElement,
    deps: SceneLifecycleDeps,
  ): void {
    if (mounted || destroyed) return

    mounted = true
    currentDeps = deps
    canvas = targetCanvas
    frameCount = 0
    manualPaused = false
    documentHiddenPaused = false

    resize(container.clientWidth, container.clientHeight)
    observer = new ResizeObserver(() => {
      resize(container.clientWidth, container.clientHeight)
    })
    observer.observe(container)

    contextLostHandler = (event: Event) => {
      if (!mounted || destroyed) return
      event.preventDefault()
      manualPaused = true
      stopLoop()
      if (canvas && contextLostHandler) {
        canvas.removeEventListener('webglcontextlost', contextLostHandler)
      }
      contextLostHandler = null
      deps.onContextLost?.(event)
    }
    canvas.addEventListener('webglcontextlost', contextLostHandler)

    startLoop()
  }

  function pause(): void {
    manualPaused = true
    stopLoop()
  }

  function resume(): void {
    manualPaused = false
    startLoop()
  }

  function setDocumentVisibilityPaused(paused: boolean): void {
    documentHiddenPaused = paused
    if (paused) stopLoop()
    else startLoop()
  }

  function destroy(): void {
    if (destroyed) return

    stopLoop()
    mounted = false
    destroyed = true
    manualPaused = true
    documentHiddenPaused = true

    observer?.disconnect()
    observer = null

    if (canvas && contextLostHandler) {
      canvas.removeEventListener('webglcontextlost', contextLostHandler)
    }
    canvas = null
    contextLostHandler = null
    currentDeps = null
    frameCount = 0
  }

  return {
    mount,
    pause,
    resume,
    destroy,
    setDocumentVisibilityPaused,
    isPaused: () => !canRun(),
    getFrameCount: () => frameCount,
  }
}
