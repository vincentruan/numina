<template>
  <Teleport to="body">
    <Transition name="celebration-fade">
      <div
        v-if="visible"
        class="celebration-host"
        role="dialog"
        aria-modal="true"
        :aria-label="t('celebration.overlayLabel')"
      >
        <TreasureRevealPopup
          :visible="popupVisible"
          :task-count="taskCount"
          :stars-earned="starsEarned"
          :education-reward-coins="educationRewardCoins"
          @confirm="onPopupConfirm"
          @auto-dismiss="onPopupConfirm"
        />

        <FlyToTarget
          :active="flightActive"
          :origin="resolvedOrigins"
          :target="resolvedTarget"
          :particle-count="starCount"
          particle-type="star"
          :duration="800"
          :stagger-ms="80"
          :control-point-offset="200"
          @landing-per-particle="onParticleLanded"
          @all-landed="onAllLanded"
        />

        <StreakLayer
          :active="flightActive"
          :tier="streakTier"
          :origin="resolvedOrigins[0] ?? null"
          :target="resolvedTarget"
        />

        <TrailResidue ref="trailRef" />
        <LandingBurst ref="burstRef" />
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import TreasureRevealPopup from '@/components/celebration/TreasureRevealPopup.vue'
import FlyToTarget from '@/components/celebration/FlyToTarget.vue'
import StreakLayer from '@/components/celebration/StreakLayer.vue'
import TrailResidue from '@/components/celebration/TrailResidue.vue'
import LandingBurst from '@/components/celebration/LandingBurst.vue'
import { useFlightChoreography } from '@/composables/useFlightChoreography'
import type { Point } from '@/utils/bezier'

const props = withDefaults(
  defineProps<{
    visible: boolean
    taskCount: number
    starsEarned: number
    streakTier?: number
    taskRefs?: Map<string, HTMLElement> | null
    balanceRef?: HTMLElement | null
    taskIds?: string[]
    educationRewardCoins?: number
  }>(),
  {
    streakTier: 0,
    taskRefs: null,
    balanceRef: null,
    taskIds: () => [],
    educationRewardCoins: 0,
  },
)

const emit = defineEmits<{
  dismiss: []
  'balance-react': [mode: 'pop' | 'invert']
  'balance-react-end': []
}>()

const { t } = useI18n()

const popupVisible = ref(false)
const flightActive = ref(false)
const trailRef = ref<InstanceType<typeof TrailResidue> | null>(null)
const burstRef = ref<InstanceType<typeof LandingBurst> | null>(null)

const resolvedOrigins = ref<Point[]>([])
const resolvedTarget = ref<Point | null>(null)

const choreo = useFlightChoreography()

const starCount = computed(() => {
  if (props.taskCount <= 1) return Math.min(props.taskCount + 2, 5)
  // Cap at 8 particles to keep total flight time ≤ 1500ms (7×80 + 800 = 1360ms)
  return Math.min(props.taskCount + 2, 8)
})

function resolveElementCenter(el: HTMLElement): Point {
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
}

function clampToViewport(p: Point): Point {
  const margin = 24
  const w = window.innerWidth
  const h = window.innerHeight
  return {
    x: Math.max(margin, Math.min(w - margin, p.x)),
    y: Math.max(margin, Math.min(h - margin, p.y)),
  }
}

function fallbackOrigin(): Point {
  return { x: window.innerWidth * 0.5, y: window.innerHeight * 0.8 }
}

function fallbackTarget(): Point {
  return { x: window.innerWidth * 0.5, y: 100 }
}

function resolvePositionsAtConfirm(): void {
  const origins: Point[] = []
  if (props.taskRefs && props.taskIds.length > 0) {
    for (const id of props.taskIds) {
      const el = props.taskRefs.get(id)
      if (el && el.isConnected) {
        const r = el.getBoundingClientRect()
        if (r.width > 0 && r.height > 0) {
          origins.push(clampToViewport(resolveElementCenter(el)))
          continue
        }
      }
    }
  }
  if (origins.length === 0) origins.push(fallbackOrigin())
  resolvedOrigins.value = origins
  resolvedTarget.value = props.balanceRef ? resolveElementCenter(props.balanceRef) : fallbackTarget()
}

function onPopupConfirm(): void {
  popupVisible.value = false
  resolvePositionsAtConfirm()
  flightActive.value = true
  choreo.run({
    origins: resolvedOrigins.value,
    target: resolvedTarget.value,
    starsEarned: props.starsEarned,
    taskCount: props.taskCount,
    reducedMotionToast: (stars) => {
      showToast({
        message: t('celebration.reducedMotionToast', { stars }),
        duration: 2500,
        position: 'top',
      })
    },
    onBalanceReact: (mode) => emit('balance-react', mode),
    onBalanceReactEnd: () => emit('balance-react-end'),
    onLandingTrail: (d) => trailRef.value?.addPath(d),
    onComplete: () => {
      flightActive.value = false
      emit('dismiss')
    },
  })
}

function onParticleLanded(index: number): void {
  const origin = resolvedOrigins.value[index % resolvedOrigins.value.length] ?? null
  const target = resolvedTarget.value
  if (origin && target) {
    choreo.notifyLanding(origin, target)
    burstRef.value?.spawnBurst(target.x, target.y)
  }
}

function onAllLanded(): void {
  choreo.notifyAllLanded()
  const target = resolvedTarget.value
  if (target && props.starsEarned > 0) {
    burstRef.value?.spawnFloat(target.x, target.y, props.starsEarned)
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      popupVisible.value = true
      flightActive.value = false
    } else {
      popupVisible.value = false
      flightActive.value = false
      choreo.cancel()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  choreo.cancel()
})
</script>

<style scoped>
.celebration-host {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 999;
}

.celebration-host > * {
  pointer-events: auto;
}

.celebration-fade-enter-active,
.celebration-fade-leave-active {
  transition: opacity 200ms ease-out;
}

.celebration-fade-enter-from,
.celebration-fade-leave-to {
  opacity: 0;
}
</style>
