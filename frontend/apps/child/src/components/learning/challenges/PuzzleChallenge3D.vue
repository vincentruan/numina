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
    <div ref="containerRef" class="puzzle-3d-container" />
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useI18n } from 'vue-i18n'
import * as THREE from 'three'
import type { PuzzleChallenge, ChallengeVerdict, ChallengeObject } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { createChildTimeline, tickDriver } from '@/motion/animeDriver'
import { easeOutBack } from '@/motion/easing'
import { clayColor } from '@/motion/materials'
import { initRapier, getWorld, stepPhysics } from '@/physics/rapierWorld'
import { createDynamicObject, createStaticGround } from '@/physics/islandBody'
import { useReducedMotion } from '@/composables/useReducedMotion'
import { tryVibrate } from '@/composables/useHaptic'
import { playClickPop, playDropThunk, resumeAudio } from '@/audio/sfx'
import { triggerSuccessFeedback, triggerErrorFeedback } from './feedback'

defineOptions({ name: 'PuzzleChallenge3D' })

const props = defineProps<{ config: PuzzleChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t } = useI18n()

const containerRef = ref<HTMLDivElement | null>(null)
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)
const hasAnyPlacement = ref(false)
const reducedMotion = useReducedMotion()
const SESSION_KEY = `puzzle-session-${props.config.id}`
interface PieceState {
  id: string
  object: ChallengeObject
  mesh: THREE.Mesh
  body: ReturnType<typeof createDynamicObject>
  slotId: string | null
  trayPosition: THREE.Vector3
}

interface SlotState {
  id: string
  position: THREE.Vector3
  expectedObjectId: string
  outlineMesh: THREE.LineSegments
  occupiedBy: string | null
}

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let raycaster: THREE.Raycaster | null = null
let mouse: THREE.Vector2 | null = null
let timeline: ReturnType<typeof createChildTimeline> | null = null
let animationFrameId: number | null = null
let isDragging = false
let draggedPiece: PieceState | null = null
let dragPlane: THREE.Plane | null = null
let dragOffset: THREE.Vector3 | null = null
const pieces: PieceState[] = []
const slots: SlotState[] = []
const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)
const statusText = computed(() => {
  const placed = pieces.filter(p => p.slotId !== null).length
  return t('learning.challenge.placedCount', { placed, total: props.config.slots.length })
})
function loadSessionState(): Record<string, string | null> {
  try { return sessionStorage.getItem(SESSION_KEY) ? JSON.parse(sessionStorage.getItem(SESSION_KEY)!) : {} }
  catch { return {} }
}

function saveSessionState(): void {
  try {
    const state: Record<string, string | null> = {}
    pieces.forEach(p => { state[p.id] = p.slotId })
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state))
  } catch { /* ignore */ }
}
function computeSlotPositions(): Map<string, THREE.Vector3> {
  const result = new Map<string, THREE.Vector3>()
  const { slotPositions } = props.config

  if (slotPositions) {
    Object.entries(slotPositions).forEach(([slotId, pos]) => {
      result.set(slotId, new THREE.Vector3(pos.x, 0.1, pos.y))
    })
  } else {
    const slotsArr = props.config.slots
    const n = slotsArr.length
    const cols = Math.ceil(Math.sqrt(n))
    const spacing = 1.2
    const startX = -((cols - 1) * spacing) / 2

    slotsArr.forEach((slot, idx) => {
      const col = idx % cols
      const row = Math.floor(idx / cols)
      const x = startX + col * spacing
      const z = -((Math.ceil(n / cols) - 1) * spacing) / 2 + row * spacing
      result.set(slot.id, new THREE.Vector3(x, 0.1, z))
    })
  }
  return result
}
function createSlotOutline(position: THREE.Vector3): THREE.LineSegments {
  const geometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(0.8, 0.02, 0.8))
  const material = new THREE.LineBasicMaterial({ color: clayColor('muted'), transparent: true, opacity: 0.4 })
  const outline = new THREE.LineSegments(geometry, material)
  outline.position.copy(position)
  return outline
}
function createPieceMesh(obj: ChallengeObject, color: THREE.Color): THREE.Mesh {
  const geometry = new THREE.BoxGeometry(0.6, 0.2, 0.6)
  const material = new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.1 })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.userData = { objectId: obj.id }
  return mesh
}
function initializeScene(): void {
  if (!containerRef.value) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  containerRef.value.appendChild(renderer.domElement)

  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100)
  camera.position.set(0, 5, 6)
  camera.lookAt(0, 0, 0)

  scene.add(new THREE.AmbientLight(0xffffff, 0.6))
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(5, 10, 5)
  scene.add(directionalLight)

  const ground = createStaticGround(getWorld(), -0.1, 4, 4)
  const groundMesh = new THREE.Mesh(
    new THREE.BoxGeometry(8, 0.2, 8),
    new THREE.MeshStandardMaterial({ color: clayColor('surface-card'), roughness: 0.9 })
  )
  groundMesh.position.set(0, -0.1, 0)
  scene.add(groundMesh)

  raycaster = new THREE.Raycaster()
  mouse = new THREE.Vector2()
  dragPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
  dragOffset = new THREE.Vector3()

  const slotPositions = computeSlotPositions()
  props.config.slots.forEach(slot => {
    const position = slotPositions.get(slot.id)!
    const outline = createSlotOutline(position)
    scene!.add(outline)
    slots.push({
      id: slot.id,
      position,
      expectedObjectId: props.config.correctPlacement[slot.id],
      outlineMesh: outline,
      occupiedBy: null,
    })
  })

  const sessionState = loadSessionState()
  const brandColors = ['brand-pink', 'brand-teal', 'brand-lavender', 'brand-peach', 'brand-ochre', 'brand-mint', 'brand-coral']

  props.config.objects.forEach((obj, idx) => {
    const color = clayColor(brandColors[idx % brandColors.length])
    const mesh = createPieceMesh(obj, color)
    const trayPos = new THREE.Vector3(-2 + idx * 0.9, 0.2, 3)
    mesh.position.copy(trayPos)
    scene!.add(mesh)

    const body = createDynamicObject(getWorld(), {
      position: { x: trayPos.x, y: trayPos.y, z: trayPos.z },
      radius: 0.3,
      mass: 0.5,
      ccd: true,
    })

    const piece: PieceState = {
      id: obj.id,
      object: obj,
      mesh,
      body,
      slotId: sessionState[obj.id] || null,
      trayPosition: trayPos.clone(),
    }
    pieces.push(piece)

    if (piece.slotId) {
      const slot = slots.find(s => s.id === piece.slotId)
      if (slot) {
        mesh.position.copy(slot.position)
        mesh.position.y = 0.2
        body.body.setTranslation({ x: slot.position.x, y: 0.2, z: slot.position.z }, true)
        slot.occupiedBy = obj.id
      }
    }
  })

  timeline = createChildTimeline()
  hasAnyPlacement.value = pieces.some(p => p.slotId !== null)
}
function onPointerDown(event: PointerEvent): void {
  if (!renderer || !camera || !raycaster || !mouse || !dragPlane || !dragOffset) return
  resumeAudio()
  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersects = raycaster.intersectObjects(pieces.map(p => p.mesh))

  if (intersects.length > 0) {
    const hitMesh = intersects[0].object as THREE.Mesh
    const piece = pieces.find(p => p.mesh === hitMesh)
    if (piece) {
      isDragging = true
      draggedPiece = piece

      if (piece.slotId) {
        const slot = slots.find(s => s.id === piece.slotId)
        if (slot) slot.occupiedBy = null
        piece.slotId = null
      }

      piece.body.body.setBodyType(0, true)
      piece.body.body.setAngvel({ x: 0, y: 0, z: 0 }, true)
      piece.body.body.setLinvel({ x: 0, y: 0, z: 0 }, true)

      const intersection = new THREE.Vector3()
      raycaster.ray.intersectPlane(dragPlane, intersection)
      dragOffset.copy(piece.mesh.position).sub(intersection)
      tryVibrate(10)
    }
  }
}
function onPointerMove(event: PointerEvent): void {
  if (!isDragging || !draggedPiece || !renderer || !camera || !raycaster || !mouse || !dragPlane || !dragOffset) return
  const rect = renderer.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, camera)
  const intersection = new THREE.Vector3()
  raycaster.ray.intersectPlane(dragPlane, intersection)

  const newPos = intersection.add(dragOffset)
  newPos.y = 1.5
  draggedPiece.mesh.position.copy(newPos)
  draggedPiece.body.body.setTranslation({ x: newPos.x, y: newPos.y, z: newPos.z }, true)
}
function onPointerUp(): void {
  if (!isDragging || !draggedPiece) return
  isDragging = false
  const piece = draggedPiece
  draggedPiece = null
  const piecePos = piece.mesh.position
  let closestSlot: SlotState | undefined
  let minDist = Infinity

  for (const slot of slots) {
    const dist = piecePos.distanceTo(slot.position)
    if (dist < minDist) {
      minDist = dist
      closestSlot = slot
    }
  }

  const threshold = 0.5
  if (closestSlot && minDist < threshold) {
    piece.slotId = closestSlot.id
    closestSlot.occupiedBy = piece.id
    const targetPos = closestSlot.position

    if (!reducedMotion.value && timeline) {
      timeline.add(piece.mesh.position, {
        x: targetPos.x,
        y: 0.2,
        z: targetPos.z,
        duration: 300,
        ease: easeOutBack,
      })
    } else {
      piece.mesh.position.copy(targetPos)
      piece.mesh.position.y = 0.2
    }

    piece.body.body.setTranslation({ x: targetPos.x, y: 0.2, z: targetPos.z }, true)
    piece.body.body.setBodyType(1, true)
    playClickPop()
    hasAnyPlacement.value = true
  } else {
    piece.body.body.setBodyType(0, true)
    piece.mesh.position.copy(piece.trayPosition)
    piece.body.body.setTranslation(
      { x: piece.trayPosition.x, y: piece.trayPosition.y, z: piece.trayPosition.z },
      true
    )
    playDropThunk()
  }
  saveSessionState()
}
function evaluatePlacement(): ChallengeVerdict {
  const totalSlots = props.config.slots.length
  let correctCount = 0

  pieces.forEach(piece => {
    if (piece.slotId) {
      const slot = slots.find(s => s.id === piece.slotId)
      if (slot && slot.expectedObjectId === piece.id) correctCount++
    }
  })

  if (correctCount === totalSlots) return 'correct'
  if (correctCount > 0) return 'close'
  return 'wrong'
}
function checkAnswer(): void {
  attemptCount.value++
  const verdict = evaluatePlacement()
  feedbackVerdict.value = verdict
  if (verdict === 'correct') {
    completed.value = true
    feedbackMessage.value = t('learning.challenge.correct')
    if (containerRef.value) triggerSuccessFeedback(containerRef.value)
    try { sessionStorage.removeItem(SESSION_KEY) } catch { /* ignore */ }
  } else if (verdict === 'close') {
    feedbackMessage.value = t('learning.challenge.almost')
    if (containerRef.value) triggerErrorFeedback(containerRef.value)
  } else {
    feedbackMessage.value = t('learning.challenge.tryAgain')
    if (containerRef.value) triggerErrorFeedback(containerRef.value)
  }
}
function onContinue(): void {
  completed.value = false
  feedbackMessage.value = ''
  feedbackVerdict.value = null
  attemptCount.value = 0
  pieces.forEach(piece => {
    piece.slotId = null
    piece.mesh.position.copy(piece.trayPosition)
    piece.body.body.setTranslation(
      { x: piece.trayPosition.x, y: piece.trayPosition.y, z: piece.trayPosition.z },
      true
    )
    piece.body.body.setBodyType(0, true)
  })

  slots.forEach(slot => { slot.occupiedBy = null })
  hasAnyPlacement.value = false
  try { sessionStorage.removeItem(SESSION_KEY) } catch { /* ignore */ }
  emit('complete')
}
function animate(): void {
  if (!renderer || !scene || !camera) return
  animationFrameId = requestAnimationFrame(animate)
  tickDriver(performance.now())
  stepPhysics(1 / 60)
  renderer.render(scene, camera)
}
function onResize(): void {
  if (!renderer || !camera || !containerRef.value) return
  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}
function onVisibilityChange(): void {
  if (document.hidden) {
    if (animationFrameId !== null) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
  } else if (animationFrameId === null) animate()
}
onMounted(async () => {
  await initRapier()
  initializeScene()
  if (renderer && containerRef.value) {
    renderer.domElement.addEventListener('pointerdown', onPointerDown)
    renderer.domElement.addEventListener('pointermove', onPointerMove)
    renderer.domElement.addEventListener('pointerup', onPointerUp)
    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', onVisibilityChange)
    animate()
  }
})
onBeforeUnmount(() => {
  if (animationFrameId !== null) cancelAnimationFrame(animationFrameId)
  if (renderer && containerRef.value) {
    renderer.domElement.removeEventListener('pointerdown', onPointerDown)
    renderer.domElement.removeEventListener('pointermove', onPointerMove)
    renderer.domElement.removeEventListener('pointerup', onPointerUp)
    window.removeEventListener('resize', onResize)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    containerRef.value.removeChild(renderer.domElement)
    renderer.dispose()
  }
  if (timeline) timeline.revert()
  pieces.forEach(piece => {
    piece.mesh.geometry.dispose()
    ;(piece.mesh.material as THREE.Material).dispose()
  })
  slots.forEach(slot => {
    slot.outlineMesh.geometry.dispose()
    ;(slot.outlineMesh.material as THREE.Material).dispose()
  })
  pieces.length = 0
  slots.length = 0
})
onActivated(() => {
  if (animationFrameId === null) animate()
})
onDeactivated(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }
})
</script>

<style scoped>
.puzzle-3d-container {
  width: 100%;
  height: 400px;
  position: relative;
  touch-action: none;
}
</style>
