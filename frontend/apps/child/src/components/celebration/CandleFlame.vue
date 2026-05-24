<template>
  <span
    class="candle-flame"
    role="img"
    :aria-label="ariaLabel"
    :data-state="state"
    @animationend="onAnimationEnd"
  >
    🕯️
  </span>
</template>

<script setup lang="ts">
const props = defineProps<{
  state: 'flickering' | 'bloom' | 'gutter'
  ariaLabel: string
}>()

const emit = defineEmits<{
  'bloom-end': []
  'gutter-end': []
}>()

function onAnimationEnd(e: AnimationEvent): void {
  if (props.state === 'bloom' && e.animationName === 'candle-bloom') {
    emit('bloom-end')
  } else if (props.state === 'gutter' && e.animationName === 'candle-gutter') {
    emit('gutter-end')
  }
}
</script>

<style scoped>
.candle-flame {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 20px;
  height: 20px;
  font-size: 16px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 2;
  transform-origin: center bottom;
}

.candle-flame[data-state='flickering'] {
  animation:
    candle-flicker 3s ease-in-out infinite,
    candle-jitter 2.5s ease-in-out 0.5s infinite;
}

.candle-flame[data-state='bloom'] {
  animation: candle-bloom 500ms ease-out forwards;
}

.candle-flame[data-state='gutter'] {
  animation: candle-gutter 600ms ease-in forwards;
}

@keyframes candle-flicker {
  0%, 100% { opacity: 0.7; }
  25% { opacity: 1; }
  50% { opacity: 0.8; }
  75% { opacity: 1; }
}

@keyframes candle-jitter {
  0%, 100% { transform: translateX(-1px); }
  50% { transform: translateX(1px); }
}

@keyframes candle-bloom {
  0% {
    transform: scale(1);
    filter: brightness(1) saturate(1);
    opacity: 1;
  }
  40% {
    transform: scale(1.6);
    filter: brightness(1.4) saturate(1.3);
    opacity: 1;
  }
  100% {
    transform: scale(1.4);
    filter: brightness(1.4) saturate(1.3);
    opacity: 0;
  }
}

@keyframes candle-gutter {
  0% { opacity: 1; }
  35% { opacity: 0.3; }
  70% { opacity: 0.05; }
  100% { opacity: 0; }
}
</style>
