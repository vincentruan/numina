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
    <div ref="containerRef" class="distribute-3d-container" />
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useI18n } from 'vue-i18n'
import * as THREE from 'three'
import RAPIER from '@dimforge/rapier3d-compat'
import type { DistributeChallenge, ChallengeVerdict } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { initRapier, getWorld, stepPhysics, syncMeshesFromBodies } from '@/physics/rapierWorld'
import { createDynamicObject, createStaticGround } from '@/physics/islandBody'
import { createChildTimeline } from '@/motion/animeDriver'
import { easeOutElastic } from '@/motion/easing'
import { clayColor } from '@/motion/materials'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { tryVibrate } from '@/composables/useHaptic'
import { resumeAudio, playDropThunk } from '@/audio/sfx'
import { triggerSuccessFeedback, triggerErrorFeedback } from './feedback'

defineOptions({ name: 'DistributeChallenge3D' })

const props = defineProps<{ config: DistributeChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t, locale } = useI18n()

const containerRef = ref<HTMLDivElement | null>(null)
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)
const hasAnyPlacement = ref(false)

const reducedMotion = useReducedMotion()
const isZh = computed(() => locale.value.startsWith('zh'))
const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)
const statusText = computed(() => `${placements.value.size}/${props.config.objects.length} placed`)

interface ObjectState {
  id: string
  mesh: THREE.Mesh
  body: RAPIER.RigidBody
  zoneId: string | null
  trayPosition: THREE.Vector3
}

interface ZoneState {
  id: string
  mesh: THREE.Mesh
  center: THREE.Vector3
  objectIds: Set<string>
}

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let raycaster: THREE.Raycaster | null = null
let mouse: THREE.Vector2 | null = null
let dragging: ObjectState | null = null
let dragPlane: THREE.Plane | null = null
let dragOffset: THREE.Vector3 | null = null
let pointerId: number | null = null
const objectStates = new Map<string, ObjectState>()
const zoneStates = new Map<string, ZoneState>()
const placements = ref(new Map<string, string>()) // objectId -> zoneId
let animationId: number | null = null
let lastTime = 0
let paused = false
const STORAGE_KEY = `numina:challenge:${props.config.id}`
const snapTimelines: ReturnType<typeof createChildTimeline>[] = []

function loadState(): void {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved) {
      const data = JSON.parse(saved) as { placements: Array<[string, string]> }
      placements.value = new Map(data.placements)
      hasAnyPlacement.value = placements.value.size > 0
    }
  } catch { /* ignore */ }
}

function saveState(): void {
  try {
    const data = { placements: Array.from(placements.value.entries()) }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch { /* ignore */ }
}

function initScene(): void {
  if (!containerRef.value) return

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = clayColor('canvas')

  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100)
  camera.position.set(0, 12, 8)
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  containerRef.value.appendChild(renderer.domElement)

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(5, 10, 5)
  scene.add(directionalLight)

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()
  dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -1)
  dragOffset = new THREE.Vector3()

  createStaticGround(getWorld(), 0, 15, 15)

  createZones()
  createObjects()
  restorePlacements()
}

function createZones(): void {
  const zoneCount = props.config.zones.length
  const radius = 5
  const zoneSize = 1.5
  const colors = ['brand-mint', 'brand-teal', 'brand-lavender', 'brand-peach', 'brand-ochre']

  props.config.zones.forEach((zone, i) => {
    const pos = props.config.zonePositions?.[zone.id]
    const x = pos ? pos.x : Math.cos((i / zoneCount) * Math.PI * 2) * radius
    const z = pos ? pos.y : Math.sin((i / zoneCount) * Math.PI * 2) * radius

    const geometry = new THREE.CircleGeometry(zoneSize, 32)
    const material = new THREE.MeshStandardMaterial({ color: clayColor(colors[i % 5]), transparent: true, opacity: 0.3 })
    const mesh = new THREE.Mesh(geometry, material)
    mesh.rotation.x = -Math.PI / 2
    mesh.position.set(x, 0.01, z)
    mesh.userData = { type: 'zone', zoneId: zone.id }
    scene!.add(mesh)

    zoneStates.set(zone.id, { id: zone.id, mesh, center: new THREE.Vector3(x, 0.5, z), objectIds: new Set() })
  })
}

function createObjects(): void {
  const trayRadius = 1.5
  const objectRadius = 0.4

  props.config.objects.forEach((obj, i) => {
    const angle = (i / props.config.objects.length) * Math.PI * 2
    const trayX = Math.cos(angle) * trayRadius
    const trayZ = Math.sin(angle) * trayRadius
    const trayY = 0.5

    const geometry = new THREE.SphereGeometry(objectRadius, 16, 16)
    const material = new THREE.MeshStandardMaterial({ color: clayColor('primary'), roughness: 0.6, metalness: 0.1 })
    const mesh = new THREE.Mesh(geometry, material)
    mesh.position.set(trayX, trayY, trayZ)
    mesh.userData = { type: 'object', objectId: obj.id }
    scene!.add(mesh)

    const { body } = createDynamicObject(getWorld(), { position: { x: trayX, y: trayY, z: trayZ }, radius: objectRadius, mass: 1, linearDamping: 0.8 })
    objectStates.set(obj.id, { id: obj.id, mesh, body, zoneId: null, trayPosition: new THREE.Vector3(trayX, trayY, trayZ) })
  })
}

function restorePlacements(): void {
  for (const [objectId, zoneId] of placements.value.entries()) {
    const objState = objectStates.get(objectId)
    const zoneState = zoneStates.get(zoneId)
    if (objState && zoneState) {
      snapToZone(objState, zoneState, false)
    }
  }
}

function snapToZone(objState: ObjectState, zoneState: ZoneState, animate: boolean): void {
  const target = zoneState.center.clone()
  objState.zoneId = zoneState.id
  zoneState.objectIds.add(objState.id)
  placements.value.set(objState.id, zoneState.id)
  hasAnyPlacement.value = true
  saveState()

  if (animate && !reducedMotion.value) {
    const timeline = createChildTimeline()
    timeline.add(objState.mesh.position, { x: target.x, y: target.y, z: target.z, duration: 400, ease: easeOutElastic })
    snapTimelines.push(timeline)
  } else {
    objState.mesh.position.copy(target)
  }

  objState.body.setTranslation({ x: target.x, y: target.y, z: target.z }, true)
  objState.body.setLinvel({ x: 0, y: 0, z: 0 }, true)
}

function returnToTray(objState: ObjectState): void {
  if (objState.zoneId) {
    zoneStates.get(objState.zoneId)?.objectIds.delete(objState.id)
    placements.value.delete(objState.id)
    objState.zoneId = null
    saveState()
  }
  const target = objState.trayPosition.clone()
  objState.body.setTranslation({ x: target.x, y: target.y, z: target.z }, true)
  objState.body.setLinvel({ x: 0, y: 0, z: 0 }, true)
  objState.mesh.position.copy(target)
}

function onPointerDown(e: PointerEvent): void {
  if (paused || !renderer || !camera || !raycaster || !mouse) return
  resumeAudio()

  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(mouse, camera)

  const intersects = raycaster.intersectObjects(Array.from(objectStates.values()).map(o => o.mesh))
  if (intersects.length > 0) {
    const hit = intersects[0].object as THREE.Mesh
    const objState = objectStates.get(hit.userData.objectId as string)
    if (objState) {
      dragging = objState
      pointerId = e.pointerId
      if (objState.zoneId) {
        zoneStates.get(objState.zoneId)?.objectIds.delete(objState.id)
        placements.value.delete(objState.id)
        objState.zoneId = null
        saveState()
      }
      objState.body.setBodyType(RAPIER.RigidBodyType.KinematicPositionBased, true)
      const intersection = new THREE.Vector3()
      raycaster.ray.intersectPlane(dragPlane!, intersection)
      dragOffset!.copy(objState.mesh.position).sub(intersection)
      pointerId = e.pointerId
      renderer.domElement.setPointerCapture(e.pointerId)
      tryVibrate(10)
    }
  }
}

function onPointerMove(e: PointerEvent): void {
  if (!dragging || !renderer || !camera || !raycaster || !mouse || !dragPlane || !dragOffset) return

  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(mouse, camera)

  const intersection = new THREE.Vector3()
  raycaster.ray.intersectPlane(dragPlane, intersection)
  intersection.add(dragOffset)
  intersection.y = 1
  dragging.mesh.position.copy(intersection)
  dragging.body.setTranslation({ x: intersection.x, y: intersection.y, z: intersection.z }, true)

  for (const zoneState of zoneStates.values()) {
    const mat = zoneState.mesh.material as THREE.MeshStandardMaterial
    mat.opacity = intersection.distanceTo(zoneState.center) < 1.5 ? 0.6 : 0.3
  }
}

function onPointerUp(): void {
  if (!dragging) return
  const objState = dragging
  dragging = null

  let dropped = false
  for (const zoneState of zoneStates.values()) {
    if (objState.mesh.position.distanceTo(zoneState.center) < 1.5) {
      snapToZone(objState, zoneState, true)
      playDropThunk()
      dropped = true
      break
    }
  }
  if (!dropped) returnToTray(objState)

  objState.body.setBodyType(RAPIER.RigidBodyType.Dynamic, true)
  for (const zoneState of zoneStates.values()) {
    (zoneState.mesh.material as THREE.MeshStandardMaterial).opacity = 0.3
  }
  if (pointerId !== null) {
    renderer?.domElement.releasePointerCapture(pointerId)
    pointerId = null
  }
}

function checkAnswer(): void {
  attemptCount.value++
  const counts = Array.from(zoneStates.values()).map(z => z.objectIds.size)
  const diff = Math.max(...counts) - Math.min(...counts)

  if (diff === 0 && counts.every(c => c > 0)) {
    feedbackVerdict.value = 'correct'
    feedbackMessage.value = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
    completed.value = true
    if (containerRef.value) triggerSuccessFeedback(containerRef.value)
  } else if (diff <= 1) {
    feedbackVerdict.value = 'close'
    feedbackMessage.value = t('learning.challenge.verdictClose')
    if (containerRef.value) triggerErrorFeedback(containerRef.value)
  } else {
    feedbackVerdict.value = 'wrong'
    feedbackMessage.value = t('learning.challenge.hintGeneric')
    if (containerRef.value) triggerErrorFeedback(containerRef.value)
  }
}

function onContinue(): void {
  completed.value = false
  feedbackMessage.value = ''
  feedbackVerdict.value = null
  emit('complete')
}

function animate(time: number): void {
  if (paused || !renderer || !scene || !camera) return
  animationId = requestAnimationFrame(animate)

  const dt = lastTime ? (time - lastTime) / 1000 : 0
  lastTime = time
  stepPhysics(dt, getWorld())

  syncMeshesFromBodies((body, _alpha) => {
    for (const objState of objectStates.values()) {
      if (objState.body === body && objState !== dragging) {
        const pos = body.translation()
        objState.mesh.position.set(pos.x, pos.y, pos.z)
      }
    }
  }, getWorld())

  renderer.render(scene, camera)
}

function onResize(): void {
  if (!containerRef.value || !renderer || !camera) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  renderer.setSize(width, height)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

function startLoop(): void {
  paused = false
  lastTime = 0
  if (animationId === null) animationId = requestAnimationFrame(animate)
}

function stopLoop(): void {
  paused = true
  if (animationId !== null) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
}

function onVisibilityChange(): void {
  if (document.hidden) {
    stopLoop()
  } else {
    startLoop()
  }
}

onMounted(async () => {
  loadState()
  await initRapier()
  initScene()

  if (renderer) {
    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointermove', onPointerMove)
    renderer.domElement.addEventListener('pointerup', onPointerUp)
  }

  window.addEventListener('resize', onResize)
  document.addEventListener('visibilitychange', onVisibilityChange)

  animationId = requestAnimationFrame(animate)
})

onBeforeUnmount(() => {
  stopLoop()
  snapTimelines.forEach((tl) => tl.revert())
  snapTimelines.length = 0
  if (renderer) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointermove', onPointerMove)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    renderer.dispose()
    renderer.domElement.remove()
  }
  window.removeEventListener('resize', onResize)
  document.removeEventListener('visibilitychange', onVisibilityChange)

  objectStates.clear()
  zoneStates.clear()
  scene = null
  camera = null
  renderer = null
})

onActivated(() => {
  startLoop()
})

onDeactivated(() => {
  stopLoop()
})
</script>

<style scoped>
.distribute-3d-container {
  width: 100%;
  height: 400px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--color-surface-card);
  touch-action: none;
}
</style>
