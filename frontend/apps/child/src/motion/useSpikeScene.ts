/**
 * useSpikeScene — T0 spike validation composable.
 *
 * Creates a minimal 3D scene that exercises:
 * - three.js: renderer, scene, camera, mesh
 * - rapier: physics world with a falling ball
 * - anime.js: island bobbing animation via child timeline
 *
 * Used exclusively for T0 spike validation (bundle, fps, integration, degradation, memory).
 */
import { ref, onBeforeUnmount, type Ref } from 'vue'
import type { Scene, PerspectiveCamera, WebGLRenderer, Mesh, Material } from 'three'
import type { World } from '@dimforge/rapier3d-compat'
import type { Timeline } from 'animejs'
import { tickDriver, createChildTimeline, revertAll } from './animeDriver'
import { initRapier, getWorld, stepPhysics, destroyWorld, syncMeshesFromBodies, removeBody } from '@/physics/rapierWorld'
import { createDynamicObject, createStaticGround, type BodyResult } from '@/physics/islandBody'

export interface SpikeSceneState {
  /** Whether the scene is fully initialized (all libs loaded). */
  ready: boolean
  /** Whether WebGL is available. */
  webglAvailable: boolean
  /** Current FPS (updated every second). */
  fps: number
  /** Whether the scene is in degraded mode (no WebGL). */
  degraded: boolean
}

export interface SpikeSceneHandle {
  state: Ref<SpikeSceneState>
  /** Mount the scene to a canvas element. Returns false if WebGL unavailable. */
  mount(canvas: HTMLCanvasElement): Promise<boolean>
  /** Pause the render loop (tab hidden). */
  pause(): void
  /** Resume the render loop (tab visible). */
  resume(): void
  /** Full teardown — frees all GPU/physics/animation resources. */
  destroy(): void
  /** Get current frame time for benchmarking. */
  getFrameTimes(): number[]
}

/**
 * Check if WebGL is available without creating a context.
 */
export function isWebGLAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl2') || canvas.getContext('webgl'))
    )
  } catch {
    return false
  }
}

/**
 * Create the spike scene handle.
 * Does NOT mount until `mount(canvas)` is called.
 */
export function useSpikeScene(): SpikeSceneHandle {
  const state = ref<SpikeSceneState>({
    ready: false,
    webglAvailable: isWebGLAvailable(),
    fps: 0,
    degraded: false,
  })

  let renderer: WebGLRenderer | null = null
  let scene: Scene | null = null
  let camera: PerspectiveCamera | null = null
  let ballMesh: Mesh | null = null
  let islandMesh: Mesh | null = null
  let ballBody: BodyResult | null = null
  let groundBody: BodyResult | null = null
  let world: World | null = null
  let rapierReady = false
  let islandTimeline: Timeline | null = null
  let animFrameId = 0
  let paused = false
  let lastFrameTime = 0
  let frameCount = 0
  let fpsAccum = 0
  let lastFpsUpdate = 0
  const frameTimes: number[] = []
  const MAX_FRAME_SAMPLES = 120

  async function mount(canvas: HTMLCanvasElement): Promise<boolean> {
    if (!state.value.webglAvailable) {
      state.value.degraded = true
      return false
    }

    try {
      // Dynamic imports — validates T0.1 (code splitting)
      const [
        { Scene, PerspectiveCamera, WebGLRenderer, BoxGeometry, SphereGeometry, MeshStandardMaterial, Mesh, AmbientLight, DirectionalLight },
      ] = await Promise.all([
        import('three'),
      ])

      // Init rapier
      await initRapier()
      rapierReady = true

      // Create three.js scene
      scene = new Scene()
      camera = new PerspectiveCamera(60, canvas.clientWidth / canvas.clientHeight, 0.1, 100)
      camera.position.set(0, 5, 10)
      camera.lookAt(0, 0, 0)

      renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true })
      renderer.setSize(canvas.clientWidth, canvas.clientHeight)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

      // Lights
      const ambient = new AmbientLight(0xffffff, 0.6)
      const directional = new DirectionalLight(0xffffff, 0.8)
      directional.position.set(5, 10, 5)
      scene.add(ambient, directional)

      // Island (kinematic box — moved by anime)
      const islandGeo = new BoxGeometry(4, 0.5, 4)
      const islandMat = new MeshStandardMaterial({ color: 0x7ec8e3 })
      islandMesh = new Mesh(islandGeo, islandMat)
      islandMesh.position.set(0, 0, 0)
      scene.add(islandMesh)

      // Ground for physics (at y=-2)
      world = getWorld()
      groundBody = createStaticGround(world, -2)

      // Ball (dynamic — falls under gravity)
      ballBody = createDynamicObject(world, {
        position: { x: 0, y: 3, z: 0 },
        radius: 0.3,
        mass: 1,
        restitution: 0.5,
      })

      // Visual mesh for ball
      const ballGeo = new SphereGeometry(0.3, 16, 16)
      const ballMat = new MeshStandardMaterial({ color: 0xff6b6b })
      ballMesh = new Mesh(ballGeo, ballMat)
      scene.add(ballMesh)

      // Anime timeline for island bobbing (looping via keyframes)
      islandTimeline = createChildTimeline()
      islandTimeline.add(
        islandMesh.position,
        { y: [0, 0.3, 0], duration: 2000, ease: 'inOutSine', loop: true },
        0,
      )

      state.value.ready = true
      state.value.degraded = false

      // Start render loop
      lastFrameTime = performance.now()
      lastFpsUpdate = lastFrameTime
      requestAnimationFrame(renderLoop)

      return true
    } catch (err) {
      console.error('[SpikeScene] Mount failed:', err)
      state.value.degraded = true
      return false
    }
  }

  function renderLoop(now: number): void {
    if (paused) return

    const dt = (now - lastFrameTime) / 1000
    lastFrameTime = now

    // Track frame times for benchmarking
    frameTimes.push(dt * 1000)
    if (frameTimes.length > MAX_FRAME_SAMPLES) frameTimes.shift()

    // FPS counter
    frameCount++
    fpsAccum += dt
    if (now - lastFpsUpdate >= 1000) {
      state.value.fps = Math.round(frameCount / fpsAccum)
      frameCount = 0
      fpsAccum = 0
      lastFpsUpdate = now
    }

    // Tick anime driver (single clock)
    tickDriver(now)

    // Step physics
    if (rapierReady && world) {
      stepPhysics(dt, world)

      // Sync ball mesh from physics body
      const currentBallBody = ballBody
      const currentBallMesh = ballMesh
      if (currentBallBody && currentBallMesh) {
        syncMeshesFromBodies((body, _alpha) => {
          if (body === currentBallBody.body) {
            const pos = body.translation()
            currentBallMesh.position.set(pos.x, pos.y, pos.z)
          }
        }, world)
      }
    }

    // Render
    if (renderer && scene && camera) {
      renderer.render(scene, camera)
    }

    animFrameId = requestAnimationFrame(renderLoop)
  }

  function pause(): void {
    paused = true
    if (animFrameId) {
      cancelAnimationFrame(animFrameId)
      animFrameId = 0
    }
  }

  function resume(): void {
    if (paused && state.value.ready) {
      paused = false
      lastFrameTime = performance.now()
      animFrameId = requestAnimationFrame(renderLoop)
    }
  }

  function destroy(): void {
    pause()

    // Revert anime timelines
    if (islandTimeline) {
      islandTimeline.revert()
      islandTimeline = null
    }
    revertAll()

    // Dispose three.js resources
    if (ballMesh) {
      ballMesh.geometry.dispose()
      ;(ballMesh.material as Material).dispose()
      ballMesh = null
    }
    if (islandMesh) {
      islandMesh.geometry.dispose()
      ;(islandMesh.material as Material).dispose()
      islandMesh = null
    }
    if (scene) {
      scene.clear()
      scene = null
    }
    if (renderer) {
      renderer.dispose()
      renderer.forceContextLoss()
      renderer = null
    }
    camera = null

    // Cleanup physics
    if (ballBody && world) {
      removeBody(world, ballBody.body)
      ballBody = null
    }
    if (groundBody && world) {
      removeBody(world, groundBody.body)
      groundBody = null
    }
    destroyWorld()
    rapierReady = false

    state.value.ready = false
    frameTimes.length = 0
  }

  function getFrameTimes(): number[] {
    return [...frameTimes]
  }

  // Auto-cleanup on unmount
  onBeforeUnmount(() => {
    destroy()
  })

  return {
    state,
    mount,
    pause,
    resume,
    destroy,
    getFrameTimes,
  }
}
