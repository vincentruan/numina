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

const props = withDefaults(
  defineProps<{
    width?: number
    height?: number
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
let hasDrawn = false

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
  const pos = getPos(e)
  lastX = pos.x
  lastY = pos.y
}

function onPointerMove(e: PointerEvent) {
  if (!drawing || !ctx) return
  e.preventDefault()
  const pos = getPos(e)
  ctx.lineWidth = props.strokeWidth
  ctx.beginPath()
  ctx.moveTo(lastX, lastY)
  ctx.lineTo(pos.x, pos.y)
  ctx.stroke()
  lastX = pos.x
  lastY = pos.y
  hasDrawn = true
  emit('draw')
}

function onPointerUp(e: PointerEvent) {
  if (drawing) e.preventDefault()
  drawing = false
}

function clear() {
  const canvas = canvasRef.value
  if (!canvas || !ctx) return
  ctx.clearRect(0, 0, props.width, props.height)
  hasDrawn = false
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
