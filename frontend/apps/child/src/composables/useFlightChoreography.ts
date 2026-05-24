/**
 * 飞行编排：在 popup 关闭后驱动 stars → balance card 的整套时序，
 * 包括星星抛物线、每次落点的触觉反馈、余额卡的视觉反应、
 * 终点的呼吸光晕，以及减少动效模式下的 toast 短路。
 *
 * 该 composable 不持有 DOM；它通过响应式 state + 回调与
 * <CelebrationAnimation> 协作，由后者实例化 <FlyToTarget> 等组件。
 */

import { ref, type Ref } from 'vue'
import { tryVibrate } from './useHaptic'
import { useReducedMotion } from './useReducedMotion'
import { MOTION } from '@/utils/motionTokens'
import { bezierPath, type Point } from '@/utils/bezier'

export type FlightPhase =
  | 'idle'
  | 'gathering'
  | 'flight'
  | 'glow'
  | 'breathing'
  | 'reduced-flash'
  | 'done'

export interface FlightRunOptions {
  origins: Array<HTMLElement | Point | null>
  target: HTMLElement | Point | null
  starsEarned: number
  taskCount: number
  reducedMotionToast: (stars: number) => void
  onBalanceReact: (mode: 'pop' | 'invert') => void
  onBalanceReactEnd: () => void
  onLandingTrail?: (path: string) => void
  onComplete: () => void
}

export interface FlightChoreography {
  phase: Readonly<Ref<FlightPhase>>
  reducedMotion: Readonly<Ref<boolean>>
  run: (opts: FlightRunOptions) => void
  cancel: () => void
  notifyLanding: (origin: Point, target: Point) => void
  notifyAllLanded: () => void
}

export function useFlightChoreography(): FlightChoreography {
  const phase = ref<FlightPhase>('idle')
  const reducedMotion = useReducedMotion()

  let activeOpts: FlightRunOptions | null = null
  let firstLandingFired = false
  const timers: Array<ReturnType<typeof setTimeout>> = []

  function clearTimers(): void {
    timers.forEach(clearTimeout)
    timers.length = 0
  }

  function pushTimer(fn: () => void, ms: number): void {
    timers.push(setTimeout(fn, ms))
  }

  function resolvePoint(input: HTMLElement | Point | null): Point | null {
    if (!input) return null
    if (input instanceof HTMLElement) {
      const r = input.getBoundingClientRect()
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
    }
    return input
  }

  function runReducedMotionPath(opts: FlightRunOptions): void {
    phase.value = 'reduced-flash'
    opts.reducedMotionToast(opts.starsEarned)
    opts.onBalanceReact('invert')
    pushTimer(() => {
      opts.onBalanceReactEnd()
    }, 400)
    pushTimer(() => {
      phase.value = 'done'
      opts.onComplete()
    }, 2500)
  }

  function run(opts: FlightRunOptions): void {
    cancel()
    activeOpts = opts
    firstLandingFired = false

    if (reducedMotion.value) {
      runReducedMotionPath(opts)
      return
    }

    const targetPt = resolvePoint(opts.target)
    if (!targetPt) {
      phase.value = 'done'
      opts.onComplete()
      return
    }

    phase.value = opts.taskCount > 1 ? 'gathering' : 'flight'
    // Particle motion is owned by <FlyToTarget>; phase advances via notifyLanding
    // and notifyAllLanded callbacks. The watchdog below ensures the orchestrator
    // never hangs if those callbacks misfire (DOM detached, particle ref nulls,
    // resize mid-flight). 10s is generous: longest legitimate path is multi-task
    // batch ≈1.4s flight + 3s breathing + headroom.
    pushTimer(() => {
      if (phase.value !== 'done') {
        phase.value = 'done'
        opts.onBalanceReactEnd()
        opts.onComplete()
        activeOpts = null
      }
    }, 10000)
  }

  function notifyLanding(origin: Point, target: Point): void {
    if (!activeOpts) return
    tryVibrate(MOTION.haptic.landing)
    if (activeOpts.onLandingTrail) {
      activeOpts.onLandingTrail(bezierPath(origin, target, 200))
    }
    if (!firstLandingFired) {
      firstLandingFired = true
      activeOpts.onBalanceReact('pop')
      phase.value = 'glow'
    }
  }

  function notifyAllLanded(): void {
    if (!activeOpts) return
    const opts = activeOpts
    pushTimer(() => {
      opts.onBalanceReactEnd()
      phase.value = 'breathing'
    }, MOTION.durations.fast + MOTION.durations.medium) // ~600ms after last landing
    pushTimer(() => {
      phase.value = 'done'
      opts.onComplete()
    }, MOTION.durations.glacial + MOTION.durations.medium) // 3s breathing + 400ms tail
  }

  function cancel(): void {
    clearTimers()
    if (activeOpts && phase.value !== 'idle' && phase.value !== 'done') {
      activeOpts.onBalanceReactEnd()
      activeOpts.onComplete()
    }
    activeOpts = null
    phase.value = 'idle'
    firstLandingFired = false
  }

  return {
    phase,
    reducedMotion,
    run,
    cancel,
    notifyLanding,
    notifyAllLanded,
  }
}
