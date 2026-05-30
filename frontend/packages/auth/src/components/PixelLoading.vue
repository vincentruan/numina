<template>
  <Transition
    name="pixel-loading"
    @before-leave="onBeforeLeave"
  >
    <div
      v-if="show"
      class="pixel-loading"
      :class="{ 'is-dismissing': dismissing }"
      role="status"
      aria-live="polite"
      :aria-label="ariaLabel"
    >
      <div class="pixel-loading__stage">
        <div class="pixel-loading__scene">
          <div class="pixel-loading__character" :data-char="chosenIdx">
            <span class="pixel-loading__char-glyph">{{ chosenGlyph }}</span>
            <span class="pixel-loading__char-shadow" aria-hidden="true"></span>
          </div>
          <div class="pixel-loading__ground" aria-hidden="true">
            <div class="pixel-loading__track">
              <span
                v-for="i in 64"
                :key="i"
                class="pixel-loading__tile"
                :class="{ 'pixel-loading__tile--block': isBlockTile(i) }"
              >{{ tileText(i) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  visible: boolean
  dismissing?: boolean
  characters?: string[]
  ariaLabel?: string
}>(), {
  dismissing: false,
  characters: () => ['🦖', '🐷', '🐎', '🤖', '🐱', '👾'],
  ariaLabel: 'Loading',
})

const show = ref(false)
const chosenIdx = ref(0)
const chosenGlyph = ref(props.characters[0])

watch(
  () => props.visible,
  (v) => {
    if (v) {
      const pool = props.characters.length > 0 ? props.characters : ['🦖']
      chosenIdx.value = Math.floor(Math.random() * pool.length)
      chosenGlyph.value = pool[chosenIdx.value]
      show.value = true
    } else {
      show.value = false
    }
  },
  { immediate: true },
)

const PHRASE = ['L', 'O', 'A', 'D', 'I', 'N', 'G', '·']

function tileText(i: number) {
  return PHRASE[(i - 1) % PHRASE.length]
}

function isBlockTile(i: number) {
  return (i - 1) % PHRASE.length === PHRASE.length - 1
}

function onBeforeLeave(el: Element) {
  const e = el as HTMLElement
  const tx = (Math.random() * 2 - 1) * 48
  const ty = (Math.random() * 2 - 1) * 48
  const sc = Math.random() > 0.5 ? 0.96 : 1.04
  const rot = (Math.random() * 2 - 1) * 6
  e.style.setProperty('--pl-exit-tx', `${tx.toFixed(1)}px`)
  e.style.setProperty('--pl-exit-ty', `${ty.toFixed(1)}px`)
  e.style.setProperty('--pl-exit-sc', sc.toFixed(2))
  e.style.setProperty('--pl-exit-rot', `${rot.toFixed(1)}deg`)
}
</script>

<style scoped>
.pixel-loading {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  background: rgba(1, 1, 32, 0.72);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}

.pixel-loading.is-dismissing {
  /* Drop below Vant toast (z-index ~2000) so toasts are visible
     during the overlay's exit animation. */
  z-index: 1999;
}

.pixel-loading__stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(440px, 86vw);
  gap: 18px;
}

.pixel-loading__scene {
  position: relative;
  width: 100%;
  height: 120px;
  overflow: hidden;
}

.pixel-loading__character {
  position: absolute;
  left: 24%;
  bottom: 36px;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: pl-bounce 0.42s steps(2, end) infinite;
  transform-origin: 50% 100%;
  z-index: 2;
}

.pixel-loading__char-glyph {
  font-size: 56px;
  line-height: 1;
  image-rendering: pixelated;
  filter: drop-shadow(2px 3px 0 rgba(0, 0, 0, 0.45));
  user-select: none;
}

.pixel-loading__char-shadow {
  position: absolute;
  bottom: -4px;
  left: 50%;
  width: 38px;
  height: 6px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.35);
  transform: translateX(-50%);
  animation: pl-shadow 0.42s steps(2, end) infinite;
  z-index: 1;
}

@keyframes pl-bounce {
  0% { transform: translateY(0) rotate(-3deg); }
  50% { transform: translateY(-14px) rotate(3deg); }
  100% { transform: translateY(0) rotate(-3deg); }
}

@keyframes pl-shadow {
  0% { transform: translateX(-50%) scaleX(1); opacity: 0.5; }
  50% { transform: translateX(-50%) scaleX(0.6); opacity: 0.25; }
  100% { transform: translateX(-50%) scaleX(1); opacity: 0.5; }
}

.pixel-loading__ground {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 36px;
  overflow: hidden;
  border-top: 3px solid #bdbbff;
  border-bottom: 3px solid #6a68b3;
  background:
    repeating-linear-gradient(
      90deg,
      rgba(189, 187, 255, 0.18) 0 6px,
      rgba(189, 187, 255, 0.06) 6px 12px
    );
}

.pixel-loading__track {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  white-space: nowrap;
  font-family: 'Courier New', 'Press Start 2P', ui-monospace, monospace;
  font-size: 14px;
  font-weight: 800;
  color: #bdbbff;
  letter-spacing: 0.32em;
  text-shadow: 0 1px 0 rgba(1, 1, 32, 0.85);
  animation: pl-scroll 4.5s linear infinite;
  width: 200%;
}

.pixel-loading__tile {
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}

.pixel-loading__tile--block {
  color: rgba(189, 187, 255, 0.55);
}

@keyframes pl-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

/* Enter — quick fade-in */
.pixel-loading-enter-active {
  transition: opacity 0.2s ease;
}
.pixel-loading-enter-from {
  opacity: 0;
}

/* Leave — 300ms randomized exit (opacity + scale + translate + rotate) */
.pixel-loading-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease,
    filter 0.3s ease;
}
.pixel-loading-leave-to {
  opacity: 0;
  transform:
    translate(var(--pl-exit-tx, 0), var(--pl-exit-ty, 0))
    scale(var(--pl-exit-sc, 1))
    rotate(var(--pl-exit-rot, 0deg));
  filter: blur(2px);
}

@media (prefers-reduced-motion: reduce) {
  .pixel-loading__character,
  .pixel-loading__char-shadow,
  .pixel-loading__track {
    animation: none;
  }
  .pixel-loading-enter-active,
  .pixel-loading-leave-active {
    transition: opacity 0.15s ease;
  }
  .pixel-loading-leave-to {
    transform: none;
    filter: none;
  }
}
</style>
