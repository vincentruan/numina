<script setup lang="ts">
/**
 * LiveTimer — reasoning duration display with live updates
 *
 * While endTime is undefined, shows a shimmer-animated "thinking" label
 * with elapsed time updating every second. Once endTime is set, displays
 * the final duration statically.
 */
import { ref, watch, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import ShimmerText from './ShimmerText.vue'

const props = defineProps<{
  startTime: number
  endTime?: number
}>()

const { t } = useI18n()

const now = ref(Date.now())
let timerId: ReturnType<typeof setInterval> | null = null

function startTimer() {
  if (timerId !== null) return
  timerId = setInterval(() => {
    now.value = Date.now()
  }, 1000)
}

function clearTimer() {
  if (timerId !== null) {
    clearInterval(timerId)
    timerId = null
  }
}

const isRunning = computed(() => props.endTime == null)

const elapsedMs = computed(() => {
  const end = props.endTime ?? now.value
  return Math.max(0, end - props.startTime)
})

// Start/stop timer based on running state
if (isRunning.value) {
  startTimer()
}

watch(isRunning, (running) => {
  if (!running) {
    clearTimer()
  }
})

onUnmounted(() => {
  clearTimer()
})

/**
 * Format duration:
 *  < 60s  → "Ns"       (e.g. "23s")
 *  < 5min → "Nm Ns"    (e.g. "1m 23s")
 *  ≥ 5min → "5m+"
 */
function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  if (totalSeconds >= 300) return '5m+'
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

const displayTime = computed(() => formatDuration(elapsedMs.value))
</script>

<template>
  <span v-if="isRunning" class="live-timer live-timer--running">
    <ShimmerText :text="t('aiChat.reasoning.thinking') + '...'" />
    <span class="live-timer__elapsed">({{ displayTime }})</span>
  </span>
  <span v-else class="live-timer live-timer--done">
    {{ t('aiChat.reasoning.thought') }} {{ displayTime }}
  </span>
</template>

<style scoped>
.live-timer {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary, #616161);
}

.live-timer__elapsed {
  font-variant-numeric: tabular-nums;
}
</style>
