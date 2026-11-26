<template>
  <div
    v-if="failed"
    class="knowledge-ocean-3d knowledge-ocean-3d--fallback"
    role="status"
  >
    <p class="knowledge-ocean-3d__message">
      {{
        t(
          'learning.ocean3d.fallback',
          '3D view is unavailable here. The standard ocean view is still available.',
        )
      }}
    </p>
  </div>
  <div v-else ref="containerRef" class="knowledge-ocean-3d">
    <canvas
      ref="canvasRef"
      class="knowledge-ocean-3d__canvas"
      :aria-label="t('learning.ocean.a11yLabel', 'Knowledge ocean map')"
      @dblclick="onDoubleClick"
      @pointerup="onPointerUp"
      @touchstart="onTouchStart"
      @touchmove="onTouchMove"
      @touchend="onTouchEnd"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'KnowledgeOcean3D' })

import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  onActivated,
  onDeactivated,
} from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  Object3D,
  PerspectiveCamera,
  Raycaster,
  Scene,
  WebGLRenderer,
} from 'three'
import { isWebGLAvailable } from '@/composables/useWebGLAvailable'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { useSceneLifecycle } from '../scene3d/useSceneLifecycle'
import type {
  OceanDomain,
  OceanSubject,
} from '@/components/learning/KnowledgeOcean.vue'
import { layoutOceanDomains, layoutOceanNodes } from './oceanGeometry'
import { buildOceanScene, type OceanScene } from './OceanSceneBuilder'
import { createOceanWater, type OceanWater } from './OceanWater'
import { createOceanLabels, type OceanLabelSet } from './OceanLabels'
import type { OceanCameraController } from './OceanCameraController'

/** Node reference emitted with navigation events and accepted by the page. */
export interface OceanNodeRef {
  id: string
  subject?: string
  x: number
  z: number
  worldRadius: number
}

const props = defineProps<{
  subjects: OceanSubject[]
  domains: OceanDomain[]
  selectedSubject: string
  selectedDomain: string
  selectedTopicLevel: boolean
}>()

const emit = defineEmits<{
  previewSubject: [subject: string]
  selectSubject: [subject: string]
  previewDomain: [payload: { subject: string; domain: string }]
  selectDomain: [payload: { subject: string; domain: string }]
  zoomOut: []
  fallback: []
  interacted: []
  oceanNavigation: [OceanNodeRef | null]
}>()

const { t } = useI18n()
const reducedMotion = useReducedMotion()

const containerRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const failed = ref(false)

const handle = useSceneLifecycle()
let lifecycleMounted = false
let contextLost = false
let disposed = false
let THREE: typeof import('three') | null = null
let ndc: import('three').Vector2 | null = null
let scene: Scene | null = null
let camera: PerspectiveCamera | null = null
let raycaster: Raycaster | null = null
let renderer: WebGLRenderer | null = null
let water: OceanWater | null = null
let labels: OceanLabelSet | null = null
let oceanScene: OceanScene | null = null
let cameraController: OceanCameraController | null = null

/** Which level's tiles are on the canvas. Derived from page selection. */
const sceneLevel = computed<'subject' | 'domain'>(() =>
  props.selectedSubject ? 'domain' : 'subject',
)
/** Topic view is a 2D overlay owned by the page; the ocean pauses while shown. */
const viewMode = computed<'ocean' | 'topic'>(() =>
  props.selectedTopicLevel ? 'topic' : 'ocean',
)

const subjectNodes = computed(() => layoutOceanNodes(props.subjects))
const domainNodes = computed(() => layoutOceanDomains(props.domains))
const activeNodes = computed(() =>
  sceneLevel.value === 'domain' ? domainNodes.value : subjectNodes.value,
)

/** Pending pointer picks are consumed by onFrame (never picked synchronously). */
let pendingPick: { x: number; y: number; kind: 'preview' | 'select' } | null =
  null
let pinchStart = 0
let pinchedOut = false
let pinchedIn = false

/** Find the group carrying island/domain metadata from any child mesh. */
function pickMetadata(object: Object3D | null): Record<string, unknown> | null {
  let current: Object3D | null = object
  while (current) {
    const data = current.userData as Record<string, unknown>
    if (data.islandId || data.domainId || data.subject) return data
    current = current.parent
  }
  return null
}

function toNodeRef(data: Record<string, unknown>): OceanNodeRef | null {
  const id =
    typeof data.islandId === 'string'
      ? data.islandId
      : typeof data.domainId === 'string'
        ? data.domainId
        : ''
  const node = activeNodes.value.find((candidate) => candidate.id === id)
  if (!node) return null
  return {
    id: node.id,
    ...(sceneLevel.value === 'domain' && typeof data.subject === 'string'
      ? { subject: data.subject }
      : {}),
    x: node.x,
    z: node.z,
    worldRadius: node.worldRadius,
  }
}

function pickAt(x: number, y: number): Record<string, unknown> | null {
  const canvas = canvasRef.value
  if (!THREE || !raycaster || !canvas || !oceanScene || !camera) return null
  const rect = canvas.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null

  if (!ndc) return null
  ndc.set(
    ((x - rect.left) / rect.width) * 2 - 1,
    -((y - rect.top) / rect.height) * 2 + 1,
  )
  raycaster.setFromCamera(ndc, camera)
  // pickTargets are Groups: descendants are meshes and carry the same
  // userData, but raycasting must be recursive to reach them.
  const hits = raycaster.intersectObjects(oceanScene.pickTargets, true)
  for (const hit of hits) {
    const data = pickMetadata(hit.object)
    if (data) return data
  }
  return null
}

function dispatchPick(
  data: Record<string, unknown>,
  kind: 'preview' | 'select',
): void {
  const isDomain = sceneLevel.value === 'domain'
  const id = isDomain ? data.domainId : data.islandId
  if (typeof id !== 'string') return
  const subject =
    typeof data.subject === 'string' ? data.subject : props.selectedSubject
  const payload = { subject, domain: id }

  if (isDomain) {
    if (kind === 'preview') emit('previewDomain', payload)
    else emit('selectDomain', payload)
  } else {
    if (kind === 'preview') emit('previewSubject', id)
    else emit('selectSubject', id)
  }

  const node = toNodeRef(data)
  if (node) emit('oceanNavigation', node)
}

function onDoubleClick(event: MouseEvent): void {
  emit('interacted')
  if (viewMode.value === 'topic' || contextLost || !lifecycleMounted) return
  pendingPick = { x: event.clientX, y: event.clientY, kind: 'select' }
}

function onPointerUp(event: PointerEvent): void {
  emit('interacted')
  if (viewMode.value === 'topic' || contextLost || !lifecycleMounted) return
  if (pinchedOut || pinchedIn) return
  pendingPick = { x: event.clientX, y: event.clientY, kind: 'preview' }
}

function onTouchStart(event: TouchEvent): void {
  emit('interacted')
  if (viewMode.value === 'topic' || contextLost) return
  if (event.touches.length === 2) {
    const first = event.touches[0]
    const second = event.touches[1]
    pinchStart = Math.hypot(
      first.clientX - second.clientX,
      first.clientY - second.clientY,
    )
    pinchedOut = false
    pinchedIn = false
  }
}

function onTouchMove(event: TouchEvent): void {
  if (viewMode.value === 'topic' || contextLost || event.touches.length !== 2)
    return
  const first = event.touches[0]
  const second = event.touches[1]
  const distance = Math.hypot(
    first.clientX - second.clientX,
    first.clientY - second.clientY,
  )
  if (pinchStart <= 0) {
    pinchStart = distance
    return
  }
  const ratio = distance / pinchStart
  if (ratio > 1.15 && !pinchedOut) {
    pinchedOut = true
    pinchStart = distance
    emit('zoomOut')
    emit('oceanNavigation', null)
    void cameraController?.ascend()
  } else if (ratio < 1 / 1.15 && !pinchedIn) {
    pinchedIn = true
    pinchStart = distance
    const data = pickAt(first.clientX, first.clientY)
    if (data && typeof data.islandId === 'string') {
      const node = toNodeRef(data)
      if (node) {
        emit('selectSubject', node.id)
        emit('oceanNavigation', node)
        void cameraController?.diveTo(node)
      }
    }
  }
}

function onTouchEnd(): void {
  if (!pinchedOut && !pinchedIn) return
  pinchStart = 0
  // Keep the gesture flag through the synthetic pointerup that follows.
  setTimeout(() => {
    pinchedOut = false
    pinchedIn = false
  }, 0)
}

function onFrame(now: number): void {
  if (!water || !labels || !camera || viewMode.value === 'topic') return
  water.update(now / 1000)
  labels.update(camera)

  const pending = pendingPick
  pendingPick = null
  if (!pending) return
  const data = pickAt(pending.x, pending.y)
  if (!data) return
  dispatchPick(data, pending.kind)
  if (pending.kind === 'select') {
    const node = toNodeRef(data)
    if (node) void cameraController?.diveTo(node)
  }
}

function onContextLost(event: Event): void {
  event.preventDefault()
  contextLost = true
  markFailed()
}

function onVisibilityChange(): void {
  if (!lifecycleMounted || contextLost) return
  handle.setDocumentVisibilityPaused(document.hidden)
}

/** Rebuild just the ocean tiles (scene graph stays mounted). */
function rebuildOceanScene(): void {
  if (!scene || !THREE) return
  if (oceanScene) {
    scene.remove(oceanScene.root)
    oceanScene.dispose()
    oceanScene = null
  }
  if (labels) {
    scene.remove(...labels.sprites)
    labels.dispose()
    labels = null
  }

  const nodes = activeNodes.value
  oceanScene = buildOceanScene(nodes, {
    domainMode: sceneLevel.value === 'domain',
    reducedMotion: reducedMotion.value,
  })
  scene.add(oceanScene.root)
  const labelNodes = nodes.map((node) => ({
    ...node,
    icon: 'icon' in node ? node.icon : '🧭',
  }))
  labels = createOceanLabels(THREE, labelNodes, {
    reducedMotion: reducedMotion.value,
  })
  if (viewMode.value === 'topic') {
    scene.remove(oceanScene.root)
    for (const sprite of labels.sprites) scene.remove(sprite)
  } else {
    scene.add(...labels.sprites)
  }
}

function markFailed(): void {
  if (failed.value) return
  failed.value = true
  emit('fallback')
}

async function mountScene(): Promise<void> {
  const canvas = canvasRef.value
  const container = containerRef.value
  if (!canvas || !container || disposed) return
  if (!isWebGLAvailable()) {
    markFailed()
    return
  }

  try {
    // Heavy three.js module is loaded only after WebGL detection succeeds.
    const loaded = await import('three')
    if (disposed) return
    THREE = loaded

    const width = Math.max(container.clientWidth, 1)
    const height = Math.max(container.clientHeight, 1)
    const newScene = new loaded.Scene()
    newScene.background = null
    const newCamera = new loaded.PerspectiveCamera(55, width / height, 0.1, 200)
    const newRenderer = new loaded.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
    })
    newRenderer.shadowMap.enabled = false

    newScene.add(new loaded.AmbientLight(0xffffff, 0.75))
    const sunlight = new loaded.DirectionalLight(0xffffff, 0.7)
    sunlight.position.set(5, 10, 8)
    newScene.add(sunlight)

    scene = newScene
    camera = newCamera
    renderer = newRenderer
    raycaster = new loaded.Raycaster()
    ndc = new loaded.Vector2()

    water = createOceanWater(loaded, { reducedMotion: reducedMotion.value })
    newScene.add(water.mesh)
    rebuildOceanScene()

    const { createOceanCameraController } =
      await import('./OceanCameraController')
    if (disposed) return
    cameraController = createOceanCameraController(newCamera, {
      instant: reducedMotion.value,
    })

    handle.mount(canvas, container, {
      THREE: loaded,
      scene: newScene,
      camera: newCamera,
      renderer: newRenderer,
      onFrame,
      onContextLost,
    })
    lifecycleMounted = true
    if (document.hidden && !contextLost)
      handle.setDocumentVisibilityPaused(true)
  } catch {
    markFailed()
  }
}

onMounted(() => {
  void mountScene()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

/** Keep the ocean scene graph in sync with the level and topic overlays. */
watch([sceneLevel, viewMode, () => props.subjects, () => props.domains], () => {
  if (!lifecycleMounted || contextLost) return
  rebuildOceanScene()
})

onActivated(() => {
  if (lifecycleMounted && !contextLost) handle.resume()
})

onDeactivated(() => {
  if (lifecycleMounted) handle.pause()
})

onBeforeUnmount(() => {
  disposed = true
  handle.destroy()
  lifecycleMounted = false
  document.removeEventListener('visibilitychange', onVisibilityChange)

  cameraController?.dispose()
  cameraController = null

  if (scene && labels) {
    for (const sprite of labels.sprites) scene.remove(sprite)
  }
  labels?.dispose()
  labels = null

  if (scene && oceanScene) scene.remove(oceanScene.root)
  oceanScene?.dispose()
  oceanScene = null

  water?.dispose()
  water = null

  renderer?.dispose()
  renderer?.forceContextLoss()
  renderer = null
  scene = null
  camera = null
  raycaster = null
  ndc = null
  THREE = null
})

defineExpose({
  /** Return the camera to the L0 ocean overview. */
  resetCamera: async (): Promise<void> => {
    await cameraController?.reset()
  },
  /** Frame a subject or domain node by id. */
  diveTo: async (id: string): Promise<void> => {
    const node = activeNodes.value.find((candidate) => candidate.id === id)
    if (!node) return
    const ref: OceanNodeRef = {
      id: node.id,
      x: node.x,
      z: node.z,
      worldRadius: node.worldRadius,
    }
    await cameraController?.diveTo(ref)
  },
})
</script>

<style scoped>
.knowledge-ocean-3d {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  touch-action: none;
}

.knowledge-ocean-3d__canvas {
  display: block;
  width: 100%;
  height: 100%;
  touch-action: none;
}

.knowledge-ocean-3d--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  border-radius: 20px;
  background: var(--ocean-sea-color, #cfe8f5);
}

.knowledge-ocean-3d__message {
  max-width: 32rem;
  margin: 0;
  text-align: center;
  color: var(--color-text-primary, #16324a);
  font-size: 1rem;
  line-height: 1.6;
}
</style>
