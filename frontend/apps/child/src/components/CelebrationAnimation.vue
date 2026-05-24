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
          @confirm="onPopupConfirm"
          @auto-dismiss="onPopupConfirm"
          @cancel="onPopupCancel"
        />

        <FlyToTarget
          :active="flightActive"
          :origin="resolvedOrigins"
          :target="resolvedTarget"
          :particle-count="starCount"
          particle-type="star"
          :duration="800"
          :stagger-ms="120"
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
  }>(),
  {
    streakTier: 0,
    taskRefs: null,
    balanceRef: null,
    taskIds: () => [],
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

const resolvedOrigins = ref<Point[]>([])
const resolvedTarget = ref<Point | null>(null)

const choreo = useFlightChoreography()

const starCount = computed(() => {
  if (props.taskCount <= 1) return Math.min(props.taskCount + 2, 8)
  return Math.min(props.taskCount + 2, 12)
})

function resolveElementCenter(el: HTMLElement): Point {
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
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
          origins.push(resolveElementCenter(el))
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

function onPopupCancel(): void {
  popupVisible.value = false
  emit('dismiss')
}

function onParticleLanded(index: number): void {
  const origin = resolvedOrigins.value[index % resolvedOrigins.value.length] ?? null
  const target = resolvedTarget.value
  if (origin && target) {
    choreo.notifyLanding(origin, target)
  }
}

function onAllLanded(): void {
  choreo.notifyAllLanded()
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
