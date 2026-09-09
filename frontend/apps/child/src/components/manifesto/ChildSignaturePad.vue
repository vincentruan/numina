<template>
  <div class="child-signature-pad">
    <canvas
      ref="canvasRef"
      class="child-signature-canvas"
      :style="{ width: width + 'px', height: height + 'px' }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const TAIL_SIZE = 5
const REFERENCE_VELOCITY = 2.0 // px/ms — above this, stroke reaches minimum width

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
    /** @deprecated Ignored — stroke width is now velocity-driven (calligraphy pipeline) */
    strokeWidth?: number
    penColor?: string
  }>(),
  {
    width: 280,
    height: 120,
    strokeWidth: 2.5,
    penColor: 'var(--color-ink)',
  },
)

const emit = defineEmits<{
  draw: []
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let drawing = false
let lastX = 0
let lastY = 0
let lastTime = 0
let lastMidX = 0
let lastMidY = 0
let hasDrawn = false
let strokeBuffer: { x: number; y: number; width: number }[] = []
let activePointerId: number | null = null

function resolveCSSVariable(color: string): string {
  if (color.startsWith('var(')) {
    const varName = color.slice(4, -1).trim()
    return (
      getComputedStyle(document.documentElement)
        .getPropertyValue(varName)
        .trim() || '#0a0a0a'
    )
  }
  return color
}

function initCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = props.width * dpr
  canvas.height = props.height * dpr
  ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(dpr, dpr)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = resolveCSSVariable(props.penColor)
}

function getPos(e: PointerEvent) {
  const canvas = canvasRef.value!
  const rect = canvas.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function onPointerDown(e: PointerEvent) {
  e.preventDefault()
  drawing = true
  activePointerId = e.pointerId
  const pos = getPos(e)
  lastX = pos.x
  lastY = pos.y
  lastMidX = pos.x
  lastMidY = pos.y
  lastTime = Date.now()
  strokeBuffer = []
}

function onPointerMove(e: PointerEvent) {
  if (!drawing || !ctx || e.pointerId !== activePointerId) return
  e.preventDefault()
  const pos = getPos(e)
  const now = Date.now()
  const dt = now - lastTime
  const dist = Math.hypot(pos.x - lastX, pos.y - lastY)
  const velocity = dt > 0 ? dist / dt : 0

  // Non-linear velocity-to-width mapping: sqrt ease-out (R2)
  const normalizedVelocity = Math.min(Math.max(velocity / REFERENCE_VELOCITY, 0), 1)
  const lineWidth = 1.0 + 2.5 * (1 - Math.sqrt(normalizedVelocity))

  // Push point into stroke buffer (U2)
  strokeBuffer.push({ x: pos.x, y: pos.y, width: lineWidth })

  // Render body — defer last TAIL_SIZE points for taper on pointer-up
  const bodyLen = strokeBuffer.length - TAIL_SIZE
  if (bodyLen >= 2) {
    const i = bodyLen - 1
    const prev = strokeBuffer[i - 1]
    const cur = strokeBuffer[i]
    const midX = (prev.x + cur.x) / 2
    const midY = (prev.y + cur.y) / 2
    ctx.lineWidth = cur.width
    ctx.beginPath()
    ctx.moveTo(lastMidX, lastMidY)
    ctx.quadraticCurveTo(prev.x, prev.y, midX, midY) // R1: Bezier smoothing (KTD2)
    ctx.stroke()
    lastMidX = midX
    lastMidY = midY
  }

  lastX = pos.x
  lastY = pos.y
  lastTime = now
  hasDrawn = true
  emit('draw')
}

function onPointerUp(e: PointerEvent) {
  if (!drawing) return
  if (e.pointerId !== activePointerId) return
  e.preventDefault()
  drawing = false
  activePointerId = null

  if (!ctx || strokeBuffer.length === 0) return

  // Render remaining tail with taper factor (R3, KTD1)
  const totalPoints = strokeBuffer.length
  const tailStartIdx = Math.max(totalPoints - TAIL_SIZE, 0)

  // renderTailFrom connects naturally from lastMidX/Y through lastBody to
  // the first tail midpoint -- no explicit bridge segment needed.
  renderTailFrom(tailStartIdx, totalPoints)
}

function renderTailFrom(startIdx: number, totalPoints: number) {
  if (!ctx || startIdx >= totalPoints) return

  const isShortStroke = totalPoints < 2 * TAIL_SIZE

  for (let i = startIdx; i < totalPoints; i++) {
    const prev = i === 0 ? { x: lastMidX, y: lastMidY } : strokeBuffer[i - 1]
    const cur = strokeBuffer[i]
    const midX = (prev.x + cur.x) / 2
    const midY = (prev.y + cur.y) / 2

    let taperFactor = 1
    // Fade-out at end
    const distFromEnd = totalPoints - 1 - i
    if (distFromEnd < TAIL_SIZE) {
      taperFactor = Math.min(taperFactor, (distFromEnd + 1) / TAIL_SIZE)
    }
    // Fade-in at start (overlaps with fade-out for short strokes)
    if (isShortStroke) {
      taperFactor = Math.min(taperFactor, (i + 1) / totalPoints)
    }

    ctx.lineWidth = cur.width * taperFactor
    ctx.beginPath()
    ctx.moveTo(lastMidX, lastMidY)
    ctx.quadraticCurveTo(prev.x, prev.y, midX, midY)
    ctx.stroke()
    lastMidX = midX
    lastMidY = midY
  }
}

function clear() {
  const canvas = canvasRef.value
  if (!canvas || !ctx) return
  ctx.clearRect(0, 0, props.width, props.height)
  hasDrawn = false
  strokeBuffer = []
}

function isEmpty(): boolean {
  return !hasDrawn
}

function toDataURL(): string {
  return canvasRef.value?.toDataURL('image/png') ?? ''
}

defineExpose({ clear, isEmpty, toDataURL })

onMounted(() => {
  initCanvas()
})

onBeforeUnmount(() => {
  ctx = null
})
</script>

<style scoped>
.child-signature-pad {
  display: inline-flex;
}

.child-signature-canvas {
  border: 2px dashed var(--color-muted-soft, #c0bcb0);
  border-radius: var(--radius-lg, 16px);
  background: var(--color-surface-card, #ffffff);
  touch-action: none;
  cursor: crosshair;
  box-shadow: inset 0 1px 3px rgba(10, 10, 10, 0.04);
}
</style>
