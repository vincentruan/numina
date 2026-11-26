<template>
  <div ref="containerRef" class="castle-panorama">
    <canvas ref="canvasRef" class="castle-panorama__canvas" />

    <!-- Tower labels overlay (HTML, cheaper than sprites) -->
    <div class="castle-panorama__labels" aria-hidden="true">
      <span
        v-for="label in towerLabels"
        :key="label.subject"
        class="castle-panorama__label"
        :style="label.style"
      >
        {{ label.icon }} {{ label.name }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'CastlePanorama' })

import { ref, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Mesh } from 'three'
import type { CastleIndex, CastleTower, CastleWindow } from '@/api/learning'
import { getContinentTheme } from '@/data/continentThemes'
import { tickDriver } from '@/motion/animeDriver'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { CameraController, frameCastle } from './CameraController'
import {
  buildCastleScene,
  disposeScene,
  getTowerCenter,
  getCastleBounds,
  type CastleScene,
} from './CastleSceneBuilder'

const props = defineProps<{
  castle: CastleIndex
  /** Topic id from `?new=` — its brick drops in when the new floor renders. */
  newTopicId?: string | null
  newSubject?: string | null
  newDomain?: string | null
}>()

const emit = defineEmits<{
  towerSelect: [subject: string]
  windowSelect: [window: CastleWindow]
}>()

const { t } = useI18n()
const reducedMotion = useReducedMotion()

const containerRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

let scene: CastleScene | null = null
let cameraController: CameraController | null = null
let animFrameId = 0
let renderer: unknown = null
let camera: unknown = null
let threeScene: unknown = null
let lastFrameTime = 0
let raycaster: unknown = null
let pointerNdc: { x: number; y: number } | null = null
let dropAbort: AbortController | null = null

/** Tower labels projected to screen — computed during render. */
const towerLabels = ref<Array<{ subject: string; icon: string; name: string; style: Record<string, string> }>>([])

/** Subject display names for labels. */
const subjectLabel = computed(() => {
  const map: Record<string, string> = {}
  props.castle.towers.forEach((tw: CastleTower) => {
    map[tw.subject] = t(`learning.subject.${tw.subject}`, tw.subject)
  })
  return map
})

async function mount(): Promise<void> {
  const canvas = canvasRef.value
  const container = containerRef.value
  if (!canvas || !container) return

  const THREE = await import('three')
  const { initRapier } = await import('@/physics/rapierWorld')
  await initRapier()

  const width = container.clientWidth
  const height = container.clientHeight

  // Scene
  const newScene = new THREE.Scene()
  newScene.background = null // transparent — clay canvas shows through

  // Camera
  const newCamera = new THREE.PerspectiveCamera(55, width / height, 0.1, 200)
  camera = newCamera

  // Renderer
  const newRenderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
  })
  newRenderer.setSize(width, height)
  newRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  newRenderer.shadowMap.enabled = false
  renderer = newRenderer
  threeScene = newScene

  // Lights
  newScene.add(new THREE.AmbientLight(0xffffff, 0.75))
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.7)
  dirLight.position.set(5, 10, 8)
  newScene.add(dirLight)

  // Build castle
  scene = buildCastleScene(props.castle)
  newScene.add(scene.root)

  // Drop the newly mastered brick (F1). One brick only — the one on the
  // floor that owns `?new=`. Physics runs; the visual bounce respects
  // reduced-motion.
  if (props.newTopicId && props.newSubject) {
    void dropNewBrick()
  }

  // Camera controller — framed to the castle's real bounds so tall towers
  // are not clipped and a small castle is not a speck.
  const bounds = getCastleBounds(scene)
  cameraController = frameCastle(newCamera, bounds)
  cameraController.enable(canvas)

  // Raycaster for picking
  raycaster = new THREE.Raycaster()

  // Pointer tracking for tap-to-select
  canvas.addEventListener('pointerup', onPointerUp)

  // WebGL context loss → notify parent for fallback
  canvas.addEventListener('webglcontextlost', onContextLost)

  // Start loop
  lastFrameTime = performance.now()
  animFrameId = requestAnimationFrame(renderLoop)
}

function onPointerUp(e: PointerEvent): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  pointerNdc = {
    x: ((e.clientX - rect.left) / rect.width) * 2 - 1,
    y: -((e.clientY - rect.top) / rect.height) * 2 + 1,
  }
}

function onContextLost(e: Event): void {
  e.preventDefault()
  console.error('[CastlePanorama] WebGL context lost')
  cancelAnimationFrame(animFrameId)
}

/**
 * Animate the single new brick for `?new=` — the last brick on the floor
 * that owns the new topic. Everything else stays static (F1/R6: only one
 * brick ever animates).
 */
async function dropNewBrick(): Promise<void> {
  if (!scene || !camera) return

  const subject = props.newSubject
  const anchor = props.newDomain ?? ''
  const tower = props.castle.towers.find((tw) => tw.subject === subject)
  if (!subject || !tower) return

  const floorIndex = tower.floors.findIndex((f) => (f.domain || '') === anchor)
  if (floorIndex < 0) return

  const group = scene.towers.get(subject)
  if (!group) return

  // The floor group sits at y = floorIndex * FLOOR_HEIGHT + FLOOR_HEIGHT/2
  const floorGroup = group.children.find(
    (child) => (child.userData as { floorIndex?: number }).floorIndex === floorIndex,
  )
  if (!floorGroup) return

  const bricks = floorGroup.children.filter(
    (child) => (child.userData as { type?: string }).type === 'brick',
  )
  if (bricks.length === 0) return

  const brick = bricks[bricks.length - 1] as Mesh
  const { getWorld } = await import('@/physics/rapierWorld')
  const { animateBrickDrop } = await import('./BrickDropAnimation')
  const world = getWorld()

  // World position: floor group is a child of the tower group
  const targetWorld = brick.position.clone()
  floorGroup.localToWorld(targetWorld)

  // Detach from the floor group so physics can drive it in world space
  floorGroup.remove(brick)
  if (scene) scene.root.add(brick)
  brick.position.copy(targetWorld)
  brick.position.y += 0.4

  dropAbort?.abort()
  dropAbort = new AbortController()

  try {
    await animateBrickDrop(brick, targetWorld, world, {
      reducedMotion: reducedMotion.value,
      signal: dropAbort.signal,
    })
  } catch {
    // Drop aborted or world freed on teardown — the brick keeps its target transform
  }
}

function renderLoop(now: number): void {
  const dt = (now - lastFrameTime) / 1000
  lastFrameTime = now

  tickDriver(now)

  // Handle pending tap
  if (pointerNdc && scene && camera && raycaster) {
    handlePick()
    pointerNdc = null
  }

  // Update tower label positions
  updateLabels()

  if (renderer && threeScene && camera) {
    const r = renderer as { render: (s: unknown, c: unknown) => void }
    r.render(threeScene, camera)
  }

  void dt
  animFrameId = requestAnimationFrame(renderLoop)
}

function handlePick(): void {
  if (!pointerNdc || !camera || !raycaster || !scene) return

  const THREE_raycaster = raycaster as {
    setFromCamera: (coords: { x: number; y: number }, cam: unknown) => void
    intersectObjects: (objs: unknown[], recursive: boolean) => Array<{ object: unknown }>
  }
  THREE_raycaster.setFromCamera(pointerNdc, camera)

  // Windows first (higher priority — smaller targets)
  const windowHits = THREE_raycaster.intersectObjects(scene.windows, false)
  if (windowHits.length > 0) {
    const hit = windowHits[0].object as { userData: { window?: CastleWindow } }
    if (hit.userData.window) {
      emit('windowSelect', hit.userData.window)
      return
    }
  }

  // Then towers
  const towerMeshes: unknown[] = []
  scene.towers.forEach((group) => {
    group.traverse((obj) => {
      if ((obj as { type?: string }).type === 'Mesh') towerMeshes.push(obj)
    })
  })
  const towerHits = THREE_raycaster.intersectObjects(towerMeshes, false)
  if (towerHits.length > 0) {
    const hit = towerHits[0].object as { userData: { subject?: string } }
    if (hit.userData.subject) {
      emit('towerSelect', hit.userData.subject)
    }
  }
}

function updateLabels(): void {
  if (!scene || !camera || !containerRef.value) return
  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  // project() lives on Vector3 and takes the camera — projecting the
  // camera's own position reads `undefined.elements` and throws.
  const cam = camera as { updateMatrixWorld: () => void }
  cam.updateMatrixWorld()

  const newLabels: Array<{ subject: string; icon: string; name: string; style: Record<string, string> }> = []

  // Neighbouring towers are only ~4 units apart, so their labels collide at
  // this zoom. Stagger alternate labels vertically instead of letting them
  // stack into an unreadable clump.
  let index = 0

  scene.towers.forEach((group, subject) => {
    const center = getTowerCenter(group)
    center.y = group.children.length * 1
    center.project(camera as Parameters<typeof center.project>[0])

    if (center.z > 1) return // Behind the camera

    const screenX = (center.x * 0.5 + 0.5) * width
    const screenY = (-center.y * 0.5 + 0.5) * height
    const stagger = index % 2 === 0 ? 0 : 26
    index++

    const theme = getContinentTheme(subject)
    newLabels.push({
      subject,
      icon: theme.icon,
      name: subjectLabel.value[subject] ?? subject,
      style: {
        left: `${screenX}px`,
        top: `${screenY - stagger}px`,
      },
    })
  })

  towerLabels.value = newLabels
}

function resize(): void {
  const container = containerRef.value
  if (!container || !renderer || !camera) return

  const width = container.clientWidth
  const height = container.clientHeight

  const r = renderer as { setSize: (w: number, h: number) => void }
  r.setSize(width, height)
  const cam = camera as { aspect: number; updateProjectionMatrix: () => void }
  cam.aspect = width / height
  cam.updateProjectionMatrix()
}

function teardown(): void {
  cancelAnimationFrame(animFrameId)
  animFrameId = 0

  // Stop any in-flight brick drop before the world is torn down
  dropAbort?.abort()
  dropAbort = null

  const canvas = canvasRef.value
  if (canvas) {
    canvas.removeEventListener('pointerup', onPointerUp)
    canvas.removeEventListener('webglcontextlost', onContextLost)
  }
  window.removeEventListener('resize', resize)

  if (cameraController) {
    cameraController.dispose(canvas ?? undefined)
    cameraController = null
  }

  if (scene) {
    disposeScene(scene)
    scene = null
  }

  if (renderer) {
    const r = renderer as { dispose: () => void; forceContextLoss: () => void }
    r.dispose()
    r.forceContextLoss()
    renderer = null
  }

  threeScene = null
  camera = null
}

onMounted(async () => {
  await mount()
  window.addEventListener('resize', resize)
})

onActivated(() => {
  if (renderer && !animFrameId) {
    lastFrameTime = performance.now()
    animFrameId = requestAnimationFrame(renderLoop)
  }
})

onDeactivated(() => {
  cancelAnimationFrame(animFrameId)
  animFrameId = 0
})

onBeforeUnmount(() => {
  teardown()
})

defineExpose({
  /** Transition the camera to focus on a tower (called by parent after towerSelect). */
  focusTower: async (subject: string): Promise<void> => {
    if (!cameraController || !scene) return
    const group = scene.towers.get(subject)
    if (!group) return
    const center = getTowerCenter(group)
    const floors = props.castle.towers.find((tw) => tw.subject === subject)?.floors.length ?? 1
    await cameraController.transitionToTower(center, floors * 2)
  },
  /** Return to the full panorama view. */
  resetCamera: async (): Promise<void> => {
    if (!cameraController) return
    await cameraController.transitionToPanorama()
  },
})
</script>

<style scoped>
.castle-panorama {
  position: relative;
  width: 100%;
  height: 100%;
  touch-action: none;
}

.castle-panorama__canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.castle-panorama__labels {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.castle-panorama__label {
  position: absolute;
  transform: translate(-50%, -100%);
  font-size: 13px;
  color: var(--color-ink);
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill, 999px);
  padding: 2px 10px;
  white-space: nowrap;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

[data-theme='dark'] .castle-panorama__label {
  background: var(--color-surface-card);
  color: var(--color-ink);
}
</style>
