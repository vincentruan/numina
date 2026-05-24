<template>
  <Teleport to="body">
    <div class="burst-overlay" aria-hidden="true">
      <span
        v-for="b in bursts"
        :key="b.id"
        class="burst-ring"
        :style="{ left: `${b.x}px`, top: `${b.y}px` }"
        @animationend="removeBurst(b.id)"
      />
      <span
        v-for="f in floats"
        :key="f.id"
        class="burst-float"
        :style="{ left: `${f.x}px`, top: `${f.y}px` }"
        @animationend="removeFloat(f.id)"
      >+{{ f.amount }} ⭐</span>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Burst { id: number; x: number; y: number }
interface Float { id: number; x: number; y: number; amount: number }

const bursts = ref<Burst[]>([])
const floats = ref<Float[]>([])
let nextId = 0

function spawnBurst(x: number, y: number): void {
  bursts.value.push({ id: nextId++, x, y })
}

function spawnFloat(x: number, y: number, amount: number): void {
  floats.value.push({ id: nextId++, x, y, amount })
}

function removeBurst(id: number): void {
  const idx = bursts.value.findIndex((b) => b.id === id)
  if (idx !== -1) bursts.value.splice(idx, 1)
}

function removeFloat(id: number): void {
  const idx = floats.value.findIndex((f) => f.id === id)
  if (idx !== -1) floats.value.splice(idx, 1)
}

defineExpose({ spawnBurst, spawnFloat })
</script>

<style scoped>
.burst-overlay {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1001;
}

.burst-ring {
  position: absolute;
  width: 16px;
  height: 16px;
  margin-left: -8px;
  margin-top: -8px;
  border-radius: 50%;
  border: 2px solid var(--color-brand-ochre);
  background: radial-gradient(circle, rgba(232, 185, 74, 0.55) 0%, rgba(232, 185, 74, 0) 70%);
  animation: burst-ring 380ms ease-out forwards;
}

@keyframes burst-ring {
  0%   { transform: scale(0.4); opacity: 0.95; }
  60%  { opacity: 0.7; }
  100% { transform: scale(2.4); opacity: 0; }
}

.burst-float {
  position: absolute;
  margin-left: 0;
  margin-top: 0;
  transform: translate(-50%, -50%);
  font-family: Inter, sans-serif;
  font-weight: 800;
  font-size: 22px;
  color: var(--color-brand-ochre);
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.25), 0 0 12px rgba(232, 185, 74, 0.7);
  animation: burst-float 1200ms cubic-bezier(0.17, 0.84, 0.44, 1) forwards;
  white-space: nowrap;
}

@keyframes burst-float {
  0%   { transform: translate(-50%, -50%) scale(0.6); opacity: 0; }
  20%  { transform: translate(-50%, -55%) scale(1.15); opacity: 1; }
  60%  { transform: translate(-50%, -85%) scale(1); opacity: 1; }
  100% { transform: translate(-50%, -130%) scale(0.95); opacity: 0; }
}
</style>
