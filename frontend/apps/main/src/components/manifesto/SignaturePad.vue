<template>
  <div class="signature-pad-container">
    <canvas
      ref="canvasRef"
      class="signature-canvas"
      :style="{ width: width + 'px', height: height + 'px' }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
    />
    <van-button size="small" @click="clear">{{ t('manifesto.clearSignature') }}</van-button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  width?: number
  height?: number
  penColor?: string
}>(), {
  width: 300,
  height: 150,
  penColor: 'var(--color-ink)',
})

const canvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let drawing = false
let lastX = 0
let lastY = 0
let lastTime = 0
let hasDrawn = false

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
  const pos = getPos(e)
  lastX = pos.x
  lastY = pos.y
  lastTime = Date.now()
}

function onPointerMove(e: PointerEvent) {
  if (!drawing || !ctx) return
  e.preventDefault()
  const pos = getPos(e)
  const now = Date.now()
  const dt = now - lastTime
  const dist = Math.hypot(pos.x - lastX, pos.y - lastY)
  const velocity = dt > 0 ? dist / dt : 0

  // Velocity-based stroke width: thinner when faster
  const minWidth = 1.5
  const maxWidth = 3
  const lineWidth = Math.max(minWidth, maxWidth - velocity * 2)

  ctx.lineWidth = lineWidth
  ctx.beginPath()
  ctx.moveTo(lastX, lastY)
  ctx.lineTo(pos.x, pos.y)
  ctx.stroke()

  lastX = pos.x
  lastY = pos.y
  lastTime = now
  hasDrawn = true
}

function onPointerUp(e: PointerEvent) {
  if (drawing) {
    e.preventDefault()
  }
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
.signature-pad-container {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
}

.signature-canvas {
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: 8px;
  background: var(--card-bg, #fff);
  touch-action: none;
  cursor: crosshair;
}
</style>
