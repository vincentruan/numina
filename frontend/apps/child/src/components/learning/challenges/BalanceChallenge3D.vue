<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="hasAnyPlacement"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <div
      ref="containerEl"
      class="challenge-3d-container"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
    >
      <canvas ref="canvasEl" class="challenge-3d-canvas" />
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import {
  ref, reactive, computed, watch,
  onMounted, onBeforeUnmount, onActivated, onDeactivated,
} from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Scene, PerspectiveCamera, WebGLRenderer, DirectionalLight, AmbientLight,
  Mesh, Group, SphereGeometry, BoxGeometry, CylinderGeometry,
  MeshStandardMaterial, Vector2, Vector3, Raycaster, Plane,
} from 'three'
import type { BalanceChallenge, ChallengeVerdict } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { createChildTimeline, tickDriver } from '@/motion/animeDriver'
import { easeOutElastic, easeOutQuad } from '@/motion/easing'
import { clayColor } from '@/motion/materials'
import { initRapier, getWorld, stepPhysics } from '@/physics/rapierWorld'
import { createKinematicIsland } from '@/physics/islandBody'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { resumeAudio, playDropThunk, playClickPop } from '@/audio/sfx'
import { triggerSuccessFeedback, triggerErrorFeedback } from './feedback'

defineOptions({ name: 'BalanceChallenge3D' })

const props = defineProps<{ config: BalanceChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t, locale } = useI18n()

const canvasEl = ref<HTMLCanvasElement | null>(null)
const containerEl = ref<HTMLDivElement | null>(null)

// ── Challenge state (mirrors 2D BalanceChallenge) ──
const rightPlacements = reactive<(string | null)[]>(
  Array.from({ length: props.config.rightSlots }, () => null),
)
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)

// ── Session persistence ──
const STORAGE_KEY = `numina:challenge:${props.config.id}`

interface PersistedState {
  rightPlacements: (string | null)[]
  attemptCount: number
  completed: boolean
  feedbackMessage: string
  feedbackVerdict: ChallengeVerdict | null
}

function restoreState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as PersistedState
    const sp = saved.rightPlacements ?? []
    for (let i = 0; i < props.config.rightSlots; i++) {
      const id = sp[i] ?? null
      rightPlacements[i] = id && props.config.objects.some((o) => o.id === id) ? id : null
    }
    attemptCount.value = saved.attemptCount ?? 0
    completed.value = saved.completed ?? false
    feedbackMessage.value = saved.feedbackMessage ?? ''
    feedbackVerdict.value = saved.feedbackVerdict ?? null
  } catch { /* unavailable */ }
}

function persistState() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      rightPlacements: [...rightPlacements], attemptCount: attemptCount.value,
      completed: completed.value, feedbackMessage: feedbackMessage.value,
      feedbackVerdict: feedbackVerdict.value,
    } as PersistedState))
  } catch { /* unavailable */ }
}

function clearState() {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* unavailable */ }
}

restoreState()
watch(
  [rightPlacements, attemptCount, completed, feedbackMessage, feedbackVerdict],
  () => persistState(), { deep: true },
)

// ── Computed ──
const isZh = computed(() => locale.value.startsWith('zh'))
const placedIds = computed(() => new Set(rightPlacements.filter((id): id is string => id !== null)))
const hasAnyPlacement = computed(() => placedIds.value.size > 0)

function objectValue(objId: string): number { return props.config.objectValues[objId] ?? 0 }

const leftTotal = computed(() => props.config.leftFixed.reduce((s, o) => s + objectValue(o.id), 0))
const rightTotal = computed(() => rightPlacements.reduce((s, id) => s + (id ? objectValue(id) : 0), 0))

const statusText = computed(() =>
  t('learning.challenge.placedCount', { placed: placedIds.value.size, total: props.config.rightSlots }))
const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)

// ── Three.js scene state ──
let scene: Scene | null = null
let camera: PerspectiveCamera | null = null
let renderer: WebGLRenderer | null = null
let beamGroup: Group | null = null
const weightMeshes = new Map<string, Mesh>()
const trayObjects: Mesh[] = []
let animFrameId = 0
let lastFrameTime = 0
let isPaused = false
let isDragging = false
let draggingObjId: string | null = null
const raycaster = new Raycaster()
const dragPlane = new Plane(new Vector3(0, 0, 1), 0)
const reducedMotion = useReducedMotion()
const childTimeline = createChildTimeline()

// Layout constants
const BEAM_Y = 3.5
const BEAM_HALF_W = 3.0
const PAN_Y = 1.5
const PAN_OFFSET_X = 2.8
const TRAY_Y = -2.5
const TRAY_SPACING = 1.2
const SNAP_RADIUS = 1.2

// ── Scene setup ──
function buildScene() {
  if (!canvasEl.value || !containerEl.value) return
  const w = containerEl.value.clientWidth
  const h = containerEl.value.clientHeight

  scene = new Scene()
  scene.background = clayColor('canvas')
  camera = new PerspectiveCamera(50, w / h, 0.1, 100)
  camera.position.set(0, 2, 10)
  camera.lookAt(0, 1.5, 0)

  renderer = new WebGLRenderer({ canvas: canvasEl.value, antialias: true, alpha: false })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h)

  scene.add(new AmbientLight(0xffffff, 0.6))
  const dir = new DirectionalLight(0xffffff, 0.8)
  dir.position.set(3, 8, 5)
  scene.add(dir)

  // Fulcrum
  const fulcrum = new Mesh(
    new CylinderGeometry(0.15, 0.5, 1.2, 3),
    new MeshStandardMaterial({ color: clayColor('body') }),
  )
  fulcrum.position.set(0, BEAM_Y - 0.9, 0)
  scene.add(fulcrum)

  // Beam + pans
  beamGroup = new Group()
  beamGroup.position.set(0, BEAM_Y, 0)
  beamGroup.add(new Mesh(
    new BoxGeometry(BEAM_HALF_W * 2 + 0.6, 0.12, 0.4),
    new MeshStandardMaterial({ color: clayColor('primary') }),
  ))
  const panGeo = new CylinderGeometry(0.7, 0.7, 0.08, 24)
  const panMat = new MeshStandardMaterial({ color: clayColor('brand-teal') })
  const lPan = new Mesh(panGeo, panMat.clone())
  lPan.position.set(-PAN_OFFSET_X, PAN_Y - BEAM_Y, 0)
  beamGroup.add(lPan)
  const rPan = new Mesh(panGeo.clone(), panMat.clone())
  rPan.position.set(PAN_OFFSET_X, PAN_Y - BEAM_Y, 0)
  beamGroup.add(rPan)
  scene.add(beamGroup)

  // Left fixed objects
  const fixedColor = clayColor('brand-lavender')
  props.config.leftFixed.forEach((obj, i) => {
    const r = 0.25 + objectValue(obj.id) * 0.05
    const m = new Mesh(new SphereGeometry(r, 16, 16), new MeshStandardMaterial({ color: fixedColor }))
    m.position.set(-PAN_OFFSET_X + (i % 2) * 0.4 - 0.2, PAN_Y - BEAM_Y + r + Math.floor(i / 2) * 0.5, 0)
    beamGroup!.add(m)
  })

  buildWeightMeshes()

  // Physics ground
  createKinematicIsland(getWorld(), {
    position: { x: 0, y: TRAY_Y - 1, z: 0 }, halfExtents: { x: 10, y: 0.1, z: 2 },
  })
}

/** Build/rebuild tray + placed weight meshes. */
function buildWeightMeshes() {
  if (!scene || !beamGroup) return
  // Clear old tray objects
  trayObjects.forEach((m) => { scene!.remove(m); m.geometry.dispose(); (m.material as MeshStandardMaterial).dispose() })
  trayObjects.length = 0
  // Clear old placed meshes from beamGroup
  const toRemove: Mesh[] = []
  beamGroup.children.forEach((child) => {
    if (child instanceof Mesh && child.userData.objId) toRemove.push(child)
  })
  toRemove.forEach((m) => {
    beamGroup!.remove(m)
    m.geometry.dispose()
    ;(m.material as MeshStandardMaterial).dispose()
  })
  weightMeshes.clear()

  // Tray (available) objects
  const available = props.config.objects.filter((o) => !placedIds.value.has(o.id))
  const startX = -((available.length - 1) * TRAY_SPACING) / 2
  available.forEach((obj, i) => {
    const r = 0.3 + objectValue(obj.id) * 0.05
    const m = new Mesh(new SphereGeometry(r, 16, 16), new MeshStandardMaterial({ color: clayColor('brand-peach') }))
    m.position.set(startX + i * TRAY_SPACING, TRAY_Y, 0)
    m.userData = { objId: obj.id, radius: r }
    scene!.add(m)
    trayObjects.push(m)
    weightMeshes.set(obj.id, m)
  })

  // Placed objects on right pan
  rightPlacements.forEach((objId, idx) => {
    if (!objId) return
    const r = 0.3 + objectValue(objId) * 0.05
    const m = new Mesh(new SphereGeometry(r, 16, 16), new MeshStandardMaterial({ color: clayColor('brand-mint') }))
    m.position.set(PAN_OFFSET_X + (idx - (props.config.rightSlots - 1) / 2) * 0.6, PAN_Y - BEAM_Y + r, 0)
    m.userData = { objId, radius: r }
    beamGroup!.add(m)
    weightMeshes.set(objId, m)
  })
}

// ── Render loop ──
function renderLoop(now: number) {
  if (isPaused || !renderer || !scene || !camera) return
  animFrameId = requestAnimationFrame(renderLoop)
  const dt = lastFrameTime ? (now - lastFrameTime) / 1000 : 1 / 60
  lastFrameTime = now

  stepPhysics(dt)
  tickDriver(now)

  // Smooth beam tilt based on weight difference
  if (beamGroup) {
    const diff = leftTotal.value - rightTotal.value
    const target = Math.max(-0.25, Math.min(0.25, diff * 0.05))
    const alpha = reducedMotion.value ? 1 : 0.08
    beamGroup.rotation.z += (target - beamGroup.rotation.z) * alpha
  }

  renderer.render(scene, camera)
}

function startLoop() { isPaused = false; lastFrameTime = 0; animFrameId = requestAnimationFrame(renderLoop) }
function stopLoop() { isPaused = true; cancelAnimationFrame(animFrameId) }

function handleResize() {
  if (!renderer || !camera || !containerEl.value) return
  const w = containerEl.value.clientWidth
  const h = containerEl.value.clientHeight
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
}

// ── Pointer interaction ──
function getNDC(e: PointerEvent): Vector2 {
  const rect = canvasEl.value!.getBoundingClientRect()
  return new Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1)
}

/** R12: expanded hit radius — find closest tray object within 28px screen distance. */
function findClosestByScreenDistance(ndc: Vector2, maxPx = 28): Mesh | null {
  if (!camera || !canvasEl.value) return null
  const rect = canvasEl.value.getBoundingClientRect()
  const cx = (ndc.x * 0.5 + 0.5) * rect.width
  const cy = (-ndc.y * 0.5 + 0.5) * rect.height
  let best: Mesh | null = null
  let bestPx = maxPx
  const v = new Vector3()
  for (const mesh of trayObjects) {
    v.copy(mesh.position).project(camera)
    const sx = (v.x * 0.5 + 0.5) * rect.width
    const sy = (-v.y * 0.5 + 0.5) * rect.height
    const px = Math.sqrt((sx - cx) ** 2 + (sy - cy) ** 2)
    if (px < bestPx) { bestPx = px; best = mesh }
  }
  return best
}

function onPointerDown(e: PointerEvent) {
  if (completed.value || !canvasEl.value) return
  resumeAudio()
  const ndc = getNDC(e)
  raycaster.setFromCamera(ndc, camera!)
  let hits = raycaster.intersectObjects(trayObjects, false)
  // R12: expanded hit radius fallback — 28px screen distance
  if (hits.length === 0) {
    const prox = findClosestByScreenDistance(ndc)
    if (prox) hits = [{ object: prox, distance: 0 } as any]
  }
  if (hits.length > 0) {
    const mesh = hits[0].object as Mesh
    isDragging = true
    draggingObjId = mesh.userData.objId as string
    playClickPop()
    ;(mesh.material as MeshStandardMaterial).color.copy(clayColor('brand-ochre'))
    mesh.scale.setScalar(1.15)
  }
}

function onPointerMove(e: PointerEvent) {
  if (!isDragging || !draggingObjId || !camera) return
  raycaster.setFromCamera(getNDC(e), camera!)
  const point = new Vector3()
  raycaster.ray.intersectPlane(dragPlane, point)
  const mesh = weightMeshes.get(draggingObjId)
  if (mesh) { mesh.position.x = point.x; mesh.position.y = point.y }
}

function onPointerUp() {
  if (!isDragging || !draggingObjId) return
  const mesh = weightMeshes.get(draggingObjId)
  if (!mesh) { resetDrag(); return }

  const dx = mesh.position.x - PAN_OFFSET_X
  const dy = mesh.position.y - PAN_Y
  const dist = Math.sqrt(dx * dx + dy * dy)

  if (dist < SNAP_RADIUS) {
    const emptyIdx = rightPlacements.indexOf(null)
    if (emptyIdx !== -1) {
      const slotX = PAN_OFFSET_X + (emptyIdx - (props.config.rightSlots - 1) / 2) * 0.6
      const slotY = PAN_Y - BEAM_Y + mesh.userData.radius

      // Update placement state first, then rebuild meshes
      rightPlacements[emptyIdx] = draggingObjId
      playDropThunk()
      // buildWeightMeshes will place the mesh at the correct slot position
      buildWeightMeshes()
    } else { animateBackToTray(mesh) }
  } else { animateBackToTray(mesh) }
  resetDrag()
}

function animateBackToTray(mesh: Mesh) {
  const available = props.config.objects.filter((o) => !placedIds.value.has(o.id))
  const availIdx = available.findIndex((o) => o.id === mesh.userData.objId)
  const startX = -((available.length - 1) * TRAY_SPACING) / 2
  const targetX = availIdx >= 0 ? startX + availIdx * TRAY_SPACING : mesh.position.x
  childTimeline.add(mesh.position, {
    x: targetX, y: TRAY_Y, z: 0, duration: reducedMotion.value ? 0 : 400, ease: easeOutQuad,
  })
  ;(mesh.material as MeshStandardMaterial).color.copy(clayColor('brand-peach'))
  mesh.scale.setScalar(1)
}

function resetDrag() { isDragging = false; draggingObjId = null }

// ── Evaluation (same logic as 2D) ──
function evaluateBalance(): { isCorrect: boolean; hint: string } {
  const left = leftTotal.value, right = rightTotal.value
  if (left === right && right > 0) return { isCorrect: true, hint: '' }
  if (left > right) return { isCorrect: false, hint: t('learning.challenge.hintTooLight') }
  return { isCorrect: false, hint: t('learning.challenge.hintTooHeavy') }
}

function checkAnswer() {
  attemptCount.value++
  const result = evaluateBalance()
  feedbackVerdict.value = result.isCorrect ? 'correct' : 'wrong'

  if (result.isCorrect) {
    completed.value = true
    feedbackMessage.value = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
    if (containerEl.value) triggerSuccessFeedback(containerEl.value)
    // Animate beam to balanced — instant target set, render loop smooths via lerp
    if (beamGroup && reducedMotion.value) {
      // reducedMotion: lerp will snap in one frame (alpha=1)
    }
  } else {
    feedbackMessage.value = result.hint
    if (containerEl.value) triggerErrorFeedback(containerEl.value)
  }
}

function onContinue() { clearState(); emit('complete') }

function handleVisibility() {
  if (document.hidden) stopLoop()
  else if (!isPaused) startLoop()
}

// ── Lifecycle ──
onMounted(async () => {
  await initRapier()
  buildScene()
  startLoop()
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibility)
})

onBeforeUnmount(() => {
  stopLoop()
  childTimeline.revert()
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('visibilitychange', handleVisibility)
  weightMeshes.forEach((m) => { m.geometry.dispose(); (m.material as MeshStandardMaterial).dispose() })
  trayObjects.forEach((m) => { m.geometry.dispose(); (m.material as MeshStandardMaterial).dispose() })
  if (renderer) renderer.dispose()
  scene = null; camera = null; renderer = null
})

onActivated(() => { startLoop() })
onDeactivated(() => { stopLoop() })
</script>

<style scoped>
.challenge-3d-container {
  position: relative;
  width: 100%;
  height: 320px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--continent-canvas-bg);
  touch-action: none;
}
.challenge-3d-canvas { display: block; width: 100%; height: 100%; }
</style>
