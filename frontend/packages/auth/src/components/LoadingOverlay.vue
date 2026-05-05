<template>
  <Transition name="overlay" @after-leave="onAfterLeave">
    <div
      v-if="isLoading"
      class="loading-overlay"
      :class="{ 'is-dismissing': isDismissing }"
      aria-live="polite"
      aria-label="加载中"
    >
      <GlassMask />
      <MusicWaveCanvas :dismissing="isDismissing" />
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { useLoadingOverlay } from '../composables/loading'
import GlassMask from './GlassMask.vue'
import MusicWaveCanvas from './MusicWaveCanvas.vue'

const { isLoading, isDismissing } = useLoadingOverlay()

function onAfterLeave() {
  // nothing — state is managed by the composable
}
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
  /* Delay fade so the wave dismiss animation plays first */
  transition: opacity 0.35s ease 0.45s;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
</style>
