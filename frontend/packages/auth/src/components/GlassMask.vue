<template>
  <div class="glass-mask" :class="{ 'no-backdrop': !supportsBackdrop }" />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const supportsBackdrop = ref(true)

onMounted(() => {
  supportsBackdrop.value = CSS.supports('backdrop-filter', 'blur(1px)') ||
    CSS.supports('-webkit-backdrop-filter', 'blur(1px)')
})
</script>

<style scoped>
.glass-mask {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.90);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
}

.glass-mask.no-backdrop {
  background: rgba(245, 245, 255, 0.88);
}

[data-theme='dark'] .glass-mask {
  background: rgba(1, 1, 32, 0.52);
  backdrop-filter: blur(12px) saturate(1.4);
  -webkit-backdrop-filter: blur(12px) saturate(1.4);
}

[data-theme='dark'] .glass-mask.no-backdrop {
  background: rgba(1, 1, 32, 0.82);
}
</style>
