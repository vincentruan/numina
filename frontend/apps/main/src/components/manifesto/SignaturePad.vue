<template>
  <div ref="containerRef" class="signature-pad-container">
    <canvas
      ref="canvasRef"
      class="signature-canvas"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    />
    <van-button size="small" @click="clear">{{ t('manifesto.clearSignature') }}</van-button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  height?: number
  penColor?: string
}>(), {
  height: 150,
  penColor: 'var(--color-ink)',
})

const emit = defineEmits<{
  draw: []
}>()

const TAIL_SIZE = 5
const REFERENCE_VELOCITY = 2.0 // px/ms — above this, stroke reaches minimum width

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let drawing = false
let lastX = 0
let lastY = 0
let lastTime = 0
let lastMidX = 0
let lastMidY = 0
let hasDrawn = false
let resolvedWidth = 300
let strokeBuffer: { x: number; y: number; width: number }[] = []
let activePointerId: number | null = null

function measureWidth(): number {
  if (containerRef.value) {
    return containerRef.value.clientWidth
  }
  return 300
}

function initCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const dpr = window.devicePixelRatio || 1
  resolvedWidth = measureWidth()
  canvas.width = resolvedWidth * dpr
  canvas.height = props.height * dpr
  ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.scale(dpr, dpr)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  // Resolve CSS variable for penColor
  const resolvedColor = getCSSVariableValue(props.penColor)
  ctx.strokeStyle = resolvedColor
}

function getCSSVariableValue(color: string): string {
  if (color.startsWith('var(')) {
    const varName = color.slice(4, -1).trim()
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || '#000'
  }
  return color
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
  ctx.clearRect(0, 0, resolvedWidth, props.height)
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

let resizeObserver: ResizeObserver | null = null

function onResize() {
  const newWidth = measureWidth()
  if (newWidth !== resolvedWidth) {
    initCanvas()
  }
}

onMounted(async () => {
  await nextTick()
  initCanvas()
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(onResize)
    resizeObserver.observe(containerRef.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  ctx = null
})
</script>

<style scoped>
.signature-pad-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.signature-canvas {
  width: 100%;
  height: auto;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: 8px;
  background: var(--card-bg, #fff);
  touch-action: none;
  cursor: crosshair;
}
</style>
