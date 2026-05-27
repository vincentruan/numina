<template>
  <span class="sr-only" aria-live="polite">{{ exitMessage }}</span>
  <Transition name="overlay" @after-leave="onAfterLeave">
    <div
      v-if="isLoading"
      class="loading-overlay"
      :class="{ 'is-dismissing': isDismissing }"
      role="status"
      aria-live="polite"
      aria-label="加载中"
    >
      <GlassMask />
      <MusicWaveCanvas :dismissing="isDismissing" />
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useLoadingOverlay } from '../composables/loading'
import GlassMask from './GlassMask.vue'
import MusicWaveCanvas from './MusicWaveCanvas.vue'

const { isLoading, isDismissing } = useLoadingOverlay()

const exitMessage = ref('')
let srTimer: ReturnType<typeof setTimeout> | null = null

function onAfterLeave() {
  exitMessage.value = '加载完成'
  if (srTimer !== null) clearTimeout(srTimer)
  srTimer = setTimeout(() => { exitMessage.value = '' }, 1000)
}

onUnmounted(() => {
  if (srTimer !== null) clearTimeout(srTimer)
})
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
}

.loading-overlay.is-dismissing {
  /* Drop below Vant toast (z-index ~2000) so toasts are visible
     during the overlay's exit animation */
  z-index: 1999;
}

.overlay-enter-active {
  transition: opacity 0.2s ease;
}
.overlay-leave-active {
  transition: opacity 0.3s ease 0s;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
