import { onMounted, onUnmounted, type Ref } from 'vue'

interface Particle {
  x: number
  y: number
  alpha: number
  baseAlpha: number
  r: number
  twinklePhase: number
  twinkleSpeed: number
}

function random(min: number, max: number): number {
  return Math.random() * (max - min) + min
}

function debounce<T extends (...args: unknown[]) => void>(fn: T, delay: number): T {
  let id: ReturnType<typeof setTimeout> | null = null
  return ((...args: unknown[]) => {
    if (id) clearTimeout(id)
    id = setTimeout(() => fn(...args), delay)
  }) as T
}

export function useDeerField(
  bgCanvasRef: Ref<HTMLCanvasElement | null>,
  deerCanvasRef: Ref<HTMLCanvasElement | null>,
) {
  let rafId: number | null = null
  let bgCtx: CanvasRenderingContext2D | null = null
  let deerCtx: CanvasRenderingContext2D | null = null
  let particles: Particle[] = []
  let w = 0
  let h = 0
  let handleResize: (() => void) | null = null
  let handleVisibility: (() => void) | null = null
  let paused = false
  const PARTICLE_COUNT = 280

  function resize() {
    if (!bgCanvasRef.value || !deerCanvasRef.value) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    w = window.innerWidth
    h = window.innerHeight

    for (const canvas of [bgCanvasRef.value, deerCanvasRef.value]) {
      canvas.width = w * dpr
      canvas.height = h * dpr
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
    }

    bgCtx = bgCanvasRef.value.getContext('2d')
    deerCtx = deerCanvasRef.value.getContext('2d')
    bgCtx?.setTransform(dpr, 0, 0, dpr, 0, 0)
    deerCtx?.setTransform(dpr, 0, 0, dpr, 0, 0)

    initParticles()
  }

  function initParticles() {
    particles = []
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const baseAlpha = random(0.04, 0.18)
      particles.push({
        x: random(0, w),
        y: random(0, h),
        r: random(0.5, 2.2),
        alpha: baseAlpha,
        baseAlpha,
        twinklePhase: random(0, Math.PI * 2),
        twinkleSpeed: random(0.008, 0.025),
      })
    }
  }

  function draw() {
    if (!bgCtx || !deerCtx) return

    bgCtx.clearRect(0, 0, w, h)
    deerCtx.clearRect(0, 0, w, h)

    for (const p of particles) {
      p.twinklePhase += p.twinkleSpeed
      p.alpha = Math.max(0.02, Math.min(0.22, p.baseAlpha + Math.sin(p.twinklePhase) * 0.07))

      // Draw on bg canvas (full field)
      bgCtx.beginPath()
      bgCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      bgCtx.fillStyle = `rgba(255,255,255,${p.alpha})`
      bgCtx.fill()

      // Draw on deer canvas (same particles — CSS mask clips to deer shape)
      deerCtx.beginPath()
      deerCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      deerCtx.fillStyle = `rgba(255,255,255,${Math.min(1, p.alpha * 6)})`
      deerCtx.fill()
    }
  }

  function loop() {
    if (!paused) draw()
    rafId = requestAnimationFrame(loop)
  }

  function start() {
    resize()

    handleResize = debounce(resize, 150)
    window.addEventListener('resize', handleResize)

    handleVisibility = () => {
      paused = document.hidden
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
  }

  onMounted(start)
  onUnmounted(stop)
}
