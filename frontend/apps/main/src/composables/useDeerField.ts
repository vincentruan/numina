import { onMounted, onUnmounted, type Ref } from 'vue'

// Two-layer background system:
//   bgCanvas  — stellar particles with bright cores + irregular halos
//   deerCanvas — dim lavender pixel grid masked to deer SVG silhouette (unchanged)

// ── Deer pixel grid constants (unchanged) ──────────────────────────────────────
const CELL_SIZE = 4
const CELL_GAP = 1
const MAX_ALPHA = 0.45
const FLICKER_RATE = 0.06

// ── Stellar particle constants ────────────────────────────────────────────────
const SPRITE_SIZE = 64
const SPRITE_DPR_MAX = 2
const SPRITE_COUNT = 15

const FAR_RATIO = 0.50
const MID_RATIO = 0.35
const NEAR_RATIO = 0.15

const FAR_RADIUS_MIN = 0.5
const FAR_RADIUS_MAX = 1.2
const FAR_OPACITY_MIN = 0.25
const FAR_OPACITY_MAX = 0.45
const FAR_SPEED_MIN = 3
const FAR_SPEED_MAX = 6

const MID_RADIUS_MIN = 1.2
const MID_RADIUS_MAX = 2.2
const MID_OPACITY_MIN = 0.45
const MID_OPACITY_MAX = 0.65
const MID_SPEED_MIN = 8
const MID_SPEED_MAX = 14

const NEAR_RADIUS_MIN = 2.2
const NEAR_RADIUS_MAX = 3.8
const NEAR_OPACITY_MIN = 0.65
const NEAR_OPACITY_MAX = 0.90
const NEAR_SPEED_MIN = 15
const NEAR_SPEED_MAX = 25

const BREATH_SPEED_MIN = 0.15
const BREATH_SPEED_MAX = 0.35
const BREATH_SIZE_AMP_MIN = 0.20
const BREATH_SIZE_AMP_MAX = 0.45
const BREATH_OPACITY_AMP_MIN = 0.30
const BREATH_OPACITY_AMP_MAX = 0.55

const CCW_BIAS_MIN = 30
const CCW_BIAS_MAX = 60
const NOISE_ANGLE_DELTA = 15
const TURN_RATE = 0.08

const HALO_MARGIN_MULTIPLIER = 5

const STELLAR_COLORS: Array<{ core: [number, number, number]; halo: [number, number, number]; ratio: number }> = [
  { core: [255, 255, 255], halo: [180, 210, 255], ratio: 0.15 },
  { core: [255, 255, 255], halo: [230, 235, 255], ratio: 0.30 },
  { core: [255, 250, 235], halo: [255, 230, 180], ratio: 0.30 },
  { core: [255, 235, 210], halo: [255, 200, 150], ratio: 0.20 },
  { core: [255, 220, 200], halo: [255, 170, 120], ratio: 0.05 },
]

const INTENSITY_LEVELS = ['soft', 'medium', 'bright'] as const
type IntensityLevel = typeof INTENSITY_LEVELS[number]

const PARTICLE_COUNT_BASE = 180
const REFERENCE_AREA = 375 * 668
const PARTICLE_COUNT_MIN = 90
const PARTICLE_COUNT_MAX = 420

interface Grid {
  cols: number
  rows: number
  alphas: Float32Array
  dpr: number
}

interface Particle {
  x: number
  y: number
  depth: 'far' | 'mid' | 'near'
  baseRadius: number
  baseOpacity: number
  driftSpeed: number
  spriteIndex: number
  breathPhase: number
  breathSpeed: number
  breathSizeAmp: number
  breathOpacityAmp: number
  vx: number
  vy: number
  noiseOffsetX: number
  noiseOffsetY: number
  currentRadius: number
  currentOpacity: number
}

interface StarSprite {
  canvas: HTMLCanvasElement
  colorTempIndex: number
  intensityIndex: number
}

function debounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let id: ReturnType<typeof setTimeout> | null = null
  return ((...args: unknown[]) => {
    if (id) clearTimeout(id)
    id = setTimeout(() => fn(...args), delay)
  }) as T
}

function rand(min: number, max: number) {
  return min + Math.random() * (max - min)
}

// ── Deer grid helpers ──────────────────────────────────────────────────────

function buildGrid(canvas: HTMLCanvasElement, w: number, h: number): Grid {
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.width = w * dpr
  canvas.height = h * dpr

  const step = CELL_SIZE + CELL_GAP
  const cols = Math.floor(w / step)
  const rows = Math.floor(h / step)
  const alphas = new Float32Array(cols * rows)
  for (let i = 0; i < alphas.length; i++) {
    alphas[i] = Math.random() * MAX_ALPHA
  }
  return { cols, rows, alphas, dpr }
}

function flickerGrid(alphas: Float32Array, dt: number) {
  const prob = FLICKER_RATE * dt
  for (let i = 0; i < alphas.length; i++) {
    if (Math.random() < prob) {
      alphas[i] = Math.random() * MAX_ALPHA
    }
  }
}

function drawGrid(ctx: CanvasRenderingContext2D, grid: Grid) {
  const { cols, rows, alphas, dpr } = grid
  const step = (CELL_SIZE + CELL_GAP) * dpr
  const size = CELL_SIZE * dpr

  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const a = alphas[c * rows + r]
      if (a < 0.01) continue
      ctx.fillStyle = `rgba(189,187,255,${a})`
      ctx.fillRect(c * step, r * step, size, size)
    }
  }
}

// ── Sprite generation helpers ───────────────────────────────────────────────

const SPRITE_INTERNAL_SIZE = SPRITE_SIZE * SPRITE_DPR_MAX

function simpleNoise2D(x: number, y: number): number {
  const v1 = Math.sin(x * 0.01) * Math.cos(y * 0.01)
  const v2 = Math.sin(x * 0.02 + 1.5) * Math.cos(y * 0.015 + 0.7)
  const v3 = Math.sin(x * 0.005 + y * 0.008)
  return (v1 + v2 * 0.5 + v3 * 0.25) / 1.75
}

function generateStarSprite(
  colorTempIndex: number,
  intensityIndex: number,
  dpr: number = SPRITE_DPR_MAX
): HTMLCanvasElement {
  const sprite = document.createElement('canvas')
  const size = SPRITE_SIZE * dpr
  sprite.width = size
  sprite.height = size
  const ctx = sprite.getContext('2d')!
  const cx = size / 2
  const cy = size / 2

  const colorSpec = STELLAR_COLORS[colorTempIndex]
  const [coreR, coreG, coreB] = colorSpec.core
  const [haloR, haloG, haloB] = colorSpec.halo

  const intensityMult = intensityIndex === 2 ? 1.4 : intensityIndex === 1 ? 1.0 : 0.7
  const rayCount = Math.floor((8 + Math.random() * 6) * intensityMult)
  const baseHaloRadius = (size / 2 - 4) * intensityMult

  // 1. Circular glow underlayer
  const glowRadius = baseHaloRadius * 0.9
  const glowGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowRadius)
  glowGrad.addColorStop(0, `rgba(${haloR},${haloG},${haloB},0.35)`)
  glowGrad.addColorStop(0.5, `rgba(${haloR},${haloG},${haloB},0.08)`)
  glowGrad.addColorStop(1, `rgba(${haloR},${haloG},${haloB},0)`)
  ctx.beginPath()
  ctx.arc(cx, cy, glowRadius, 0, Math.PI * 2)
  ctx.fillStyle = glowGrad
  ctx.fill()

  // 2. Irregular radiating rays
  ctx.save()
  ctx.translate(cx, cy)

  for (let i = 0; i < rayCount; i++) {
    const angle = (i / rayCount) * Math.PI * 2 + Math.random() * 0.3
    const rayLength = baseHaloRadius * (0.6 + Math.random() * 0.8)
    const rayWidth = (2 + Math.random() * 4) * dpr
    const rayOpacity = 0.12 + Math.random() * 0.15

    const endX = Math.cos(angle) * rayLength
    const endY = Math.sin(angle) * rayLength
    const rayGrad = ctx.createLinearGradient(0, 0, endX, endY)
    rayGrad.addColorStop(0, `rgba(${haloR},${haloG},${haloB},0.25)`)
    rayGrad.addColorStop(0.4, `rgba(${haloR},${haloG},${haloB},${rayOpacity.toFixed(3)})`)
    rayGrad.addColorStop(0.8, `rgba(${haloR},${haloG},${haloB},0.03)`)
    rayGrad.addColorStop(1, `rgba(${haloR},${haloG},${haloB},0)`)

    ctx.beginPath()
    ctx.moveTo(0, 0)
    ctx.lineTo(endX, endY)
    ctx.strokeStyle = rayGrad
    ctx.lineWidth = rayWidth
    ctx.lineCap = 'round'
    ctx.stroke()
  }

  ctx.restore()

  // 3. Bright core
  const coreRadius = 4 * dpr
  const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius)
  coreGrad.addColorStop(0, `rgba(255,255,255,1.0)`)
  coreGrad.addColorStop(0.3, `rgba(255,255,255,0.95)`)
  coreGrad.addColorStop(0.6, `rgba(${coreR},${coreG},${coreB},0.7)`)
  coreGrad.addColorStop(1, `rgba(${coreR},${coreG},${coreB},0)`)
  ctx.beginPath()
  ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2)
  ctx.fillStyle = coreGrad
  ctx.fill()

  return sprite
}

function buildSprites(dpr: number = SPRITE_DPR_MAX): StarSprite[] {
  const sprites: StarSprite[] = []
  for (let tempIdx = 0; tempIdx < STELLAR_COLORS.length; tempIdx++) {
    for (let intIdx = 0; intIdx < INTENSITY_LEVELS.length; intIdx++) {
      sprites.push({
        canvas: generateStarSprite(tempIdx, intIdx, dpr),
        colorTempIndex: tempIdx,
        intensityIndex: intIdx,
      })
    }
  }
  return sprites
}

// ── Particle helpers ───────────────────────────────────────────────────────

function computeParticleCount(w: number, h: number): number {
  const area = w * h
  const scale = Math.sqrt(area / REFERENCE_AREA)

  if (w >= 1280) return Math.min(PARTICLE_COUNT_MAX, Math.round(PARTICLE_COUNT_BASE * scale))
  if (w >= 768) return Math.min(320, Math.round(PARTICLE_COUNT_BASE * scale))

  const heightFactor = h / 668
  return Math.round(PARTICLE_COUNT_BASE * Math.max(0.85, Math.min(1.15, heightFactor)))
}

function assignDepthLayer(): 'far' | 'mid' | 'near' {
  const r = Math.random()
  if (r < FAR_RATIO) return 'far'
  if (r < FAR_RATIO + MID_RATIO) return 'mid'
  return 'near'
}

function assignColorTemp(): number {
  const r = Math.random()
  let cumulative = 0
  for (let i = 0; i < STELLAR_COLORS.length; i++) {
    cumulative += STELLAR_COLORS[i].ratio
    if (r < cumulative) return i
  }
  return STELLAR_COLORS.length - 1
}

function getDepthParams(depth: 'far' | 'mid' | 'near') {
  switch (depth) {
    case 'far':
      return {
        radiusMin: FAR_RADIUS_MIN, radiusMax: FAR_RADIUS_MAX,
        opacityMin: FAR_OPACITY_MIN, opacityMax: FAR_OPACITY_MAX,
        speedMin: FAR_SPEED_MIN, speedMax: FAR_SPEED_MAX,
      }
    case 'mid':
      return {
        radiusMin: MID_RADIUS_MIN, radiusMax: MID_RADIUS_MAX,
        opacityMin: MID_OPACITY_MIN, opacityMax: MID_OPACITY_MAX,
        speedMin: MID_SPEED_MIN, speedMax: MID_SPEED_MAX,
      }
    case 'near':
      return {
        radiusMin: NEAR_RADIUS_MIN, radiusMax: NEAR_RADIUS_MAX,
        opacityMin: NEAR_OPACITY_MIN, opacityMax: NEAR_OPACITY_MAX,
        speedMin: NEAR_SPEED_MIN, speedMax: NEAR_SPEED_MAX,
      }
  }
}

function initParticleFlow(p: Particle, w: number, h: number): void {
  const cx = w / 2
  const cy = h / 2
  const toCenterAngle = Math.atan2(cy - p.y, cx - p.x)
  const biasOffset = (CCW_BIAS_MIN + Math.random() * (CCW_BIAS_MAX - CCW_BIAS_MIN)) * Math.PI / 180
  const baseAngle = toCenterAngle + biasOffset + Math.PI
  const noiseAngle = baseAngle + (Math.random() - 0.5) * 80 * Math.PI / 180

  p.vx = Math.cos(noiseAngle) * p.driftSpeed
  p.vy = Math.sin(noiseAngle) * p.driftSpeed
  p.noiseOffsetX = Math.random() * 1000
  p.noiseOffsetY = Math.random() * 1000
}

function buildParticles(w: number, h: number): Particle[] {
  const particles: Particle[] = []
  const count = computeParticleCount(w, h)

  for (let i = 0; i < count; i++) {
    const depth = assignDepthLayer()
    const params = getDepthParams(depth)
    const colorTempIdx = assignColorTemp()
    const intensityIdx = Math.floor(Math.random() * INTENSITY_LEVELS.length)

    const baseRadius = rand(params.radiusMin, params.radiusMax)
    const baseOpacity = rand(params.opacityMin, params.opacityMax)
    const driftSpeed = rand(params.speedMin, params.speedMax)

    const p: Particle = {
      x: Math.random() * w,
      y: Math.random() * h,
      depth,
      baseRadius,
      baseOpacity,
      driftSpeed,
      spriteIndex: colorTempIdx * INTENSITY_LEVELS.length + intensityIdx,
      breathPhase: Math.random(),
      breathSpeed: rand(BREATH_SPEED_MIN, BREATH_SPEED_MAX),
      breathSizeAmp: rand(BREATH_SIZE_AMP_MIN, BREATH_SIZE_AMP_MAX),
      breathOpacityAmp: rand(BREATH_OPACITY_AMP_MIN, BREATH_OPACITY_AMP_MAX),
      vx: 0,
      vy: 0,
      noiseOffsetX: 0,
      noiseOffsetY: 0,
      currentRadius: baseRadius,
      currentOpacity: baseOpacity,
    }

    initParticleFlow(p, w, h)
    particles.push(p)
  }

  return particles
}

function updateBreathing(p: Particle, dt: number): void {
  p.breathPhase = (p.breathPhase + p.breathSpeed * dt) % 1
  const breathWave = (Math.sin(p.breathPhase * Math.PI * 2) + 1) / 2
  p.currentRadius = p.baseRadius * (1 + p.breathSizeAmp * breathWave)
  p.currentOpacity = p.baseOpacity * (1 + p.breathOpacityAmp * breathWave)
}

function updateFlowField(p: Particle, dt: number, time: number): void {
  const noiseVal = simpleNoise2D(
    p.noiseOffsetX + time * 0.05,
    p.noiseOffsetY + time * 0.05
  )
  const noiseDelta = noiseVal * NOISE_ANGLE_DELTA * Math.PI / 180

  const currentAngle = Math.atan2(p.vy, p.vx)
  const targetAngle = currentAngle + noiseDelta
  const newAngle = currentAngle + (targetAngle - currentAngle) * TURN_RATE

  const newSpeed = p.driftSpeed * (0.95 + Math.random() * 0.1)

  p.vx = Math.cos(newAngle) * newSpeed
  p.vy = Math.sin(newAngle) * newSpeed
  p.x += p.vx * dt
  p.y += p.vy * dt
}

function wrapEdges(p: Particle, w: number, h: number): void {
  const margin = p.currentRadius * HALO_MARGIN_MULTIPLIER
  if (p.x < -margin) p.x = w + margin
  else if (p.x > w + margin) p.x = -margin
  if (p.y < -margin) p.y = h + margin
  else if (p.y > h + margin) p.y = -margin
}

function updateParticles(particles: Particle[], dt: number, w: number, h: number, time: number): void {
  for (const p of particles) {
    updateBreathing(p, dt)
    updateFlowField(p, dt, time)
    wrapEdges(p, w, h)
  }
}

function drawParticles(
  ctx: CanvasRenderingContext2D,
  particles: Particle[],
  sprites: StarSprite[],
  dpr: number
): void {
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height)

  for (const p of particles) {
    const sprite = sprites[p.spriteIndex]
    const finalSize = p.currentRadius * dpr * SPRITE_DPR_MAX
    const drawX = p.x * dpr - finalSize / 2
    const drawY = p.y * dpr - finalSize / 2

    ctx.globalAlpha = p.currentOpacity
    ctx.drawImage(sprite.canvas, drawX, drawY, finalSize, finalSize)
  }

  ctx.globalAlpha = 1
}

// ── Main composable ────────────────────────────────────────────────────────

export function useDeerField(
  bgCanvasRef: Ref<HTMLCanvasElement | null>,
  deerCanvasRef: Ref<HTMLCanvasElement | null>,
) {
  let rafId: number | null = null
  let bgCtx: CanvasRenderingContext2D | null = null
  let deerCtx: CanvasRenderingContext2D | null = null
  let grid: Grid | null = null
  let particles: Particle[] = []
  let sprites: StarSprite[] = []
  let animTime = 0
  let bgDpr = 1
  let vpW = 0
  let vpH = 0
  let lastTime = 0
  let paused = false
  let handleResize: (() => void) | null = null
  let handleVisibility: (() => void) | null = null
  let maskBlobUrl: string | null = null

  function resize() {
    const bg = bgCanvasRef.value
    const deer = deerCanvasRef.value
    if (!bg || !deer) return

    vpW = window.innerWidth
    vpH = window.innerHeight

    bgDpr = Math.min(window.devicePixelRatio || 1, 2)
    bg.width = vpW * bgDpr
    bg.height = vpH * bgDpr
    bg.style.width = `${vpW}px`
    bg.style.height = `${vpH}px`
    bgCtx = bg.getContext('2d')
    bgCtx?.setTransform(1, 0, 0, 1, 0, 0)

    deer.style.width = `${vpW}px`
    deer.style.height = `${vpH}px`
    grid = buildGrid(deer, vpW, vpH)
    deerCtx = deer.getContext('2d')
    deerCtx?.setTransform(1, 0, 0, 1, 0, 0)

    particles = buildParticles(vpW, vpH)
  }

  function loop(ts: number) {
    if (!paused && bgCtx && deerCtx && grid && sprites.length > 0) {
      const dt = lastTime === 0 ? 0.016 : Math.min((ts - lastTime) / 1000, 0.1)
      lastTime = ts
      animTime += dt

      updateParticles(particles, dt, vpW, vpH, animTime)
      drawParticles(bgCtx, particles, sprites, bgDpr)

      flickerGrid(grid.alphas, dt)
      drawGrid(deerCtx, grid)
    }
    rafId = requestAnimationFrame(loop)
  }

  function applyMask(url: string) {
    const deer = deerCanvasRef.value
    if (!deer) return
    deer.style.webkitMaskImage = `url("${url}")`
    deer.style.maskImage = `url("${url}")`
  }

  function start() {
    resize()
    sprites = buildSprites(bgDpr)

    fetch('/images/deer.svg')
      .then((r) => r.blob())
      .then((blob) => {
        maskBlobUrl = URL.createObjectURL(blob)
        applyMask(maskBlobUrl)
      })
      .catch(() => {
        applyMask('/images/deer.svg')
      })

    handleResize = debounce(resize, 150)
    window.addEventListener('resize', handleResize)

    handleVisibility = () => {
      paused = document.hidden
      if (!paused) lastTime = 0
    }
    document.addEventListener('visibilitychange', handleVisibility)

    rafId = requestAnimationFrame(loop)
  }

  function stop() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    if (handleResize) {
      window.removeEventListener('resize', handleResize)
      handleResize = null
    }
    if (handleVisibility) {
      document.removeEventListener('visibilitychange', handleVisibility)
      handleVisibility = null
    }
    if (maskBlobUrl) {
      URL.revokeObjectURL(maskBlobUrl)
      maskBlobUrl = null
    }
    sprites = []
    animTime = 0
  }

  onMounted(start)
  onUnmounted(stop)
}
